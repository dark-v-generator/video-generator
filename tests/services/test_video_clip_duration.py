from moviepy import ColorClip

from src.entities.editor.video_clip import VideoClip


def _clip_with_duration(seconds: float) -> VideoClip:
    video = VideoClip()
    video.clip = ColorClip(size=(64, 64), color=(0, 0, 0), duration=seconds)
    return video


def test_ajust_duration_trims_after_looping():
    # Regression: when the background is shorter than the audio, looping used
    # to double the clip without trimming, leaving a long mute tail where the
    # background keeps playing after the narration ends.
    video = _clip_with_duration(10.0)
    video.ajust_duration(10.5)
    assert video.clip.duration == 10.5


def test_ajust_duration_trims_longer_background():
    video = _clip_with_duration(10.0)
    video.ajust_duration(4.0)
    assert video.clip.duration == 4.0


def test_ajust_duration_keeps_exact_match():
    video = _clip_with_duration(10.0)
    video.ajust_duration(10.0)
    assert video.clip.duration == 10.0
