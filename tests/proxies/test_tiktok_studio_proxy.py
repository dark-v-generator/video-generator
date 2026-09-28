"""The Studio reader over responses recorded on the server, without a browser.

tests/fixtures/tiktok_studio_probe.json is a redacted dump of
scripts/tiktok_studio_probe.py: two pages of the content list (the first page
and a later one) and the analytics insight that carries the retention.
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.entities.history import PerformanceMetrics
from src.proxies.interfaces import TikTokSessionExpiredError, TikTokStudioLayoutError
from src.proxies.tiktok_studio_proxy import (
    INSIGHT_PATH,
    ITEM_LIST_PATH,
    PatchrightTikTokStudioProxy,
    _parse_analytics,
    _parse_video_list,
    _retention_response,
    _videos_since,
    raise_if_logged_out,
)

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "tiktok_studio_probe.json").read_text(
        encoding="utf-8"
    )
)
LOGIN_URL = (
    "https://www.tiktok.com/login?redirect_url=https%3A%2F%2Fwww.tiktok.com"
    "%2Ftiktokstudio%2Fcontent&enter_method=redirect&enter_from=tiktokstudio"
)


def first_page() -> dict:
    return copy.deepcopy(FIXTURE["item_list_pages"][0]["body"])


def later_page() -> dict:
    return copy.deepcopy(FIXTURE["item_list_pages"][1]["body"])


def insight() -> dict:
    return copy.deepcopy(FIXTURE["insight"]["body"])


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_the_fixture_was_recorded_from_the_endpoints_the_reader_listens_to():
    assert {page["path"] for page in FIXTURE["item_list_pages"]} == {ITEM_LIST_PATH}
    assert FIXTURE["insight"]["path"] == INSIGHT_PATH


def test_a_list_page_gives_each_post_with_its_counts():
    videos = _parse_video_list(first_page())

    assert len(videos) == 4
    newest = videos[0]
    assert newest.video_id == "7000000000000000002"
    assert newest.description.startswith("Acordei com um estranho bêbado")
    assert newest.description.endswith("#reddit")
    # The post time, which for a scheduled post is its slot (18:00 in São Paulo).
    assert newest.created_at == utc(2026, 9, 28, 15, 0)
    assert newest.metrics == PerformanceMetrics(
        views=287, likes=28, comments=0, shares=0, saves=4
    )


def test_the_analytics_give_the_counts_and_the_retention():
    assert _parse_analytics(insight()) == PerformanceMetrics(
        views=2147,
        likes=217,
        comments=1,
        shares=0,
        saves=10,
        avg_watch_seconds=38.78,
        full_watch_ratio=0.0683,
    )


def test_retention_the_studio_has_not_computed_yet_is_none():
    body = insight()
    body["video_finish_rate_realtime"]["value"] = {"status": 2}
    body["video_per_duration_realtime"]["value"] = {"status": 2, "value": None}

    metrics = _parse_analytics(body)

    assert metrics.full_watch_ratio is None
    assert metrics.avg_watch_seconds is None
    assert metrics.views == 2147


def test_a_list_post_without_its_view_count_fails_naming_the_field():
    body = first_page()
    del body["item_list"][1]["play_count"]

    with pytest.raises(TikTokStudioLayoutError, match="play_count.*item_list"):
        _parse_video_list(body)


def test_analytics_without_the_statistics_fail_naming_the_field():
    body = insight()
    del body["video_info"]["statistics"]

    with pytest.raises(TikTokStudioLayoutError, match="video_info.statistics"):
        _parse_analytics(body)


def test_analytics_without_a_retention_insight_fail_naming_it():
    body = insight()
    del body["video_per_duration_realtime"]

    with pytest.raises(TikTokStudioLayoutError, match="video_per_duration_realtime"):
        _parse_analytics(body)


def test_an_error_answer_fails_with_the_studios_message():
    body = {"status_code": 8, "status_msg": "Login expired"}

    with pytest.raises(TikTokStudioLayoutError, match="status_code 8: Login expired"):
        _parse_video_list(body)


def test_pages_that_do_not_reach_back_to_since_ask_for_more():
    videos, covered, loaded = _videos_since(
        [first_page(), later_page()], utc(2026, 8, 1)
    )

    assert not covered
    assert loaded == 6
    assert [video.created_at for video in videos] == sorted(
        (video.created_at for video in videos), reverse=True
    )


def test_a_post_older_than_since_ends_the_list_and_is_left_out():
    videos, covered, _ = _videos_since([first_page(), later_page()], utc(2026, 9, 10))

    assert covered
    assert [video.video_id for video in videos] == [
        "7000000000000000002",
        "7000000000000000003",
        "7000000000000000004",
        "7000000000000000005",
    ]


def test_the_last_page_ends_the_list():
    last = first_page()
    last["has_more"] = False

    _, covered, _ = _videos_since([last], utc(2026, 1, 1))

    assert covered


def test_an_old_pinned_post_does_not_end_the_list():
    page = first_page()
    old = later_page()["item_list"][0]
    old["is_pinned"] = True
    page["item_list"].insert(0, old)

    videos, covered, _ = _videos_since([page], utc(2026, 9, 27))

    assert not covered
    assert old["item_id"] not in [video.video_id for video in videos]


def test_a_refetched_first_page_keeps_the_latest_numbers():
    refetched = first_page()
    refetched["item_list"][0]["play_count"] = "288"

    videos, _, loaded = _videos_since([first_page(), refetched], utc(2026, 9, 1))

    assert loaded == 4
    assert videos[0].metrics.views == 288


def test_only_the_insight_with_this_videos_retention_is_read():
    without_retention = insight()
    without_retention["video_finish_rate_realtime"] = None
    other_video = insight()
    other_video["video_info"]["aweme_id"] = "7000000000000000999"
    rewards = {"status_code": 0, "video_rewards_data": {"status": 100}}
    bodies = [rewards, without_retention, other_video]

    assert _retention_response(bodies, "7000000000000000001") is None
    assert _retention_response([*bodies, insight()], "7000000000000000001") == (
        insight()
    )


def test_the_login_page_means_the_session_expired():
    with pytest.raises(TikTokSessionExpiredError, match="prod-tiktok-bootstrap"):
        raise_if_logged_out(SimpleNamespace(url=LOGIN_URL))

    raise_if_logged_out(
        SimpleNamespace(url="https://www.tiktok.com/tiktokstudio/content")
    )


class FakeStudioPage:
    """Delivers recorded bodies to the proxy as the real page would: some on
    navigation, some on each scroll."""

    def __init__(self, proxy, on_goto, on_scroll=(), url=None):
        self.proxy = proxy
        self.on_goto = on_goto
        self.on_scroll = list(on_scroll)
        self.url = url or "https://www.tiktok.com/tiktokstudio/content"
        self.mouse = SimpleNamespace(move=self._noop, wheel=self._wheel)
        self.visited = []

    async def goto(self, url, **_):
        self.visited.append(url)
        for path, body in self.on_goto:
            self.proxy._bodies[path].append(body)

    async def evaluate(self, _):
        return [1920, 1080]

    async def _noop(self, *_):
        return None

    async def _wheel(self, *_):
        if self.on_scroll:
            path, body = self.on_scroll.pop(0)
            self.proxy._bodies[path].append(body)


def studio(page_factory, timeout=1) -> PatchrightTikTokStudioProxy:
    proxy = PatchrightTikTokStudioProxy(Path("/unused"), page_timeout_seconds=timeout)
    page = page_factory(proxy)

    async def opened():
        proxy._page = page
        return page

    proxy._open = opened
    return proxy


@pytest.mark.asyncio
async def test_the_list_scrolls_until_it_reaches_since():
    proxy = studio(
        lambda proxy: FakeStudioPage(
            proxy,
            on_goto=[(ITEM_LIST_PATH, first_page())],
            on_scroll=[(ITEM_LIST_PATH, later_page())],
        )
    )

    # The later page has posts at 23:00 and 21:00 UTC on 09-06.
    videos = await proxy.list_videos(since=utc(2026, 9, 6, 22, 0))

    assert len(videos) == 5
    assert videos[-1].video_id == "7000000000000000006"
    assert videos[-1].created_at == utc(2026, 9, 6, 23, 0)
    assert proxy._page.on_scroll == []


@pytest.mark.asyncio
async def test_a_list_that_stops_loading_fails_instead_of_returning_part_of_it():
    proxy = studio(
        lambda proxy: FakeStudioPage(
            proxy,
            on_goto=[(ITEM_LIST_PATH, first_page())],
            on_scroll=[(ITEM_LIST_PATH, first_page())] * 5,
        )
    )

    with pytest.raises(TikTokStudioLayoutError, match="loaded no older post"):
        await proxy.list_videos(since=utc(2026, 1, 1))


@pytest.mark.asyncio
async def test_a_logged_out_profile_fails_as_an_expired_session():
    proxy = studio(lambda proxy: FakeStudioPage(proxy, on_goto=[], url=LOGIN_URL))

    with pytest.raises(TikTokSessionExpiredError):
        await proxy.list_videos(since=utc(2026, 9, 1))


@pytest.mark.asyncio
async def test_analytics_wait_for_the_insight_with_the_retention():
    rewards = {"status_code": 0, "video_rewards_data": {"status": 100}}
    proxy = studio(
        lambda proxy: FakeStudioPage(
            proxy, on_goto=[(INSIGHT_PATH, rewards), (INSIGHT_PATH, insight())]
        )
    )

    metrics = await proxy.video_analytics("7000000000000000001")

    assert metrics.full_watch_ratio == 0.0683
    assert proxy._page.visited == [
        "https://www.tiktok.com/tiktokstudio/analytics/7000000000000000001"
    ]


@pytest.mark.asyncio
async def test_analytics_that_never_bring_the_retention_fail_naming_the_video():
    rewards = {"status_code": 0, "video_rewards_data": {"status": 100}}
    proxy = studio(
        lambda proxy: FakeStudioPage(proxy, on_goto=[(INSIGHT_PATH, rewards)])
    )

    with pytest.raises(
        TikTokStudioLayoutError, match="retention of video 7000000000000000001"
    ):
        await proxy.video_analytics("7000000000000000001")
