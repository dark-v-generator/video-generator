"""Render a hand-written story over a folder of .mp4 clips into output/render/.

Only a ``Story`` and ``container.renderer()``: the footage comes from the folder,
everything else from the config at CONFIG_PATH. story.json: {"title", "parts":
[text, ...], "narrator_gender", "language", "origin": {StoryOrigin fields}}.
Usage: uv run python scripts/render_story.py story.json /path/to/clips
"""

import asyncio
import json
import os
import sys

from dependency_injector import providers

from src.core.container import container
from src.entities.language import Language
from src.entities.story import Story, StoryOrigin, StoryPart

OUTPUT_DIR = "output/render"


def load_story(path: str) -> Story:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    gender = data.get("narrator_gender", "unknown")
    return Story(
        title=data["title"],
        parts=[StoryPart(index=i, text=t) for i, t in enumerate(data["parts"], 1)],
        narrator_gender=gender,
        resolved_gender=gender if gender in ("male", "female") else "male",
        language=Language(data["language"]),
        summary=data.get("summary", ""),
        origin=StoryOrigin(**data["origin"]),
    )


async def main(story_path: str, footage_dir: str) -> None:
    config = container.main_config()
    video = config.services.video_config.model_copy(
        update={"footage_source": "local", "local_footage_dir": footage_dir}
    )
    services = config.services.model_copy(update={"video_config": video})
    container.main_config.override(
        providers.Object(config.model_copy(update={"services": services}))
    )

    parts = await container.renderer().render(load_story(story_path))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for part in parts:
        path = os.path.join(OUTPUT_DIR, f"part{part.part.index}.mp4")
        with open(path, "wb") as f:
            f.write(part.video)
        print(path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
