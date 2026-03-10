import random
import os
import sys
import logging

# Ensure project root is in path if run from subdirectory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.container import container

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    channel_url = "https://www.youtube.com/@OddlySatisfying"

    logger.info("Initializing youtube proxy from container...")
    proxy = container.youtube_proxy()

    logger.info(f"Fetching video IDs from {channel_url}...")
    video_ids = proxy.list_video_ids(channel_url)

    if not video_ids:
        logger.error("No video IDs could be found from the channel.")
        return

    logger.info(f"Successfully retrieved {len(video_ids)} video IDs.")

    # Pick a random video ID
    chosen_id = random.choice(video_ids)
    logger.info(f"Selected random video ID: {chosen_id}")

    # Download the video
    logger.info(f"Downloading video {chosen_id}... This might take a moment.")
    video_bytes = proxy.download_video(chosen_id)

    # Save the file
    output_dir = os.path.join("tests", "data")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{chosen_id}.mp4")

    logger.info(f"Saving downloaded stream to {output_path}...")
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    logger.info(f"Done! Saved {len(video_bytes)} bytes.")


if __name__ == "__main__":
    main()
