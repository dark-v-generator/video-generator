import argparse
import asyncio

from src.core.container import container
from src.entities.config import MainConfig


def print_posts(subreddit: str, posts: list) -> None:
    print(f"\n{'=' * 70}")
    print(f"  r/{subreddit}  —  {len(posts)} posts")
    print(f"{'=' * 70}")

    for i, post in enumerate(posts, 1):
        chars = len(post.content)
        score = post.score or 0
        comments = post.num_comments or 0
        print(f"\n  {i}. [{score:>5} pts | {comments:>4} comments | {chars:>5} chars]")
        print(f"     {post.title[:80]}")
        if post.url:
            print(f"     {post.url}")


def main():
    parser = argparse.ArgumentParser(
        description="List recent Reddit posts from configured subreddits"
    )
    parser.add_argument(
        "--sub",
        type=str,
        default=None,
        help="Single subreddit to list (overrides config list)",
    )
    parser.add_argument(
        "--sort",
        type=str,
        choices=["top", "new", "hot"],
        default="top",
    )
    parser.add_argument(
        "--time",
        type=str,
        choices=["hour", "day", "week", "month", "year", "all"],
        default="day",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-chars", type=int, default=None)
    parser.add_argument("--max-chars", type=int, default=None)

    args = parser.parse_args()

    container.wire(modules=[__name__])

    config: MainConfig = container.main_config()
    reddit_proxy = container.reddit_proxy()
    eval_config = config.evaluation

    min_chars = args.min_chars if args.min_chars is not None else eval_config.min_chars
    max_chars = args.max_chars if args.max_chars is not None else eval_config.max_chars

    subreddits = [args.sub] if args.sub else eval_config.subreddits

    total = 0
    for sub in subreddits:
        posts = reddit_proxy.list_subreddit_posts(
            subreddit=sub,
            sort=args.sort,
            time_filter=args.time,
            limit=args.limit,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        print_posts(sub, posts)
        total += len(posts)

    print(f"\n{'─' * 70}")
    print(f"  Total: {total} posts from {len(subreddits)} subreddits")
    print(f"  Filters: sort={args.sort}, time={args.time}, chars=[{min_chars}, {max_chars}]")
    print(f"{'─' * 70}\n")


if __name__ == "__main__":
    main()
