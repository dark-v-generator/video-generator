"""Generate a video from AI-generated images timed to an existing narration.

Usage:
    uv run python scripts/image_story_video.py \
        --audio output/audio_part1.mp3 \
        --image-story output/image_story_part1.json \
        --captions output/captions_part1.json \
        --cover output/cover.png \
        --output output/image_story_part1.mp4
"""

import argparse
import asyncio
import json
import os

from src.entities.captions import Captions, CaptionSegment
from src.entities.config import MainConfig
from src.entities.configs.services.captions import CaptionsConfig
from src.entities.editor.audio_clip import AudioClip
from src.entities.editor.captions_clip import CaptionsClip
from src.entities.editor.image_clip import ImageClip
from src.entities.image_story import ImageStory
from src.proxies.mock_image_proxy import MockImageGeneratorProxy
from src.services.video_service import VideoService


def load_captions(captions_path: str, font_path: str) -> CaptionsClip:
    with open(captions_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    segments = [
        CaptionSegment(start=w["start"], end=w["end"], text=w["word"])
        for w in raw
    ]
    captions = Captions(segments=segments)
    config = CaptionsConfig()
    with open(font_path, "rb") as f:
        font_bytes = f.read()
    return CaptionsClip(captions=captions, config=config, font_bytes=font_bytes)


async def main():
    parser = argparse.ArgumentParser(
        description="Generate an image-story video from a narration + image timeline JSON"
    )
    parser.add_argument(
        "--audio", type=str, required=True, help="Path to the narration audio (mp3)"
    )
    parser.add_argument(
        "--image-story",
        type=str,
        required=True,
        help="Path to the image story JSON file",
    )
    parser.add_argument(
        "--captions", type=str, default=None, help="Path to captions JSON"
    )
    parser.add_argument(
        "--cover", type=str, default=None, help="Path to cover PNG"
    )
    parser.add_argument(
        "--output", type=str, default="output/image_story.mp4", help="Output video path"
    )
    parser.add_argument(
        "--low-quality",
        action="store_true",
        help="Downscale for fast preview rendering",
    )
    parser.add_argument(
        "--font-path",
        type=str,
        default="default_font.ttf",
        help="Font file for captions",
    )
    args = parser.parse_args()

    with open(args.image_story, "r", encoding="utf-8") as f:
        image_story = ImageStory(**json.load(f))

    print(f"Loaded image story: {len(image_story.images)} images")
    print(f"  intro ends at {image_story.introduction_end_time}s")
    print(f"  CTA starts at {image_story.call_to_action_start_time}s")

    main_config = MainConfig.from_yaml("config.yaml")
    video_config = main_config.services.video_config
    img_width = video_config.width
    img_height = video_config.height

    image_proxy = MockImageGeneratorProxy()
    generated_images = []
    for i, img_def in enumerate(image_story.images):
        print(f"  Generating image {i + 1}/{len(image_story.images)}: {img_def.description[:60]}...")
        result = image_proxy.generate_image(
            prompt=img_def.prompt, width=img_width, height=img_height, num_images=1
        )
        generated_images.append(result[0])
    print(f"Generated {len(generated_images)} images")

    audio = AudioClip(file_path=args.audio)
    print(f"Audio duration: {audio.clip.duration:.2f}s")

    cover = ImageClip(file_path=args.cover) if args.cover else None

    captions_clip = None
    if args.captions and os.path.exists(args.font_path):
        captions_clip = load_captions(args.captions, args.font_path)
        print(f"Loaded {len(captions_clip.captions.segments)} caption segments")

    youtube_proxy_stub = _StubYouTubeProxy()
    video_service = VideoService(
        youtube_proxy=youtube_proxy_stub, video_config=video_config
    )

    print("Composing video...")
    final_video = video_service.generate_image_story_video(
        audio=audio,
        image_story=image_story,
        generated_images=generated_images,
        cover=cover,
        captions=captions_clip,
        low_quality=args.low_quality,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    print(f"Writing video to {args.output}...")
    final_video.clip.write_videofile(
        args.output, fps=24, ffmpeg_params=video_config.ffmpeg_params
    )
    print(f"Done! Video saved to {args.output}")


class _StubYouTubeProxy:
    """Stub — the image-story flow doesn't use YouTube backgrounds."""

    async def list_video_ids(self, url):
        return []

    async def download_video(self, video_id, low_quality=False):
        return b""


if __name__ == "__main__":
    asyncio.run(main())
