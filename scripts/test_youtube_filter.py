"""Download a random video from the configured YouTube channel and apply filters.

Usage:
  python scripts/test_youtube_filter.py
"""
import random
import asyncio

from pytubefix import Channel
from src.entities.editor.video_clip import VideoClip
from src.entities.configs.services.video import AntiFingerprintConfig

CHANNEL_URL = "https://www.youtube.com/@FoodieBoyKR"
DURATION = 10

config = AntiFingerprintConfig(
    enabled=True, mirror=True, zoom=1.04,
    brightness_delta=0.02, contrast_delta=0,
    hue_shift_degrees=0, speed_delta=0.02,
)

print(f"Fetching video list from {CHANNEL_URL}...")
channel = Channel(CHANNEL_URL)
urls = list(channel.video_urls)
print(f"Found {len(urls)} videos")

from pytubefix import YouTube
import tempfile

vid = random.choice(urls)
vid_url = vid if isinstance(vid, str) else vid.watch_url if hasattr(vid, 'watch_url') else str(vid)
print(f"Downloading: {vid_url}")

yt = YouTube(vid_url)
stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
if not stream:
    stream = yt.streams.filter(file_extension="mp4").order_by("resolution").desc().first()

with tempfile.TemporaryDirectory() as td:
    path = stream.download(output_path=td)
    with open(path, "rb") as f:
        video_bytes = f.read()

print(f"Downloaded {len(video_bytes) / 1024 / 1024:.1f} MB")

import tempfile as tf
with tf.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
    tmp.write(video_bytes)
    tmp_path = tmp.name

vc_orig = VideoClip(file_path=tmp_path)
start = random.uniform(0, max(0, vc_orig.clip.duration - DURATION))
orig_clip = vc_orig.clip.subclipped(start, start + DURATION)
orig_clip.write_videofile("output/yt_original.mp4", codec="libx264", preset="fast", logger=None)
print(f"Wrote output/yt_original.mp4 (original {start:.1f}s-{start+DURATION:.1f}s)")

vc = VideoClip(file_path=tmp_path)
vc.clip = vc.clip.subclipped(start, start + DURATION)
vc.apply_anti_fingerprint(config)
vc.clip.write_videofile("output/yt_filtered.mp4", codec="libx264", preset="fast", logger=None)
print(f"Wrote output/yt_filtered.mp4 (filtered)")

import os
os.unlink(tmp_path)
