import argparse
import asyncio
import os

from src.entities.language import Language
from src.core.container import container


async def main():
    parser = argparse.ArgumentParser(
        description="Generate a two-part Reddit history video via the DI container"
    )
    parser.add_argument("post_url", type=str, help="Reddit post URL")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to place the resulting videos",
    )
    parser.add_argument(
        "--language",
        type=str,
        choices=[l.value for l in Language],
        default=Language.PORTUGUESE.value,
        help="Language for story and speech",
    )
    parser.add_argument(
        "--gender",
        type=str,
        choices=["male", "female"],
        default=None,
        help="TTS voice gender (auto-detected from post if not specified)",
    )
    parser.add_argument("--rate", type=float, default=1.0, help="TTS speech rate")
    parser.add_argument(
        "--low-quality",
        action="store_true",
        help="Downscale video to 400px width for fast local rendering",
    )

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    out_part1 = os.path.join(args.output_dir, "part1.mp4")
    out_part2 = os.path.join(args.output_dir, "part2.mp4")

    print(f"Resolving dependencies...")
    # Trigger wiring of the entire application
    container.wire(modules=[__name__])

    reddit_video_service = container.reddit_video_service()

    lang_enum = Language(args.language)

    print(f"Starting pipeline for post: {args.post_url}")
    result = await reddit_video_service.generate_two_part_history_video(
        post_url=args.post_url,
        output_path_part1=out_part1,
        output_path_part2=out_part2,
        language=lang_enum,
        speech_gender=args.gender,
        speech_rate=args.rate,
        low_quality=args.low_quality,
    )

    print("\nGeneration Complete!")
    print(f"Part 1 saved at: {result.part1_path}")
    print(f"Part 2 saved at: {result.part2_path}")


if __name__ == "__main__":
    asyncio.run(main())
