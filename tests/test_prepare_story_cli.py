"""Tests for the local story-preparation CLI (scripts/prepare_story.py).

No subcommand may reach a paid model, so every collaborator is faked here and
the assertions focus on what the CLI itself is responsible for: what it passes
to the services, what it writes to disk, what it prints and its exit code.
"""

import json
import time

import pytest

from scripts import prepare_story
from src.core.container import container
from src.entities.config import EvaluationConfig, MainConfig
from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import StoryCandidate
from tests.test_prepared_story_package import package_payload


def make_post(post_id: str, title: str, score: int = 2500) -> RedditPost:
    return RedditPost(
        title=title,
        content=f"Conteudo completo do post {post_id}.\n\nSegundo paragrafo.",
        community="r/pettyrevenge",
        author="u/someone",
        community_url_photo="https://styles.redditmedia.com/icon.png",
        url=f"https://www.reddit.com/r/pettyrevenge/comments/{post_id}/slug/",
        score=score,
        num_comments=310,
        upvote_ratio=0.96,
        created_utc=time.time() - 7200,
    )


class FakeStoryFinder:
    def __init__(self, candidates: list[StoryCandidate]):
        self._candidates = candidates
        self.calls: list[dict] = []

    async def find_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._candidates)

    async def find_best_stories(self, **kwargs):
        raise AssertionError("the CLI must never run the LLM evaluation")


class FakeRedditProxy:
    def __init__(self, post: RedditPost):
        self._post = post
        self.requested: list[str] = []

    def get_reddit_post(self, url: str) -> RedditPost:
        self.requested.append(url)
        return self._post


@pytest.fixture
def config():
    cfg = MainConfig(
        language=Language.PORTUGUESE,
        evaluation=EvaluationConfig(subreddits=["pettyrevenge", "Antiwork"]),
    )
    container.main_config.override(cfg)
    yield cfg
    container.main_config.reset_override()


@pytest.fixture
def finder():
    fake = FakeStoryFinder(
        [
            StoryCandidate(
                post=make_post("aaa111", "Primeira historia"),
                deterministic_score=78.4,
                score_breakdown={"length": 100.0},
            ),
            StoryCandidate(
                post=make_post("bbb222", "Segunda historia"),
                deterministic_score=61.2,
                score_breakdown={"length": 80.0},
            ),
        ]
    )
    container.story_finder_service.override(fake)
    yield fake
    container.story_finder_service.reset_override()


def write_package(directory, **overrides) -> str:
    payload = package_payload(**overrides)
    path = (
        directory
        / f"{payload['post']['url'].split('/comments/')[1].split('/')[0]}.json"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestFind:
    def test_writes_candidates_file(self, tmp_path, config, finder, capsys):
        code = prepare_story.main(["find", "--out", str(tmp_path)])

        assert code == 0
        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert data["sort"] == "top"
        assert data["time_filter"] == "day"
        assert data["subreddits"] == ["pettyrevenge", "Antiwork"]
        assert data["generated_at"]
        assert [c["rank"] for c in data["candidates"]] == [1, 2]
        assert data["candidates"][0]["deterministic_score"] == 78.4
        assert data["candidates"][0]["post"]["title"] == "Primeira historia"

    def test_prints_the_shortlist(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert "Primeira historia" in out
        assert "78.4" in out
        assert "pettyrevenge" in out
        assert "310" in out
        assert "https://www.reddit.com/r/pettyrevenge/comments/aaa111/slug/" in out

    def test_forwards_the_search_options(self, tmp_path, config, finder):
        prepare_story.main(
            [
                "find",
                "--out",
                str(tmp_path),
                "--sort",
                "hot",
                "--time",
                "week",
                "--per-sub",
                "10",
                "--top-per-sub",
                "2",
                "--sub",
                "r/Antiwork",
            ]
        )

        call = finder.calls[0]
        assert call["sort"] == "hot"
        assert call["time_filter"] == "week"
        assert call["posts_per_sub"] == 10
        assert call["top_per_sub"] == 2
        assert call["subreddits"] == ["Antiwork"]

    def test_excludes_packages_already_prepared(self, tmp_path, config, finder):
        write_package(tmp_path)

        prepare_story.main(["find", "--out", str(tmp_path)])

        excluded = finder.calls[0]["exclude_urls"]
        assert (
            "https://www.reddit.com/r/MaliciousCompliance/comments/1vuze4m/"
            "no_second_date_and_i_cant_be_happier/" in excluded
        )


class TestShow:
    def test_prints_the_full_original_text(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["show", "2", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert code == 0
        assert "Segunda historia" in out
        assert "Conteudo completo do post bbb222." in out
        assert "Segundo paragrafo." in out

    def test_unknown_rank_fails(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])

        code = prepare_story.main(["show", "9", "--out", str(tmp_path)])

        assert code == 1

    def test_url_appends_the_post_as_the_next_rank(
        self, tmp_path, config, finder, capsys
    ):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        post = make_post("ccc333", "Historia vinda de URL")
        proxy = FakeRedditProxy(post)
        container.reddit_proxy.override(proxy)
        try:
            code = prepare_story.main(
                ["show", "--url", post.url, "--out", str(tmp_path)]
            )
        finally:
            container.reddit_proxy.reset_override()

        out = capsys.readouterr().out
        assert code == 0
        assert proxy.requested == [post.url]
        assert "Historia vinda de URL" in out
        assert "#3" in out

        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert [c["rank"] for c in data["candidates"]] == [1, 2, 3]
        assert data["candidates"][2]["post"]["title"] == "Historia vinda de URL"

    def test_url_works_without_a_previous_find(self, tmp_path, config, capsys):
        post = make_post("ccc333", "Historia vinda de URL")
        container.reddit_proxy.override(FakeRedditProxy(post))
        try:
            code = prepare_story.main(
                ["show", "--url", post.url, "--out", str(tmp_path)]
            )
        finally:
            container.reddit_proxy.reset_override()

        assert code == 0
        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert [c["rank"] for c in data["candidates"]] == [1]


class TestPrompt:
    def test_prints_the_server_prompt_for_the_candidate(
        self, tmp_path, config, finder, capsys
    ):
        from src.proxies.prompts.render import render_story_prompt

        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["prompt", "1", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert code == 0
        expected = render_story_prompt(
            "Primeira historia",
            "Conteudo completo do post aaa111.\n\nSegundo paragrafo.",
            Language.PORTUGUESE,
        )
        assert out.strip() == expected.strip()

    def test_language_can_be_overridden(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        prepare_story.main(["prompt", "1", "--out", str(tmp_path), "--language", "en"])

        assert "English" in capsys.readouterr().out


class TestValidate:
    def test_valid_package_passes(self, tmp_path, config, capsys):
        path = write_package(tmp_path)

        code = prepare_story.main(["validate", path])

        assert code == 0
        assert "✓" in capsys.readouterr().out

    def test_forbidden_word_fails_with_the_problem_list(self, tmp_path, config, capsys):
        path = write_package(
            tmp_path,
            script_text="No fim das contas ele matou a paciencia de todo mundo.",
        )

        code = prepare_story.main(["validate", path])

        out = capsys.readouterr().out
        assert code == 1
        assert "✗" in out
        assert "script_text: 'matou' em" in out

    def test_wrong_language_fails(self, tmp_path, config, capsys):
        path = write_package(tmp_path, language="en")

        code = prepare_story.main(["validate", path])

        assert code == 1
        assert "language: package=en server=pt" in capsys.readouterr().out

    def test_malformed_package_is_reported_not_crashed(self, tmp_path, config, capsys):
        path = tmp_path / "broken.json"
        path.write_text('{"version": 1}', encoding="utf-8")

        code = prepare_story.main(["validate", str(path)])

        assert code == 1
        assert "✗" in capsys.readouterr().out

    def test_one_bad_file_fails_the_whole_run(self, tmp_path, config, capsys):
        good = write_package(tmp_path)
        bad = tmp_path / "broken.json"
        bad.write_text("not json at all", encoding="utf-8")

        code = prepare_story.main(["validate", good, str(bad)])

        out = capsys.readouterr().out
        assert code == 1
        assert "✓" in out and "✗" in out


class TestList:
    def test_lists_packages_with_preview_status(self, tmp_path, config, capsys):
        write_package(tmp_path)

        code = prepare_story.main(["list", "--out", str(tmp_path)])
        out = capsys.readouterr().out

        assert code == 0
        assert "1vuze4m" in out
        assert "Ele pediu pra eu ignorar o encontro dele" in out
        assert "2026-09-21" in out
        assert "sem mp3" in out

        (tmp_path / "1vuze4m.preview.mp3").write_bytes(b"x")
        prepare_story.main(["list", "--out", str(tmp_path)])

        assert "mp3 ok" in capsys.readouterr().out

    def test_ignores_the_candidates_file(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["list", "--out", str(tmp_path)])

        assert code == 0
        assert "Nenhum pacote" in capsys.readouterr().out
