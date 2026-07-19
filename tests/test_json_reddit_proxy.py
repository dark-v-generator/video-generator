import pytest

from src.entities.configs.proxies.reddit import JsonRedditConfig
from src.proxies.json_reddit_proxy import JsonRedditProxy


class FakeTokenResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "access_token": "token-1",
            "expires_in": 3600,
            "token_type": "bearer",
        }


class FakeListingResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": {"children": [], "after": None}}


class FakeJsonResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def _post_data(
    *,
    title="A real story",
    selftext="I had a long story to tell.",
    permalink="/r/test/comments/abc/a_real_story/",
    removed_by_category=None,
):
    data = {
        "title": title,
        "selftext": selftext,
        "subreddit_name_prefixed": "r/test",
        "author": "author",
        "permalink": permalink,
    }
    if removed_by_category is not None:
        data["removed_by_category"] = removed_by_category
    return data


def _listing(children):
    return FakeJsonResponse(
        {
            "data": {
                "children": [{"kind": "t3", "data": child} for child in children],
                "after": None,
            }
        }
    )


def test_list_subreddit_posts_uses_oauth_endpoint_and_normalizes_prefix(
    monkeypatch,
):
    token_calls = []
    listing_calls = []

    def fake_post(url, *, auth, data, headers, timeout):
        token_calls.append((url, data, headers))
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        listing_calls.append((url, headers, params))
        return FakeListingResponse()

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
        user_agent="video-generator-test",
    )
    proxy.list_subreddit_posts(subreddit="r/relacionamentos/")

    assert token_calls == [
        (
            "https://www.reddit.com/api/v1/access_token",
            {"grant_type": "client_credentials"},
            {"User-Agent": "video-generator-test"},
        )
    ]
    assert listing_calls == [
        (
            "https://oauth.reddit.com/r/relacionamentos/top.json",
            {
                "Authorization": "Bearer token-1",
                "User-Agent": "video-generator-test",
            },
            {"limit": 50, "raw_json": 1, "t": "day"},
        )
    ]


def test_list_subreddit_posts_reuses_cached_oauth_token(monkeypatch):
    token_call_count = 0

    def fake_post(url, *, auth, data, headers, timeout):
        nonlocal token_call_count
        token_call_count += 1
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        return FakeListingResponse()

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
        user_agent="video-generator-test",
    )
    proxy.list_subreddit_posts(subreddit="AmItheAsshole")
    proxy.list_subreddit_posts(subreddit="TrueOffMyChest")

    assert token_call_count == 1


def test_missing_oauth_credentials_raises_clear_error():
    proxy = JsonRedditProxy(config=JsonRedditConfig())

    try:
        proxy.list_subreddit_posts(subreddit="AmItheAsshole")
    except RuntimeError as exc:
        assert "REDDIT_CLIENT_ID" in str(exc)
        assert "REDDIT_CLIENT_SECRET" in str(exc)
    else:
        raise AssertionError("Expected missing Reddit credentials to fail")


def test_list_subreddit_posts_skips_unavailable_and_removed_posts(monkeypatch):
    def fake_post(url, *, auth, data, headers, timeout):
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        return _listing(
            [
                _post_data(title="This post is unavailable", selftext="unavailable"),
                _post_data(
                    title="Removed post",
                    selftext="This post has been removed.",
                    removed_by_category="moderator",
                ),
                _post_data(title="Valid story", selftext="I have a real story."),
            ]
        )

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
    )

    posts = proxy.list_subreddit_posts(subreddit="test")

    assert [post.title for post in posts] == ["Valid story"]


def test_list_subreddit_posts_keeps_normal_unavailable_word_usage(monkeypatch):
    def fake_post(url, *, auth, data, headers, timeout):
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        return _listing(
            [
                _post_data(
                    title="I was unavailable last night",
                    selftext="I was unavailable because my phone died.",
                ),
            ]
        )

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
    )

    posts = proxy.list_subreddit_posts(subreddit="test")

    assert [post.title for post in posts] == ["I was unavailable last night"]


def test_get_reddit_post_rejects_unavailable_post(monkeypatch):
    def fake_post(url, *, auth, data, headers, timeout):
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        return FakeJsonResponse(
            [
                {
                    "data": {
                        "children": [
                            {
                                "data": _post_data(
                                    title="This post is unavailable",
                                    selftext="[removed]",
                                )
                            }
                        ]
                    }
                }
            ]
        )

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
    )

    with pytest.raises(ValueError, match="unavailable or removed"):
        proxy.get_reddit_post("https://www.reddit.com/r/test/comments/abc/title/")


def test_get_reddit_post_rejects_removed_post_flag(monkeypatch):
    def fake_post(url, *, auth, data, headers, timeout):
        return FakeTokenResponse()

    def fake_get(url, *, headers, params, timeout):
        return FakeJsonResponse(
            [
                {
                    "data": {
                        "children": [
                            {
                                "data": _post_data(
                                    title="A removed post",
                                    selftext="Text that should not be processed.",
                                    removed_by_category="moderator",
                                )
                            }
                        ]
                    }
                }
            ]
        )

    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.post", fake_post)
    monkeypatch.setattr("src.proxies.json_reddit_proxy.requests.get", fake_get)

    proxy = JsonRedditProxy(
        config=JsonRedditConfig(),
        client_id="client-id",
        client_secret="client-secret",
    )

    with pytest.raises(ValueError, match="unavailable or removed"):
        proxy.get_reddit_post("https://www.reddit.com/r/test/comments/abc/title/")
