"""Service that finds the best Reddit stories for TikTok across configured subreddits.

Pipeline:
1. Fetch posts from all configured subreddits.
2. Compute deterministic scores per-sub (relative) + global (absolute).
3. Take the top N candidates globally.
4. Evaluate each with the LLM.
5. Return EvaluatedStory list sorted by LLM grade descending.
"""

import math
import re
import time
from typing import List, Literal, Optional
import statistics

from src.core.logging_config import get_logger
from src.entities.config import EvaluationConfig
from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import StoryCandidate, EvaluatedStory
from src.proxies.interfaces import IRedditProxy, ILLMProxy

logger = get_logger(__name__)

IDEAL_CHAR_MIN = 1500
IDEAL_CHAR_MAX = 4000

# Weights for the final deterministic score
W_RELATIVE_UPVOTES = 0.20
W_RELATIVE_COMMENTS = 0.10
W_ABSOLUTE_ENGAGEMENT = 0.20
W_COMMENT_RATIO = 0.10
W_UPVOTE_RATIO = 0.05
W_LENGTH = 0.15
W_TEXT_QUALITY = 0.15
W_FRESHNESS = 0.05


def _log_ratio_score(value: float, median: float) -> float:
    """0-100 score using log-scale comparison to median.

    log2(value/median) mapped so that: at median -> 50, 2x -> 70, 4x -> 85, 8x -> 95.
    Below median scales down proportionally.
    """
    if median <= 0:
        median = 1.0
    if value <= 0:
        return 0.0
    ratio = value / median
    log_score = 50.0 + 20.0 * math.log2(max(ratio, 0.01))
    return max(0.0, min(100.0, log_score))


def _absolute_engagement_score(upvotes: int, comments: int) -> float:
    """0-100 score based on raw engagement numbers (log-scaled).

    Benchmarks: 100 pts -> ~30, 500 pts -> ~50, 2000 pts -> ~70, 10000 pts -> ~90.
    """
    combined = upvotes + comments * 2
    if combined <= 0:
        return 0.0
    return min(100.0, math.log10(combined) / math.log10(50000) * 100.0)


def _comment_ratio_score(comments: int, upvotes: int) -> float:
    """0-100 score for comments-to-upvotes ratio. High ratio = debate/engagement.

    Sweet spot: 0.15-0.50 comments per upvote.
    """
    if upvotes <= 0:
        return 50.0
    ratio = comments / upvotes
    if 0.15 <= ratio <= 0.50:
        return 100.0
    if ratio < 0.15:
        return max(0.0, (ratio / 0.15) * 100.0)
    # ratio > 0.50 — still good but diminishing
    return max(50.0, 100.0 - (ratio - 0.50) * 50.0)


def _upvote_ratio_score(upvote_ratio: Optional[float]) -> float:
    """0-100 based on Reddit's upvote_ratio. High = consensus, moderate = debate."""
    if upvote_ratio is None:
        return 50.0
    # 0.95+ is great (consensus), 0.80-0.95 is good, below 0.70 is controversial
    if upvote_ratio >= 0.90:
        return 90.0 + (upvote_ratio - 0.90) * 100.0
    if upvote_ratio >= 0.75:
        return 60.0 + (upvote_ratio - 0.75) / 0.15 * 30.0
    return max(0.0, upvote_ratio / 0.75 * 60.0)


def _length_score(char_count: int) -> float:
    """0-100 score for content length. Peak at IDEAL_CHAR_MIN..IDEAL_CHAR_MAX."""
    if IDEAL_CHAR_MIN <= char_count <= IDEAL_CHAR_MAX:
        return 100.0
    if char_count < IDEAL_CHAR_MIN:
        return max(0.0, (char_count / IDEAL_CHAR_MIN) * 100)
    overshoot = char_count - IDEAL_CHAR_MAX
    return max(0.0, 100.0 - (overshoot / IDEAL_CHAR_MAX) * 50)


def _text_quality_score(content: str) -> float:
    """0-100 heuristic score for narrative text quality without LLM."""
    score = 0.0

    # First-person narrative (strong signal for storytelling)
    first_person = len(re.findall(r'\b(?:I|my|me|mine|myself)\b', content, re.IGNORECASE))
    if first_person >= 10:
        score += 30.0
    elif first_person >= 5:
        score += 20.0
    elif first_person >= 2:
        score += 10.0

    # Dialogue presence (quotes indicate vivid storytelling)
    quotes = content.count('"') // 2
    if quotes >= 3:
        score += 25.0
    elif quotes >= 1:
        score += 15.0

    # Paragraph structure (well-structured posts have multiple paragraphs)
    paragraphs = len([p for p in content.split('\n') if p.strip()])
    if paragraphs >= 5:
        score += 25.0
    elif paragraphs >= 3:
        score += 15.0
    elif paragraphs >= 2:
        score += 10.0

    # Sentence variety (not just a wall of text)
    sentences = len(re.findall(r'[.!?]+', content))
    if sentences >= 10:
        score += 20.0
    elif sentences >= 5:
        score += 10.0

    return min(100.0, score)


def _freshness_score(created_utc: Optional[float]) -> float:
    """0-100 bonus for recent posts. A post getting high engagement quickly is hotter."""
    if created_utc is None:
        return 50.0
    age_hours = (time.time() - created_utc) / 3600.0
    if age_hours <= 0:
        return 100.0
    # < 6h -> 100, 12h -> 80, 24h -> 60, 48h -> 40
    return max(0.0, min(100.0, 120.0 - 20.0 * math.log2(max(age_hours, 1))))


def score_candidates(posts: List[RedditPost]) -> List[StoryCandidate]:
    """Score a batch of posts from the SAME subreddit using deterministic metrics."""
    if not posts:
        return []

    scores_list = [p.score or 0 for p in posts]
    comments_list = [p.num_comments or 0 for p in posts]

    median_score = statistics.median(scores_list) if scores_list else 1
    median_comments = statistics.median(comments_list) if comments_list else 1

    candidates = []
    for post in posts:
        ups = post.score or 0
        coms = post.num_comments or 0
        chars = len(post.content)

        rel_upvotes = _log_ratio_score(ups, median_score)
        rel_comments = _log_ratio_score(coms, median_comments)
        abs_engagement = _absolute_engagement_score(ups, coms)
        com_ratio = _comment_ratio_score(coms, ups)
        up_ratio = _upvote_ratio_score(post.upvote_ratio)
        length = _length_score(chars)
        text_q = _text_quality_score(post.content)
        fresh = _freshness_score(post.created_utc)

        total = (
            rel_upvotes * W_RELATIVE_UPVOTES
            + rel_comments * W_RELATIVE_COMMENTS
            + abs_engagement * W_ABSOLUTE_ENGAGEMENT
            + com_ratio * W_COMMENT_RATIO
            + up_ratio * W_UPVOTE_RATIO
            + length * W_LENGTH
            + text_q * W_TEXT_QUALITY
            + fresh * W_FRESHNESS
        )

        candidates.append(
            StoryCandidate(
                post=post,
                deterministic_score=round(total, 1),
                score_breakdown={
                    "rel_upvotes": round(rel_upvotes, 1),
                    "rel_comments": round(rel_comments, 1),
                    "abs_engagement": round(abs_engagement, 1),
                    "comment_ratio": round(com_ratio, 1),
                    "upvote_ratio": round(up_ratio, 1),
                    "length": round(length, 1),
                    "text_quality": round(text_q, 1),
                    "freshness": round(fresh, 1),
                    "median_upvotes": round(median_score, 1),
                    "median_comments": round(median_comments, 1),
                },
            )
        )

    return candidates


class StoryFinderService:
    def __init__(
        self,
        reddit_proxy: IRedditProxy,
        evaluation_llm_proxy: Optional[ILLMProxy],
        llm_proxy: ILLMProxy,
        evaluation_config: EvaluationConfig,
    ):
        self._reddit = reddit_proxy
        self._llm = evaluation_llm_proxy or llm_proxy
        self._config = evaluation_config

    async def find_best_stories(
        self,
        sort: Literal["top", "new", "hot"] = "top",
        time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "day",
        posts_per_sub: int = 25,
        top_per_sub: int = 2,
        language: Language = Language.PORTUGUESE,
    ) -> List[EvaluatedStory]:
        finalists: List[StoryCandidate] = []

        for sub in self._config.subreddits:
            logger.info("Fetching posts from r/%s ...", sub)
            try:
                posts = self._reddit.list_subreddit_posts(
                    subreddit=sub,
                    sort=sort,
                    time_filter=time_filter,
                    limit=posts_per_sub,
                    min_chars=self._config.min_chars,
                    max_chars=self._config.max_chars,
                )
            except Exception:
                logger.exception("Failed to fetch r/%s, skipping", sub)
                continue

            scored = score_candidates(posts)
            scored.sort(key=lambda c: c.deterministic_score, reverse=True)
            picked = scored[:top_per_sub]
            finalists.extend(picked)
            logger.info(
                "  r/%s: %d posts fetched, top %d picked (best det=%.1f)",
                sub,
                len(posts),
                len(picked),
                picked[0].deterministic_score if picked else 0,
            )

        logger.info(
            "%d finalists from %d subs. Running LLM evaluation...",
            len(finalists),
            len(self._config.subreddits),
        )

        evaluated: List[EvaluatedStory] = []
        for i, candidate in enumerate(finalists, 1):
            post = candidate.post
            sub_name = post.community.replace("r/", "")
            logger.info(
                "  [%d/%d] Evaluating (r/%s, det=%.1f): %s",
                i,
                len(finalists),
                sub_name,
                candidate.deterministic_score,
                post.title[:50],
            )
            try:
                evaluation = await self._llm.evaluate_story(
                    title=post.title,
                    content=post.content,
                    target_language=language,
                )
            except Exception:
                logger.exception("LLM evaluation failed for '%s'", post.title[:60])
                evaluation = {"nota_geral": 0.0, "veredito": "Erro", "resumo": "", "notas": {}}

            evaluated.append(
                EvaluatedStory(
                    post=post,
                    deterministic_score=candidate.deterministic_score,
                    evaluation=evaluation,
                )
            )

        evaluated.sort(key=lambda e: e.nota_geral, reverse=True)
        worthy = [e for e in evaluated if e.veredito in ("Excelente", "Boa")]
        logger.info(
            "%d/%d stories rated Boa or Excelente",
            len(worthy),
            len(evaluated),
        )
        return worthy
