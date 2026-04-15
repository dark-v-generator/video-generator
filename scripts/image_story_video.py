"""Generate an image-story video from a Reddit post URL.

Usage:
    uv run python scripts/image_story_video.py <reddit_url> [--output-dir output] [--low-quality]
"""

import argparse
import asyncio
import os

from src.entities.language import Language
from src.core.container import container


async def main():
    parser = argparse.ArgumentParser(
        description="Generate an image-story Reddit video via the DI container"
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

    print("Resolving dependencies...")
    container.wire(modules=[__name__])

    reddit_video_service = container.reddit_video_service()

    lang_enum = Language(args.language)

    print(f"Starting image-story pipeline for post: {args.post_url}")
    result = await reddit_video_service.generate_image_story_video(
        post_url=args.post_url,
        language=lang_enum,
        speech_gender=args.gender,
        speech_rate=args.rate,
        low_quality=args.low_quality,
    )

    out = args.output_dir

    with open(os.path.join(out, "part1.mp4"), "wb") as f:
        f.write(result.part1_video)
    with open(os.path.join(out, "part2.mp4"), "wb") as f:
        f.write(result.part2_video)
    with open(os.path.join(out, "story.md"), "w", encoding="utf-8") as f:
        f.write(result.story_md)
    with open(os.path.join(out, "original_post.md"), "w", encoding="utf-8") as f:
        f.write(result.original_post_md)
    with open(os.path.join(out, "audio_part1.mp3"), "wb") as f:
        f.write(result.audio_part1)
    with open(os.path.join(out, "audio_part2.mp3"), "wb") as f:
        f.write(result.audio_part2)
    with open(os.path.join(out, "captions_part1.json"), "w", encoding="utf-8") as f:
        f.write(result.captions_part1_json)
    with open(os.path.join(out, "captions_part2.json"), "w", encoding="utf-8") as f:
        f.write(result.captions_part2_json)
    with open(os.path.join(out, "image_story_part1.json"), "w", encoding="utf-8") as f:
        f.write(result.image_story_part1_json)
    with open(os.path.join(out, "image_story_part2.json"), "w", encoding="utf-8") as f:
        f.write(result.image_story_part2_json)
    if result.cover_part1_png:
        with open(os.path.join(out, "cover_part1.png"), "wb") as f:
            f.write(result.cover_part1_png)
    if result.cover_part2_png:
        with open(os.path.join(out, "cover_part2.png"), "wb") as f:
            f.write(result.cover_part2_png)

    print("\nGeneration Complete!")
    print(f"All artifacts saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
