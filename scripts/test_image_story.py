"""End-to-end debug script for image story timing.

Caches the derived data (script text, raw transcription) in /tmp/vg_cache
so the expensive LLM call can be iterated quickly.

Usage (from repo root):
    .venv/bin/python scripts/test_image_story.py            # full run
    .venv/bin/python scripts/test_image_story.py --llm-only # skip to LLM call (uses cache)
    .venv/bin/python scripts/test_image_story.py --fresh     # ignore cache
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

os.environ["CONFIG_PATH"] = "config.prod.yaml"

from src.core.container import container  # noqa: E402
from src.entities.language import Language  # noqa: E402
from src.services.reddit_video_service import RedditVideoService  # noqa: E402

REDDIT_URL = (
    "https://www.reddit.com/r/pettyrevenge/comments/1sl1h1e/"
    "you_wont_stop_my_ride_you_dont_get_paid/"
)

CACHE_DIR = "/tmp/vg_cache"


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def _save_json(name: str, data: object) -> None:
    with open(_cache_path(name), "w") as f:
        json.dump(data, f, ensure_ascii=False)


def _load_json(name: str) -> object | None:
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-only", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    container.wire(modules=[__name__])
    service: RedditVideoService = container.reddit_video_service()
    language = Language.PORTUGUESE

    cached = _load_json("image_story_cache") if not args.fresh else None

    if cached and args.llm_only:
        print("[cache] Using cached script + transcription data")
        part1_text = cached["part1_text"]
        part2_text = cached["part2_text"]
        raw1 = cached["raw_part1_data"]
        raw2 = cached["raw_part2_data"]
    else:
        print("Scraping post...", flush=True)
        post = service.scrape_post(REDDIT_URL)
        print(f"  Title: {post.title!r}")

        print("Generating script...", flush=True)
        script = await service.generate_script(post, language=language)
        part1_text = script.part1
        part2_text = script.part2

        print("Generating audio...", flush=True)
        audio = await service.generate_audio(script, language=language)

        print("Generating captions pair...", flush=True)
        captions = await service.generate_captions_pair(
            audio, script, language=language
        )
        raw1 = captions.raw_part1_data
        raw2 = captions.raw_part2_data

        _save_json(
            "image_story_cache",
            {
                "part1_text": part1_text,
                "part2_text": part2_text,
                "raw_part1_data": raw1,
                "raw_part2_data": raw2,
            },
        )
        print("[cache] Saved script + transcription data")

    # ── Content boundaries ──────────────────────────────────────────
    for part_name, raw_data in [("Part 1", raw1), ("Part 2", raw2)]:
        intro_end_time, cta_start_time, offset, zero_based = (
            RedditVideoService._compute_content_boundaries(raw_data)
        )
        words = [w["word"] for w in zero_based]
        total_duration = zero_based[-1]["end"] if zero_based else 0

        print(f"\n{'='*60}")
        print(f"  {part_name} — Content Boundaries")
        print(f"{'='*60}")
        print(f"  Raw transcription words: {len(raw_data)}")
        print(f"  intro_end_time:          {intro_end_time}s")
        print(f"  cta_start_time:          {cta_start_time}s")
        print(f"  offset (shift):          {offset}s")
        print(f"  Content words:           {len(words)}")
        print(f"  Content duration:        {total_duration:.2f}s")
        print(f"  First 10 words:          {words[:10]}")
        print(f"  Last 10 words:           {words[-10:]}")

    # ── LLM image story — both parts via generate_image_story ──────
    llm_proxy = service._llm_proxy
    style_ctx = None

    for part_label, story_text, raw_data in [
        ("Part 1", part1_text, raw1),
        ("Part 2", part2_text, raw2),
    ]:
        print(f"\n{'='*60}")
        print(f"  LLM Image Story — {part_label}")
        print(f"{'='*60}")

        iet, csat, off, zb = RedditVideoService._compute_content_boundaries(raw_data)
        print(f"  intro_end_time={iet}  cta_start_time={csat}  offset={off}")
        print(f"  Content: {len(zb)} words, {zb[-1]['end']:.2f}s duration")

        image_story = await llm_proxy.generate_image_story(
            story_text=story_text,
            transcription=zb,
            style_context=style_ctx,
            introduction_end_time=iet,
            call_to_action_start_time=csat,
        )

        print(f"\n  ImageStory validated OK")
        print(f"  introduction_end_time:     {image_story.introduction_end_time}")
        print(f"  call_to_action_start_time: {image_story.call_to_action_start_time}")
        print(f"  Images ({len(image_story.images)}):")

        before = [img.start_time for img in image_story.images]
        for i, img in enumerate(image_story.images):
            print(f"    [{i:2d}] t={img.start_time:>8.3f} | {img.description[:70]}")

        RedditVideoService._shift_images_back(image_story, off)
        after = [img.start_time for img in image_story.images]

        print(f"\n  After _shift_images_back (offset={off}):")
        for i, (b, a) in enumerate(zip(before, after)):
            print(f"    [{i:2d}] {b:>8.3f} -> {a:>8.3f}")

        last_img_time = after[-1]
        audio_duration = raw_data[-1]["end"] if raw_data else 0
        print(
            f"\n  Last image at {last_img_time:.3f}s vs audio ends at {audio_duration:.2f}s"
        )

        style_ctx = RedditVideoService._extract_style_context(image_story)

    print(f"\n{'='*60}")
    print("  ALL DONE — both parts generated and validated successfully")
    print(f"{'='*60}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
