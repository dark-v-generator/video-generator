"""Tests for the local story-preparation CLI (scripts/prepare_story.py).

No subcommand may reach a paid model, so every collaborator is faked here and
the assertions focus on what the CLI itself is responsible for: what it passes
to the services, what it writes to disk, what it prints and its exit code.
"""

import json
import re
import subprocess
import time
from pathlib import Path

import pytest

from scripts import prepare_story
from src.core.container import container
from src.entities.config import EvaluationConfig, MainConfig
from src.entities.editor.audio_clip import AudioClip
from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import StoryCandidate
from src.proxies.prompts.render import render_two_part_story_prompt
from src.services.speech_service import SpeechResult
from tests.test_prepared_story_package import package_payload, two_part_payload


def make_post(post_id: str, title: str, score: int = 2500) -> RedditPost:
    return RedditPost(
        title=title,
        content=f"Conteudo completo do post {post_id}.\n\nSegundo paragrafo.",
        community="r/pettyrevenge",
        author="u/someone",
        community_url_photo="https://styles.redditmedia.com/icon.png",
        url=f"https://www.reddit.com/r/pettyrevenge/comments/{post_id}/slug/",
        score=score,
        num_comments=310,
        upvote_ratio=0.96,
        created_utc=time.time() - 7200,
    )


class FakeStoryFinder:
    def __init__(self, candidates: list[StoryCandidate]):
        self._candidates = candidates
        self.calls: list[dict] = []

    async def find_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._candidates)

    async def find_best_stories(self, **kwargs):
        raise AssertionError("the CLI must never run the LLM evaluation")


class FakeRedditProxy:
    def __init__(self, post: RedditPost):
        self._post = post
        self.requested: list[str] = []

    def get_reddit_post(self, url: str) -> RedditPost:
        self.requested.append(url)
        return self._post


@pytest.fixture
def config():
    cfg = MainConfig(
        language=Language.PORTUGUESE,
        evaluation=EvaluationConfig(subreddits=["pettyrevenge", "Antiwork"]),
    )
    container.main_config.override(cfg)
    yield cfg
    container.main_config.reset_override()


@pytest.fixture
def finder():
    fake = FakeStoryFinder(
        [
            StoryCandidate(
                post=make_post("aaa111", "Primeira historia"),
                deterministic_score=78.4,
                score_breakdown={"length": 100.0},
            ),
            StoryCandidate(
                post=make_post("bbb222", "Segunda historia"),
                deterministic_score=61.2,
                score_breakdown={"length": 80.0},
            ),
        ]
    )
    container.story_finder_service.override(fake)
    yield fake
    container.story_finder_service.reset_override()


def write_package(directory, **overrides) -> str:
    payload = package_payload(**overrides)
    path = (
        directory
        / f"{payload['post']['url'].split('/comments/')[1].split('/')[0]}.json"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestFind:
    def test_writes_candidates_file(self, tmp_path, config, finder, capsys):
        code = prepare_story.main(["find", "--out", str(tmp_path)])

        assert code == 0
        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert data["sort"] == "top"
        assert data["time_filter"] == "day"
        assert data["subreddits"] == ["pettyrevenge", "Antiwork"]
        assert data["generated_at"]
        assert [c["rank"] for c in data["candidates"]] == [1, 2]
        assert data["candidates"][0]["deterministic_score"] == 78.4
        assert data["candidates"][0]["post"]["title"] == "Primeira historia"

    def test_prints_the_shortlist(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert "Primeira historia" in out
        assert "78.4" in out
        assert "pettyrevenge" in out
        assert "310" in out
        assert "https://www.reddit.com/r/pettyrevenge/comments/aaa111/slug/" in out

    def test_forwards_the_search_options(self, tmp_path, config, finder):
        prepare_story.main(
            [
                "find",
                "--out",
                str(tmp_path),
                "--sort",
                "hot",
                "--time",
                "week",
                "--per-sub",
                "10",
                "--top-per-sub",
                "2",
                "--sub",
                "r/Antiwork",
            ]
        )

        call = finder.calls[0]
        assert call["sort"] == "hot"
        assert call["time_filter"] == "week"
        assert call["posts_per_sub"] == 10
        assert call["top_per_sub"] == 2
        assert call["subreddits"] == ["Antiwork"]

    def test_excludes_packages_already_prepared(self, tmp_path, config, finder):
        write_package(tmp_path)

        prepare_story.main(["find", "--out", str(tmp_path)])

        excluded = finder.calls[0]["exclude_urls"]
        assert (
            "https://www.reddit.com/r/MaliciousCompliance/comments/1vuze4m/"
            "no_second_date_and_i_cant_be_happier/" in excluded
        )


class TestShow:
    def test_prints_the_full_original_text(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["show", "2", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert code == 0
        assert "Segunda historia" in out
        assert "Conteudo completo do post bbb222." in out
        assert "Segundo paragrafo." in out

    def test_unknown_rank_fails(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])

        code = prepare_story.main(["show", "9", "--out", str(tmp_path)])

        assert code == 1

    def test_url_appends_the_post_as_the_next_rank(
        self, tmp_path, config, finder, capsys
    ):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        post = make_post("ccc333", "Historia vinda de URL")
        proxy = FakeRedditProxy(post)
        container.reddit_proxy.override(proxy)
        try:
            code = prepare_story.main(
                ["show", "--url", post.url, "--out", str(tmp_path)]
            )
        finally:
            container.reddit_proxy.reset_override()

        out = capsys.readouterr().out
        assert code == 0
        assert proxy.requested == [post.url]
        assert "Historia vinda de URL" in out
        assert "#3" in out

        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert [c["rank"] for c in data["candidates"]] == [1, 2, 3]
        assert data["candidates"][2]["post"]["title"] == "Historia vinda de URL"

    def test_url_works_without_a_previous_find(self, tmp_path, config, capsys):
        post = make_post("ccc333", "Historia vinda de URL")
        container.reddit_proxy.override(FakeRedditProxy(post))
        try:
            code = prepare_story.main(
                ["show", "--url", post.url, "--out", str(tmp_path)]
            )
        finally:
            container.reddit_proxy.reset_override()

        assert code == 0
        data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
        assert [c["rank"] for c in data["candidates"]] == [1]


class TestPrompt:
    def test_prints_the_server_prompt_for_the_candidate(
        self, tmp_path, config, finder, capsys
    ):
        from src.proxies.prompts.render import render_story_prompt

        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["prompt", "1", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert code == 0
        expected = render_story_prompt(
            "Primeira historia",
            "Conteudo completo do post aaa111.\n\nSegundo paragrafo.",
            Language.PORTUGUESE,
        )
        assert out.strip() == expected.strip()

    def test_language_can_be_overridden(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        prepare_story.main(["prompt", "1", "--out", str(tmp_path), "--language", "en"])

        assert "English" in capsys.readouterr().out


class TestValidate:
    def test_valid_package_passes(self, tmp_path, config, capsys):
        path = write_package(tmp_path)

        code = prepare_story.main(["validate", path])

        assert code == 0
        assert "✓" in capsys.readouterr().out

    def test_forbidden_word_fails_with_the_problem_list(self, tmp_path, config, capsys):
        path = write_package(
            tmp_path,
            script_text="No fim das contas ele matou a paciencia de todo mundo.",
        )

        code = prepare_story.main(["validate", path])

        out = capsys.readouterr().out
        assert code == 1
        assert "✗" in out
        assert "script_text: 'matou' em" in out

    def test_wrong_language_fails(self, tmp_path, config, capsys):
        path = write_package(tmp_path, language="en")

        code = prepare_story.main(["validate", path])

        assert code == 1
        assert "language: package=en server=pt" in capsys.readouterr().out

    def test_malformed_package_is_reported_not_crashed(self, tmp_path, config, capsys):
        path = tmp_path / "broken.json"
        path.write_text('{"version": 1}', encoding="utf-8")

        code = prepare_story.main(["validate", str(path)])

        assert code == 1
        assert "✗" in capsys.readouterr().out

    def test_one_bad_file_fails_the_whole_run(self, tmp_path, config, capsys):
        good = write_package(tmp_path)
        bad = tmp_path / "broken.json"
        bad.write_text("not json at all", encoding="utf-8")

        code = prepare_story.main(["validate", good, str(bad)])

        out = capsys.readouterr().out
        assert code == 1
        assert "✓" in out and "✗" in out


class TestList:
    def test_lists_packages_with_preview_status(self, tmp_path, config, capsys):
        write_package(tmp_path)

        code = prepare_story.main(["list", "--out", str(tmp_path)])
        out = capsys.readouterr().out

        assert code == 0
        assert "1vuze4m" in out
        assert "Ele pediu pra eu ignorar o encontro dele" in out
        assert "2026-09-21" in out
        assert "sem mp3" in out

        (tmp_path / "1vuze4m.preview.mp3").write_bytes(b"x")
        prepare_story.main(["list", "--out", str(tmp_path)])

        assert "mp3 ok" in capsys.readouterr().out

    def test_ignores_the_candidates_file(self, tmp_path, config, finder, capsys):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["list", "--out", str(tmp_path)])

        assert code == 0
        assert "Nenhum pacote" in capsys.readouterr().out


MP3_FIXTURE = Path(__file__).parent / "data" / "output_portuguese.mp3"


class FakeSpeechService:
    """Returns a real (short) mp3 so the duration the CLI prints is a real one."""

    def __init__(self):
        self.calls: list[dict] = []

    async def generate_speech(self, **kwargs):
        self.calls.append(kwargs)
        speech_bytes = MP3_FIXTURE.read_bytes()
        return SpeechResult(clip=AudioClip(bytes=speech_bytes), bytes=speech_bytes)


@pytest.fixture
def speech():
    fake = FakeSpeechService()
    container.speech_service.override(fake)
    yield fake
    container.speech_service.reset_override()


class TestPreview:
    def test_writes_the_mp3_next_to_the_package(self, tmp_path, config, speech, capsys):
        path = write_package(tmp_path)

        code = prepare_story.main(["preview", path])

        assert code == 0
        assert (tmp_path / "1vuze4m.preview.mp3").exists()
        assert "1vuze4m.preview.mp3" in capsys.readouterr().out

    def test_uses_the_voice_and_language_of_the_package(
        self, tmp_path, config, speech, capsys
    ):
        path = write_package(
            tmp_path, narrator_gender="female", resolved_gender="female"
        )

        prepare_story.main(["preview", path])

        assert speech.calls == [
            {
                "text": package_payload()["script_text"],
                "gender": "female",
                "rate": 1.0,
                "language": Language.PORTUGUESE,
            }
        ]

    def test_prints_the_duration_as_mm_ss(self, tmp_path, config, speech, capsys):
        path = write_package(tmp_path)

        prepare_story.main(["preview", path])

        out = capsys.readouterr().out
        assert re.search(r"\b\d{2}:\d{2}\b", out)

    def test_rate_can_be_overridden(self, tmp_path, config, speech, capsys):
        path = write_package(tmp_path)

        prepare_story.main(["preview", path, "--rate", "1.5"])

        assert speech.calls[0]["rate"] == 1.5

    def test_second_run_replaces_the_previous_mp3(
        self, tmp_path, config, speech, capsys
    ):
        path = write_package(tmp_path)
        mp3 = tmp_path / "1vuze4m.preview.mp3"
        mp3.write_bytes(b"stale")

        prepare_story.main(["preview", path])

        assert mp3.read_bytes() != b"stale"
        assert len(speech.calls) == 1


class FakeSubprocess:
    """Records every command and answers from a queue of scripted results."""

    def __init__(self, results=None):
        self.commands: list[list[str]] = []
        self._results = dict(results or {})

    def __call__(self, cmd, **kwargs):
        self.commands.append(list(cmd))
        key = cmd[0] if cmd[0] != "ssh" else _ssh_kind(cmd)
        returncode, stderr = self._results.get(key, (0, ""))
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)


def _ssh_kind(cmd: list[str]) -> str:
    remote_cmd = cmd[-1]
    if remote_cmd.startswith("mkdir"):
        return "mkdir"
    if remote_cmd.startswith("test -e"):
        return "test"
    return "ssh"


REMOTE = "gustavo@example.test:~/video-generator/.storage/prepared"


@pytest.fixture
def run(monkeypatch):
    fake = FakeSubprocess()
    monkeypatch.setattr(prepare_story.subprocess, "run", fake)
    return fake


class TestShip:
    def test_invalid_package_never_touches_the_network(
        self, tmp_path, config, run, capsys
    ):
        path = write_package(tmp_path, language="en")

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        assert code == 1
        assert run.commands == []
        assert "language: package=en" in capsys.readouterr().out

    def test_creates_the_inbox_then_checks_then_copies(
        self, tmp_path, config, run, capsys
    ):
        path = write_package(tmp_path)
        run._results["test"] = (1, "")  # no duplicate on the remote

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        assert code == 0
        assert run.commands == [
            [
                "ssh",
                "gustavo@example.test",
                "mkdir -p ~/video-generator/.storage/prepared/inbox",
            ],
            [
                "ssh",
                "gustavo@example.test",
                "test -e ~/video-generator/.storage/prepared/inbox/1vuze4m.json",
            ],
            [
                "scp",
                path,
                "gustavo@example.test:~/video-generator/.storage/prepared/inbox/",
            ],
        ]
        assert "1vuze4m.json" in capsys.readouterr().out

    def test_duplicate_asks_and_aborts_on_no(
        self, tmp_path, config, run, monkeypatch, capsys
    ):
        path = write_package(tmp_path)
        run._results["test"] = (0, "")  # already queued
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        assert code == 1
        assert [c[0] for c in run.commands] == ["ssh", "ssh"]

    def test_duplicate_proceeds_on_yes(
        self, tmp_path, config, run, monkeypatch, capsys
    ):
        path = write_package(tmp_path)
        run._results["test"] = (0, "")
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        assert code == 0
        assert run.commands[-1][0] == "scp"

    def test_force_skips_the_question(self, tmp_path, config, run, monkeypatch, capsys):
        path = write_package(tmp_path)
        run._results["test"] = (0, "")

        def no_input(prompt=""):
            raise AssertionError("--force must not prompt")

        monkeypatch.setattr("builtins.input", no_input)

        code = prepare_story.main(["ship", path, "--remote", REMOTE, "--force"])

        assert code == 0
        assert run.commands[-1][0] == "scp"

    def test_scp_failure_exits_2_and_leaves_the_local_file_alone(
        self, tmp_path, config, run, capsys
    ):
        path = write_package(tmp_path)
        before = Path(path).read_bytes()
        run._results["test"] = (1, "")
        run._results["scp"] = (1, "ssh: connect to host example.test: timed out")

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        out = capsys.readouterr().out
        assert code == 2
        assert "timed out" in out
        assert "scp" in out
        assert Path(path).read_bytes() == before

    def test_unreachable_host_on_mkdir_exits_2_before_copying(
        self, tmp_path, config, run, capsys
    ):
        path = write_package(tmp_path)
        run._results["mkdir"] = (255, "ssh: Could not resolve hostname")

        code = prepare_story.main(["ship", path, "--remote", REMOTE])

        assert code == 2
        assert [c[0] for c in run.commands] == ["ssh"]

    def test_remote_defaults_to_the_config(self, tmp_path, config, run, capsys):
        path = write_package(tmp_path)
        run._results["test"] = (1, "")

        prepare_story.main(["ship", path])

        assert run.commands[0][1] == "gustavo@192.168.1.100"


class TestQueue:
    def _remote_listing(self, *payloads) -> str:
        blocks = []
        for mtime, payload in payloads:
            blocks.append(f"{mtime}\n{json.dumps(payload, indent=2)}\n\n")
        return "".join(blocks)

    def test_lists_the_remote_inbox(self, tmp_path, config, monkeypatch, capsys):
        listing = self._remote_listing(
            (1789900500, package_payload()),
        )

        def fake_run(cmd, **kwargs):
            assert cmd[0] == "ssh"
            return subprocess.CompletedProcess(cmd, 0, stdout=listing, stderr="")

        monkeypatch.setattr(prepare_story.subprocess, "run", fake_run)

        code = prepare_story.main(["queue", "--remote", REMOTE])

        out = capsys.readouterr().out
        assert code == 0
        assert "1vuze4m" in out
        assert "Ele pediu pra eu ignorar o encontro dele" in out
        assert "reddit.com" in out
        assert "2026-09-21" in out

    def test_empty_inbox_says_so(self, tmp_path, config, monkeypatch, capsys):
        monkeypatch.setattr(
            prepare_story.subprocess,
            "run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "", ""),
        )

        code = prepare_story.main(["queue", "--remote", REMOTE])

        assert code == 0
        assert "Fila vazia." in capsys.readouterr().out

    def test_ssh_failure_exits_2(self, tmp_path, config, monkeypatch, capsys):
        monkeypatch.setattr(
            prepare_story.subprocess,
            "run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(
                cmd, 255, "", "Connection refused"
            ),
        )

        code = prepare_story.main(["queue", "--remote", REMOTE])

        assert code == 2
        assert "Connection refused" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Two-part packages (version 2)
# ---------------------------------------------------------------------------


def write_two_part_package(directory, **overrides) -> str:
    payload = two_part_payload(**overrides)
    directory.mkdir(parents=True, exist_ok=True)
    path = (
        directory
        / f"{payload['post']['url'].split('/comments/')[1].split('/')[0]}.json"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestTwoPartPrompt:
    def test_two_part_flag_prints_the_two_part_prompt(
        self, tmp_path, config, finder, capsys
    ):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        code = prepare_story.main(["prompt", "1", "--two-part", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert code == 0
        assert out.startswith(
            render_two_part_story_prompt(
                "Primeira historia",
                make_post("aaa111", "Primeira historia").content,
                Language.PORTUGUESE,
            )
        )

    def test_without_the_flag_the_single_prompt_is_unchanged(
        self, tmp_path, config, finder, capsys
    ):
        prepare_story.main(["find", "--out", str(tmp_path)])
        capsys.readouterr()

        prepare_story.main(["prompt", "1", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert "2-part story" not in out


class TestTwoPartValidate:
    def test_valid_two_part_package_passes(self, tmp_path, config, capsys):
        path = write_two_part_package(tmp_path)

        code = prepare_story.main(["validate", path])

        assert code == 0
        assert capsys.readouterr().out.startswith("✓")

    def test_missing_cta_names_the_field(self, tmp_path, config, capsys):
        path = write_two_part_package(
            tmp_path, part1_text="Ele jurou que nao tinha nada."
        )

        code = prepare_story.main(["validate", path])

        out = capsys.readouterr().out
        assert code == 1
        assert "✗" in out
        assert (
            'part1_text: precisa terminar com "Curta e me siga para a parte 2."' in out
        )

    def test_forbidden_word_in_part_two_names_the_field(self, tmp_path, config, capsys):
        path = write_two_part_package(
            tmp_path, part2_text="No fim ele pegou a arma da gaveta."
        )

        code = prepare_story.main(["validate", path])

        out = capsys.readouterr().out
        assert code == 1
        assert "part2_text: 'arma'" in out

    def test_unknown_version_is_reported_not_crashed(self, tmp_path, config, capsys):
        path = tmp_path / "1vuze4m.json"
        path.write_text(json.dumps(two_part_payload(version=3)), encoding="utf-8")

        code = prepare_story.main(["validate", str(path)])

        out = capsys.readouterr().out
        assert code == 1
        assert "unsupported package version" in out

    def test_both_versions_validate_in_the_same_run(self, tmp_path, config, capsys):
        single = write_package(tmp_path)
        two_part = write_two_part_package(tmp_path / "other")

        code = prepare_story.main(["validate", single, two_part])

        out = capsys.readouterr().out
        assert code == 0
        assert out.count("✓") == 2


class TestTwoPartList:
    def test_two_part_package_is_marked(self, tmp_path, config, capsys):
        write_two_part_package(tmp_path)

        prepare_story.main(["list", "--out", str(tmp_path)])

        out = capsys.readouterr().out
        assert "2 partes" in out
        assert "sem mp3" in out

    def test_both_previews_are_needed_for_the_mp3_mark(self, tmp_path, config, capsys):
        write_two_part_package(tmp_path)
        (tmp_path / "1vuze4m.part1.preview.mp3").write_bytes(b"x")

        prepare_story.main(["list", "--out", str(tmp_path)])
        assert "sem mp3" in capsys.readouterr().out

        (tmp_path / "1vuze4m.part2.preview.mp3").write_bytes(b"x")

        prepare_story.main(["list", "--out", str(tmp_path)])
        assert "mp3 ok" in capsys.readouterr().out

    def test_single_part_package_is_not_marked(self, tmp_path, config, capsys):
        write_package(tmp_path)

        prepare_story.main(["list", "--out", str(tmp_path)])

        assert "2 partes" not in capsys.readouterr().out


class TestTwoPartPreview:
    def test_writes_one_mp3_per_part(self, tmp_path, config, speech, capsys):
        path = write_two_part_package(tmp_path)

        code = prepare_story.main(["preview", path])

        assert code == 0
        assert (tmp_path / "1vuze4m.part1.preview.mp3").exists()
        assert (tmp_path / "1vuze4m.part2.preview.mp3").exists()
        assert not (tmp_path / "1vuze4m.preview.mp3").exists()

    def test_each_part_is_narrated_with_the_package_voice(
        self, tmp_path, config, speech, capsys
    ):
        payload = two_part_payload(narrator_gender="female", resolved_gender="female")
        path = write_two_part_package(
            tmp_path, narrator_gender="female", resolved_gender="female"
        )

        prepare_story.main(["preview", path])

        assert speech.calls == [
            {
                "text": payload["part1_text"],
                "gender": "female",
                "rate": 1.0,
                "language": Language.PORTUGUESE,
            },
            {
                "text": payload["part2_text"],
                "gender": "female",
                "rate": 1.0,
                "language": Language.PORTUGUESE,
            },
        ]

    def test_prints_each_duration_and_the_total(self, tmp_path, config, speech, capsys):
        path = write_two_part_package(tmp_path)

        prepare_story.main(["preview", path])

        out = capsys.readouterr().out
        assert "part1.preview.mp3" in out
        assert "part2.preview.mp3" in out
        assert "total" in out.lower()
        assert len(re.findall(r"\b\d{2}:\d{2}\b", out)) == 3


class TestTwoPartQueue:
    def test_remote_listing_shows_a_two_part_package(
        self, tmp_path, config, monkeypatch, capsys
    ):
        listing = f"1789900500\n{json.dumps(two_part_payload(), indent=2)}\n\n"

        monkeypatch.setattr(
            prepare_story.subprocess,
            "run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, listing, ""),
        )

        code = prepare_story.main(["queue", "--remote", REMOTE])

        out = capsys.readouterr().out
        assert code == 0
        assert "1vuze4m" in out
        assert "Ele pediu pra eu ignorar o encontro dele" in out
        assert "2 partes" in out
