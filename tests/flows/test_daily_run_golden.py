"""Golden record of the daily run's observable behaviour in its three modes.

Recorded once from the code as it stood before the capabilities were pulled
out (feature 004, M1). Every later milestone must reproduce it unchanged: the
same candidates and the same fake answers have to yield the same progress
messages, manifests, publish-log rows and publisher calls. A diff here is a
behaviour change, not progress; ``--update-golden`` rewrites the fixture and
the diff is reviewed in the PR.

Scenario: six posts over two subreddits, one of them already scheduled in the
publish log. Of the five candidates left, the 2nd hits a transient model error
once, the 3rd is blocked by the content filter, and the first publish attempt
fails. The target is three stories.
"""

import csv
import datetime as real_datetime
import json
import os
import types

import pytest
from dependency_injector import providers

from bots import satisfying_bot
from src.core.container import ApplicationContainer
from src.entities.config import EvaluationConfig, MainConfig
from src.entities.configs.bots import BotsConfig, TelegramBotConfig
from src.entities.reddit_post import RedditPost
from tests.fakes.proxies import (
    FakeCoverProxy,
    FakeLLMProxy,
    FakeRedditProxy,
    FakeSpeechProxy,
    FakeTranscriptionProxy,
)
from tests.fakes.publisher import FakePublisher
from tests.fakes.video import FakeComposer, FakeFootageSource

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "fixtures", "daily_run_golden.json"
)

NOW = real_datetime.datetime(2026, 9, 25, 10, 0)

SUBREDDITS = ["contos", "desabafos"]


def _post(sub: str, n: int, title: str) -> RedditPost:
    return RedditPost(
        title=title,
        content=(
            f"Eu nunca contei isso pra ninguém, parte {n}. "
            "Minha vizinha fez uma coisa e eu reagi. "
            '"Você viu?", ela perguntou. Eu disse que sim.\n\n'
            "No fim, todo mundo ficou sabendo."
        ),
        community=f"r/{sub}",
        author=f"autor{n}",
        community_url_photo=f"https://example.com/{sub}.png",
        url=f"https://www.reddit.com/r/{sub}/comments/p{n}/",
        score=100 * n,
        num_comments=10 * n,
        upvote_ratio=0.9,
    )


POSTS = {
    "contos": [
        _post("contos", 1, "A vizinha e o bolo"),
        _post("contos", 2, "O chefe e a planilha"),
        _post("contos", 3, "O primo e o carro"),
    ],
    "desabafos": [
        _post("desabafos", 4, "A sogra e o almoço"),
        _post("desabafos", 5, "O síndico e a garagem"),
        _post("desabafos", 6, "Já publicada antes"),
    ],
}

# Discovery orders candidates by these grades: this is the candidate order.
GRADES = {
    "A vizinha e o bolo": 95.0,
    "O chefe e a planilha": 90.0,
    "O primo e o carro": 85.0,
    "A sogra e o almoço": 80.0,
    "O síndico e a garagem": 75.0,
    "Já publicada antes": 99.0,
}

STORY_ERRORS = {
    "O chefe e a planilha": [RuntimeError("429 Too Many Requests: rate limit")],
    "O primo e o carro": [RuntimeError("Response blocked by content filter")],
}

ALREADY_SCHEDULED = POSTS["desabafos"][2].url

LOG_FIELDS = [
    "created_at",
    "status",
    "scheduled_at",
    "video_path",
    "title",
    "post_url",
    "hashtags",
    "publish_result",
    "error",
]


class _FrozenDateTime(real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def _main_config() -> MainConfig:
    return MainConfig(
        language="pt-br",
        evaluation=EvaluationConfig(subreddits=SUBREDDITS),
        bots=BotsConfig(
            satisfying_bot=TelegramBotConfig(
                allowed_user_ids=[1],
                low_quality=True,
                daily_auto_publish_count=3,
                publish_slots_local=["12:00", "18:00", "20:00"],
                publish_min_lead_minutes=30,
                publish_hashtags=["fyp"],
            )
        ),
    )


class _Run:
    """One mode's worth of fakes, wired into the real container and the bot."""

    def __init__(self, monkeypatch, tmp_path, *, publish_fail_on=frozenset()):
        self.tmp_path = tmp_path
        os.makedirs(tmp_path, exist_ok=True)
        self.output_dir = str(tmp_path / "daily")
        self.log_path = tmp_path / "tiktok_publish_log.csv"
        self.messages: list[str] = []
        self.publisher = FakePublisher(fail_on=set(publish_fail_on))

        config = _main_config()
        container = ApplicationContainer()
        container.main_config.override(providers.Object(config))
        container.reddit_proxy.override(providers.Object(FakeRedditProxy(POSTS)))
        container.llm_proxy.override(
            providers.Object(FakeLLMProxy(grades=GRADES, story_errors=STORY_ERRORS))
        )
        container.speech_proxy.override(providers.Object(FakeSpeechProxy()))
        container.transcription_proxy.override(
            providers.Object(FakeTranscriptionProxy())
        )
        container.cover_proxy.override(providers.Object(FakeCoverProxy()))
        container.footage_source.override(providers.Object(FakeFootageSource()))
        container.video_composer.override(providers.Object(FakeComposer()))

        async def no_sleep(delay):
            return None

        monkeypatch.setattr(satisfying_bot, "container", container)
        monkeypatch.setattr(satisfying_bot, "config", config)
        monkeypatch.setattr(satisfying_bot, "bot_config", config.bots.satisfying_bot)
        monkeypatch.setattr(
            satisfying_bot, "_build_tiktok_publisher", lambda: self.publisher
        )
        monkeypatch.setattr(satisfying_bot.asyncio, "sleep", no_sleep)
        monkeypatch.setattr(
            satisfying_bot,
            "datetime",
            types.SimpleNamespace(
                datetime=_FrozenDateTime,
                date=real_datetime.date,
                time=real_datetime.time,
                timedelta=real_datetime.timedelta,
                timezone=real_datetime.timezone,
            ),
        )
        monkeypatch.setenv("TIKTOK_PUBLISH_LOG_PATH", str(self.log_path))

    async def send_message(self, text: str) -> None:
        self.messages.append(text)

    def seed_publish_log(self) -> None:
        with open(self.log_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "created_at": "2026-09-24T10:00:00",
                    "status": "scheduled",
                    "scheduled_at": "2026-09-24T18:00",
                    "video_path": "old/story_01.mp4",
                    "title": "Já publicada antes",
                    "post_url": ALREADY_SCHEDULED,
                    "hashtags": "#fyp",
                    "publish_result": "ok",
                    "error": "",
                }
            )

    def _relative(self, path: str) -> str:
        return os.path.relpath(path, self.tmp_path)

    def record(self) -> dict:
        manifests = []
        if os.path.isdir(self.output_dir):
            for name in sorted(os.listdir(self.output_dir)):
                if not name.endswith(".json"):
                    continue
                with open(os.path.join(self.output_dir, name)) as f:
                    manifest = json.load(f)
                manifest["video_path"] = self._relative(manifest["video_path"])
                manifests.append({"file": name, **manifest})

        rows = []
        if self.log_path.exists():
            with open(self.log_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    row.pop("created_at")
                    if row["video_path"].startswith(str(self.tmp_path)):
                        row["video_path"] = self._relative(row["video_path"])
                    rows.append(row)

        calls = [
            {
                "video_path": self._relative(call.video_path),
                "description": call.description,
                "hashtags": call.hashtags,
                "schedule_at": (
                    call.schedule_at.isoformat(timespec="minutes")
                    if call.schedule_at
                    else None
                ),
            }
            for call in self.publisher.calls
        ]

        return {
            "messages": self.messages,
            "manifests": manifests,
            "publish_log_rows": rows,
            "publisher_calls": calls,
        }


async def _auto_publish(monkeypatch, tmp_path) -> dict:
    run = _Run(monkeypatch, tmp_path / "auto", publish_fail_on={1})
    run.seed_publish_log()
    await satisfying_bot.run_daily_auto_publish(
        run.send_message, output_dir=run.output_dir
    )
    return run.record()


async def _generate(monkeypatch, tmp_path) -> dict:
    run = _Run(monkeypatch, tmp_path / "generate")
    run.seed_publish_log()
    await satisfying_bot.run_daily_generate(run.send_message, output_dir=run.output_dir)
    return run.record()


async def _publish(monkeypatch, tmp_path) -> dict:
    # The input is what generate-only leaves behind for the same scenario. The
    # publish run then starts from an empty log, so its rows are only its own.
    source = _Run(monkeypatch, tmp_path / "publish")
    source.seed_publish_log()
    await satisfying_bot.run_daily_generate(
        source.send_message, output_dir=source.output_dir
    )
    os.remove(source.log_path)

    run = _Run(monkeypatch, tmp_path / "publish", publish_fail_on={1})
    videos = satisfying_bot.load_generated_videos(run.output_dir)
    await satisfying_bot.run_daily_publish(run.send_message, videos)
    return run.record()


@pytest.mark.asyncio
async def test_daily_run_matches_the_golden_record(
    monkeypatch, tmp_path, update_golden
):
    observed = {
        "auto_publish": await _auto_publish(monkeypatch, tmp_path),
        "generate": await _generate(monkeypatch, tmp_path),
        "publish": await _publish(monkeypatch, tmp_path),
    }

    if update_golden:
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(observed, f, ensure_ascii=False, indent=2)
            f.write("\n")

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    for mode in ("auto_publish", "generate", "publish"):
        for key in ("messages", "manifests", "publish_log_rows", "publisher_calls"):
            assert observed[mode][key] == golden[mode][key], f"{mode}.{key}"
