import argparse
import asyncio

from src.core.container import container
from src.entities.language import Language


LLM_LABELS = {
    "retencao": "Retenção",
    "qualidade": "Qualidade",
    "viralizacao": "Viralização",
    "adequacao_tiktok": "TikTok Fit",
    "gancho": "Gancho",
}


def _bar(value: float, width: int = 15) -> str:
    filled = round(value / 100 * width)
    return "█" * filled + "░" * (width - filled)


def print_results(evaluated: list) -> None:
    if not evaluated:
        print("\nNenhuma história encontrada.\n")
        return

    print(f"\n{'=' * 70}")
    print(f"  {len(evaluated)} MELHORES HISTÓRIAS (Boa+)  —  ordenadas por nota LLM")
    print(f"{'=' * 70}")

    for i, story in enumerate(evaluated, 1):
        post = story.post
        ev = story.evaluation
        notas = ev.get("notas", {})

        print(f"\n{'─' * 70}")
        print(f"  #{i}  [{story.veredito}]  LLM: {story.nota_geral}/100  |  Det: {story.deterministic_score}/100")
        print(f"  {post.title[:80]}")
        ratio_str = f"{post.upvote_ratio:.0%}" if post.upvote_ratio else "n/a"
        print(f"  r/{post.community.replace('r/', '')}  |  {post.score or 0} pts ({ratio_str})  |  {post.num_comments or 0} comments  |  {len(post.content)} chars")
        if post.url:
            print(f"  {post.url}")

        print(f"\n  LLM Evaluation:")
        for key, label in LLM_LABELS.items():
            entry = notas.get(key, {})
            nota = entry.get("nota", 0)
            print(f"    {label:<14} {_bar(nota)} {nota}/100")

        if story.resumo:
            resumo = story.resumo[:200]
            if len(story.resumo) > 200:
                resumo += "..."
            print(f"\n  Resumo: {resumo}")

    print(f"\n{'=' * 70}\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Find and evaluate the best Reddit stories for TikTok"
    )
    parser.add_argument("--sort", choices=["top", "new", "hot"], default="top")
    parser.add_argument(
        "--time",
        choices=["hour", "day", "week", "month", "year", "all"],
        default="day",
    )
    parser.add_argument("--top-per-sub", type=int, default=2, help="Best posts to pick per subreddit")
    parser.add_argument("--per-sub", type=int, default=25, help="Posts to fetch per subreddit")

    args = parser.parse_args()

    container.wire(modules=[__name__])
    finder = container.story_finder_service()

    print(f"Finding best stories (sort={args.sort}, time={args.time}, top_per_sub={args.top_per_sub})...\n")

    results = await finder.find_best_stories(
        sort=args.sort,
        time_filter=args.time,
        posts_per_sub=args.per_sub,
        top_per_sub=args.top_per_sub,
        language=Language.PORTUGUESE,
    )

    print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
