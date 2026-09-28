"""The bot and the command line are adapters: both call the same ``DailyRun``
and the same ``PerformanceCollection``.

Recording flows stand in for the real ones; each call is bound against the
real method's signature, so a call the real flow would reject fails here too,
and defaults are filled in before comparing.
"""

import asyncio
import inspect
import sys
from types import SimpleNamespace

import pytest

from bots import satisfying_bot
from scripts import collect_performance, daily_auto_publish
from src.entities.generated_video import GeneratedVideo
from src.flows.collect_performance import PerformanceCollection
from src.flows.daily_run import DailyRun
from src.flows.progress import RunLock


class RecordingDailyRun:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.progress = None
        self.hold: asyncio.Event | None = None

    def _record(self, name, *args, **kwargs):
        bound = inspect.signature(getattr(DailyRun, name)).bind(self, *args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        arguments.pop("self")
        self.calls.append((name, arguments))

    async def run(self, *args, **kwargs):
        self._record("run", *args, **kwargs)
        await self.progress("progresso do fluxo")
        if self.hold is not None:
            await self.hold.wait()

    async def generate(self, *args, **kwargs):
        self._record("generate", *args, **kwargs)
        await self.progress("progresso do fluxo")
        return []

    async def publish(self, *args, **kwargs):
        self._record("publish", *args, **kwargs)


class RecordingCollection:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.progress = None
        self.error: Exception | None = None

    def _record(self, name, *args, **kwargs):
        bound = inspect.signature(getattr(PerformanceCollection, name)).bind(
            self, *args, **kwargs
        )
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        arguments.pop("self")
        self.calls.append((name, arguments))

    async def collect(self, *args, **kwargs):
        self._record("collect", *args, **kwargs)
        await self.progress("progresso da coleta")
        if self.error is not None:
            raise self.error

    def assign(self, *args, **kwargs):
        self._record("assign", *args, **kwargs)


class FakeContainer:
    def __init__(self, manifests=None):
        self.flow = RecordingDailyRun()
        self.collection = RecordingCollection()
        self.builds: list[dict] = []
        self.loaded_from: list[str] = []
        self._manifests = manifests or []

    def daily_run(self, **kwargs):
        self.builds.append(kwargs)
        self.flow.progress = kwargs["progress"]
        return self.flow

    def performance_collection(self, **kwargs):
        self.collection.progress = kwargs["progress"]
        return self.collection

    def run_store(self):
        container = self

        class Store:
            def load_manifests(self, directory):
                container.loaded_from.append(directory)
                return container._manifests

        return Store()


# --------------------------------------------------------------------------
# Telegram bot
# --------------------------------------------------------------------------


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


def telegram(args=None, user_id=1, chat_id=500):
    replies = []

    async def reply_text(text):
        replies.append(text)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=chat_id),
        message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(args=args, bot=FakeBot())
    return update, context, replies


@pytest.fixture
def bot(monkeypatch):
    container = FakeContainer()
    monkeypatch.setattr(satisfying_bot, "container", container)
    monkeypatch.setattr(satisfying_bot, "run_lock", RunLock())
    monkeypatch.setattr(
        satisfying_bot, "bot_config", SimpleNamespace(allowed_user_ids=[1, 2])
    )
    return container


class TestBot:
    @pytest.mark.asyncio
    async def test_autopost_with_a_count_runs_the_flow_and_reports_to_the_chat(
        self, bot
    ):
        update, context, _ = telegram(args=["2"])

        await satisfying_bot.cmd_autopost(update, context)

        assert bot.flow.calls == [("run", {"count": 2, "output_dir": "output/daily"})]
        assert context.bot.sent == [
            (500, "🚀 Auto-post manual iniciado."),
            (500, "progresso do fluxo"),
        ]

    @pytest.mark.asyncio
    async def test_the_daily_job_is_autopost_without_a_count(self, bot):
        update, context, _ = telegram(args=None)
        await satisfying_bot.cmd_autopost(update, context)
        job_context = SimpleNamespace(bot=FakeBot())

        await satisfying_bot._daily_find(job_context)

        manual, daily = bot.flow.calls
        assert manual == daily == ("run", {"count": None, "output_dir": "output/daily"})
        # The daily job reports to the first allowed user.
        assert job_context.bot.sent == [(1, "progresso do fluxo")]

    @pytest.mark.asyncio
    async def test_a_second_run_is_refused_while_one_is_going(self, bot):
        bot.flow.hold = asyncio.Event()
        first = asyncio.create_task(
            satisfying_bot._daily_find(SimpleNamespace(bot=FakeBot()))
        )
        await asyncio.sleep(0)
        update, context, _ = telegram(args=["1"])

        await satisfying_bot.cmd_autopost(update, context)
        bot.flow.hold.set()
        await first

        assert len(bot.flow.calls) == 1
        assert context.bot.sent[-1] == (500, "Já existe um fluxo em andamento.")

    @pytest.mark.asyncio
    async def test_collect_with_days_runs_the_collection_and_reports_to_the_chat(
        self, bot
    ):
        update, context, _ = telegram(args=["30"])

        await satisfying_bot.cmd_collect(update, context)

        assert bot.collection.calls == [("collect", {"lookback_days": 30})]
        assert context.bot.sent == [
            (500, "📊 Coleta de desempenho iniciada."),
            (500, "progresso da coleta"),
        ]

    @pytest.mark.asyncio
    async def test_collect_without_days_uses_the_configured_window(self, bot):
        update, context, _ = telegram(args=None)

        await satisfying_bot.cmd_collect(update, context)

        assert bot.collection.calls == [("collect", {"lookback_days": None})]

    @pytest.mark.asyncio
    async def test_collect_is_refused_while_a_daily_run_is_going(self, bot):
        bot.flow.hold = asyncio.Event()
        daily = asyncio.create_task(
            satisfying_bot._daily_find(SimpleNamespace(bot=FakeBot()))
        )
        await asyncio.sleep(0)
        update, context, _ = telegram(args=["30"])

        await satisfying_bot.cmd_collect(update, context)
        bot.flow.hold.set()
        await daily

        assert bot.collection.calls == []
        assert context.bot.sent == [(500, "Já existe um fluxo em andamento.")]

    @pytest.mark.asyncio
    async def test_a_failed_collection_is_reported_and_frees_the_lock(self, bot):
        bot.collection.error = RuntimeError("sessão expirada")
        update, context, _ = telegram(args=None)

        await satisfying_bot.cmd_collect(update, context)

        assert context.bot.sent[-1] == (500, "❌ Coleta falhou: sessão expirada")
        assert not satisfying_bot.run_lock.locked

    @pytest.mark.asyncio
    async def test_a_bad_count_is_answered_and_nothing_runs(self, bot):
        update, context, replies = telegram(args=["zero"])

        await satisfying_bot.cmd_autopost(update, context)

        assert replies == ["Use /autopost ou /autopost 2"]
        assert bot.flow.calls == []

    @pytest.mark.asyncio
    async def test_a_stranger_cannot_start_a_run(self, bot):
        update, context, replies = telegram(args=None, user_id=99)

        await satisfying_bot.cmd_autopost(update, context)

        assert bot.flow.calls == []
        assert replies and "permissão" in replies[0]


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def cli(monkeypatch, *argv, manifests=None) -> tuple[FakeContainer, int]:
    container = FakeContainer(manifests)
    monkeypatch.setattr(daily_auto_publish, "container", container)
    monkeypatch.setattr(sys, "argv", ["daily_auto_publish.py", *argv])
    return container, daily_auto_publish.main()


class TestCommandLine:
    def test_count_runs_the_full_flow_like_the_bot(self, monkeypatch):
        container, code = cli(monkeypatch, "--count", "2")

        assert code == 0
        assert container.flow.calls == [
            ("run", {"count": 2, "output_dir": "output/daily"})
        ]

    def test_generate_only_generates_without_building_a_publisher(self, monkeypatch):
        container, code = cli(
            monkeypatch, "--generate-only", "--count", "1", "--output-dir", "out/x"
        )

        assert code == 0
        assert container.flow.calls == [
            ("generate", {"count": 1, "output_dir": "out/x"})
        ]
        assert container.builds[0]["publisher"] is None

    def test_publish_only_publishes_what_the_store_loads(self, monkeypatch, capsys):
        videos = [GeneratedVideo("a.mp4", "A", "", "url-a")]

        container, code = cli(
            monkeypatch, "--publish-only", "out/day", manifests=videos
        )

        assert code == 0
        assert container.loaded_from == ["out/day"]
        assert container.flow.calls == [("publish", {"videos": videos})]
        assert "Found 1 videos in out/day" in capsys.readouterr().out

    def test_publish_only_with_nothing_to_publish_exits_1(self, monkeypatch):
        container, code = cli(monkeypatch, "--publish-only", "out/empty")

        assert code == 1
        assert container.flow.calls == []

    def test_progress_goes_to_stdout(self, monkeypatch, capsys):
        cli(monkeypatch)

        assert "progresso do fluxo" in capsys.readouterr().out


def collect_cli(monkeypatch, *argv) -> tuple[FakeContainer, int]:
    container = FakeContainer()
    monkeypatch.setattr(collect_performance, "container", container)
    monkeypatch.setattr(sys, "argv", ["collect_performance.py", *argv])
    return container, collect_performance.main()


class TestCollectCommandLine:
    @pytest.mark.asyncio
    async def test_lookback_days_collects_like_the_bot(self, monkeypatch, bot):
        update, context, _ = telegram(args=["30"])
        await satisfying_bot.cmd_collect(update, context)

        container, code = await asyncio.to_thread(
            collect_cli, monkeypatch, "--lookback-days", "30"
        )

        assert code == 0
        assert container.collection.calls == bot.collection.calls

    def test_without_arguments_the_window_comes_from_config(self, monkeypatch):
        container, code = collect_cli(monkeypatch)

        assert code == 0
        assert container.collection.calls == [("collect", {"lookback_days": None})]

    def test_assign_attaches_a_video_to_a_record(self, monkeypatch, capsys):
        container, code = collect_cli(monkeypatch, "--assign", "7412", "42")

        assert code == 0
        assert container.collection.calls == [
            ("assign", {"tiktok_video_id": "7412", "record_id": 42})
        ]
        assert "Registro 42 ↔ TikTok 7412" in capsys.readouterr().out

    def test_a_failed_collection_exits_1(self, monkeypatch, capsys):
        container = FakeContainer()
        container.collection.error = RuntimeError("sessão expirada")
        monkeypatch.setattr(collect_performance, "container", container)
        monkeypatch.setattr(sys, "argv", ["collect_performance.py"])

        assert collect_performance.main() == 1
        assert "Fatal: sessão expirada" in capsys.readouterr().err

    def test_progress_goes_to_stdout(self, monkeypatch, capsys):
        collect_cli(monkeypatch)

        assert "progresso da coleta" in capsys.readouterr().out
