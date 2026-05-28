from src.entities.configs.proxies.youtube import PyTubeYouTubeConfig
from src.proxies import pytube_proxy
from src.proxies.pytube_proxy import PyTubeProxy


class FakeChannel:
    video_urls = [[], []]
    videos_url = "https://www.youtube.com/@FoodieBoyKR/videos"
    shorts_url = "https://www.youtube.com/@FoodieBoyKR/shorts"
    html_url = videos_url
    shorts = [
        type("FakeShort", (), {"video_id": "short123abc"})(),
        type("FakeShort", (), {"video_id": "short456def"})(),
    ]
    initial_data = {
        "contents": [
            {"videoRenderer": {"videoId": "abc123def45"}},
            {
                "richItemRenderer": {
                    "content": {"videoRenderer": {"videoId": "xyz987uvw65"}}
                }
            },
            {"videoRenderer": {"videoId": "abc123def45"}},
        ]
    }

    def __init__(self, url):
        self.url = url


def test_channel_extraction_falls_back_to_initial_data(monkeypatch):
    monkeypatch.setattr(pytube_proxy, "Channel", FakeChannel)

    proxy = PyTubeProxy(PyTubeYouTubeConfig())

    assert proxy._extract_video_ids("https://www.youtube.com/@FoodieBoyKR") == [
        "abc123def45",
        "xyz987uvw65",
    ]


def test_channel_extraction_can_list_shorts_only(monkeypatch):
    monkeypatch.setattr(pytube_proxy, "Channel", FakeChannel)

    proxy = PyTubeProxy(PyTubeYouTubeConfig())

    assert proxy._extract_video_ids(
        "https://www.youtube.com/@FoodieBoyKR",
        surface="shorts",
    ) == [
        "short123abc",
        "short456def",
    ]
