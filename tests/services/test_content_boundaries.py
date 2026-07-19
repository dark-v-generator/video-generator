"""Tests for RedditVideoService._compute_content_boundaries after the repair.

The title and "Parte N." marker are no longer narrated, so:
- the first spoken word must NOT be dropped;
- the cover-overlay window (intro_end) comes from video_config.cover_duration.
A leading "Parte N." marker is still detected for backward compatibility.
"""

from types import SimpleNamespace

from src.entities.configs.services.video import VideoConfig
from src.services.reddit_video_service import RedditVideoService


def _svc(cover_duration=3):
    svc = RedditVideoService.__new__(RedditVideoService)
    svc._video_service = SimpleNamespace(
        _video_config=VideoConfig(cover_duration=cover_duration)
    )
    return svc


def _words(texts, start=0.0, step=0.4):
    out = []
    t = start
    for w in texts:
        out.append({"word": w, "start": round(t, 3), "end": round(t + step, 3)})
        t += step
    return out


def test_keeps_first_word_when_no_marker():
    svc = _svc(cover_duration=3)
    words = _words(
        ["Morava", "com", "o", "Marcos", "e", "ele", "pegava", "minhas",
         "coisas", "emprestadas", "sempre", "assim", "curta", "e", "siga"]
    )
    intro, cta, offset, content = svc._compute_content_boundaries(words)

    assert content[0]["word"] == "Morava"          # first word NOT dropped
    assert intro == 3.0                            # cover window == cover_duration
    assert offset == words[0]["start"]
    assert content[0]["start"] == 0.0              # zero-based
    # CTA ("curta") is excluded from content
    assert all(w["word"] != "curta" for w in content)


def test_cover_window_follows_config():
    svc = _svc(cover_duration=5)
    _, _, _, _ = svc._compute_content_boundaries(_words(["a", "b", "c", "d", "e", "f", "g"]))
    intro, *_ = svc._compute_content_boundaries(_words(["a", "b", "c", "d", "e", "f", "g"]))
    assert intro == 5.0


def test_legacy_marker_is_still_stripped():
    svc = _svc(cover_duration=3)
    words = (
        _words(["Titulo", "antigo", "Parte", "1."])
        + _words(["Era", "uma", "vez", "uma", "historia", "boa", "curta", "fim"], start=2.0)
    )
    intro, cta, offset, content = svc._compute_content_boundaries(words)

    assert content[0]["word"] == "Era"             # everything up to "1." stripped
    assert intro == words[3]["end"]                # end of the "1." marker
