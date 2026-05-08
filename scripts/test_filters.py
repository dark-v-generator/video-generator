"""Generate a 10s side-by-side comparison of anti-fingerprint filters.

Outputs:
  output/filter_original.mp4  – untouched 10s clip
  output/filter_applied.mp4   – same clip with anti-fingerprint effects

Usage:
  python scripts/test_filters.py [source.mp4]
"""
import sys
import random

from moviepy import VideoFileClip
from src.entities.editor.video_clip import VideoClip
from src.entities.configs.services.video import AntiFingerprintConfig

SOURCE = sys.argv[1] if len(sys.argv) > 1 else "output/part1.mp4"
DURATION = 10

clip = VideoFileClip(SOURCE)

start = random.uniform(0, max(0, clip.duration - DURATION))
segment = clip.subclipped(start, start + DURATION)
segment.write_videofile("output/filter_original.mp4", codec="libx264", preset="fast", logger=None)
print(f"Wrote output/filter_original.mp4 (original, {start:.1f}s–{start+DURATION:.1f}s)")

vc = VideoClip(file_path=SOURCE)
vc.clip = vc.clip.subclipped(start, start + DURATION)

config = AntiFingerprintConfig(
    enabled=True, mirror=True, zoom=1.04,
    brightness_delta=0.02, contrast_delta=0,
    hue_shift_degrees=0, speed_delta=0.02,
)
vc = VideoClip(file_path=SOURCE)
vc.clip = vc.clip.subclipped(start, start + DURATION)
vc.apply_anti_fingerprint(config)
vc.clip.write_videofile("output/filter_new.mp4", codec="libx264", preset="fast", logger=None)
print(f"Wrote output/filter_new.mp4 — mirror + zoom={config.zoom} + "
      f"brightness={config.brightness_delta} + speed={config.speed_delta} (no hue/contrast)")
