"""Tests for the prepared-story package entity and its local validation."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.entities.configs.bots import TelegramBotConfig
from src.entities.language import Language
from src.entities.prepared_story import (
    PreparedStoryPackage,
    TwoPartStoryPackage,
    extract_post_id,
    load_package,
)
from src.services.prepared_story_validation import validate_package
from src.services.reddit_video_service import PreparedStory, StoryScript
from src.services.text_censor import TextCensor

POST_URL = (
    "https://www.reddit.com/r/MaliciousCompliance/comments/1vuze4m/"
    "no_second_date_and_i_cant_be_happier/"
)


def package_payload(**overrides) -> dict:
    payload = {
        "version": 1,
        "source": "claude-code",
        "language": "pt-br",
        "created_at": "2026-09-21T10:40:12",
        "post": {
            "title": "No second date and I can't be happier",
            "content": "I work as a waiter in a fancy restaurant and one night ...",
            "community": "r/MaliciousCompliance",
            "author": "u/someone",
            "community_url_photo": "https://styles.redditmedia.com/icon.png",
            "url": POST_URL,
            "score": 4120,
            "num_comments": 310,
            "upvote_ratio": 0.96,
            "created_utc": 1789900000.0,
        },
        "story_title": "Ele pediu pra eu ignorar o encontro dele",
        "script_text": "A acompanhante dele veio reclamar comigo. Foi ele que pediu.",
        "narrator_gender": "male",
        "resolved_gender": "male",
        "summary": "Um garcom recebe um cliente que exige nao ser interrompido.",
        "hashtags": ["historia", "reddit"],
    }
    payload.update(overrides)
    return payload


def build_package(**overrides) -> PreparedStoryPackage:
    return PreparedStoryPackage.model_validate(package_payload(**overrides))


class TestExtractPostId:
    def test_extracts_id_from_comments_url(self):
        assert extract_post_id(POST_URL) == "1vuze4m"

    def test_extracts_id_without_trailing_slug(self):
        assert extract_post_id("https://reddit.com/r/x/comments/abc123") == "abc123"

    def test_url_without_comments_segment_is_an_error(self):
        with pytest.raises(ValueError) as exc:
            extract_post_id("https://www.reddit.com/r/MaliciousCompliance/")

        assert "/comments/" in str(exc.value)

    def test_missing_url_is_an_error(self):
        with pytest.raises(ValueError):
            extract_post_id(None)


class TestPreparedStoryPackage:
    def test_json_round_trip(self):
        raw = json.dumps(package_payload())

        package = PreparedStoryPackage.model_validate_json(raw)
        reloaded = PreparedStoryPackage.model_validate_json(package.model_dump_json())

        assert reloaded == package
        assert reloaded.created_at == datetime(2026, 9, 21, 10, 40, 12)

    def test_post_id_comes_from_the_post_url(self):
        assert build_package().post_id == "1vuze4m"

    def test_post_url_without_id_is_rejected_with_a_clear_message(self):
        payload = package_payload()
        payload["post"]["url"] = "https://www.reddit.com/r/MaliciousCompliance/"

        with pytest.raises(ValidationError) as exc:
            PreparedStoryPackage.model_validate(payload)

        assert "/comments/" in str(exc.value)

    def test_language_accepts_pt_br_and_serializes_back(self):
        package = build_package(language="pt-br")

        assert package.language is Language.PORTUGUESE

        dumped = json.loads(package.model_dump_json())
        assert (
            PreparedStoryPackage.model_validate(dumped).language is Language.PORTUGUESE
        )

    def test_to_prepared_story_maps_one_to_one(self):
        package = build_package()

        prepared = package.to_prepared_story()

        assert isinstance(prepared, PreparedStory)
        assert prepared.post == package.post
        assert prepared.script_text == package.script_text
        assert prepared.story_title == package.story_title
        assert prepared.narrator_gender == package.narrator_gender
        assert prepared.resolved_gender == package.resolved_gender

    def test_original_post_md_matches_what_the_server_builds(self):
        package = build_package()
        post = package.post

        expected = f"# {post.title}\n\n{post.content}\n"

        assert package.original_post_md == expected
        assert package.to_prepared_story().original_post_md == expected

    def test_extra_keys_are_ignored(self):
        package = PreparedStoryPackage.model_validate(
            package_payload(notes="escolhida pelo operador em 21/09")
        )

        assert package.story_title == "Ele pediu pra eu ignorar o encontro dele"
        assert not hasattr(package, "notes")

    def test_unknown_version_is_rejected(self):
        with pytest.raises(ValidationError):
            PreparedStoryPackage.model_validate(package_payload(version=2))

    @pytest.mark.parametrize("field", ["story_title", "script_text"])
    def test_empty_text_fields_are_rejected(self, field):
        with pytest.raises(ValidationError):
            PreparedStoryPackage.model_validate(package_payload(**{field: "   "}))

    def test_hashtags_are_optional(self):
        payload = package_payload()
        del payload["hashtags"]

        assert PreparedStoryPackage.model_validate(payload).hashtags is None


class TestValidatePackage:
    def test_valid_package_has_no_problems(self):
        problems = validate_package(build_package(), TextCensor(), Language.PORTUGUESE)

        assert problems == []

    def test_language_mismatch_is_reported(self):
        problems = validate_package(
            build_package(language="en"), TextCensor(), Language.PORTUGUESE
        )

        assert problems == ["language: package=en server=pt"]

    def test_forbidden_word_in_script_is_reported_with_context(self):
        package = build_package(
            script_text=(
                "O gerente chegou gritando e o cara quase matou o garcom de "
                "tanto reclamar da conta."
            )
        )

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        assert len(problems) == 1
        assert problems[0].startswith("script_text: 'matou' em \"")
        assert "o cara quase matou o garcom de" in problems[0]

    def test_forbidden_word_in_title_is_reported(self):
        package = build_package(story_title="Ele viu sangue na cozinha e ficou mudo")

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        assert len(problems) == 1
        assert problems[0].startswith("story_title: 'sangue' em \"")

    def test_extra_word_replacements_from_config_are_detected(self):
        censor = TextCensor(extra_mappings={"demitido": "d3m*itido"})
        package = build_package(
            script_text="No dia seguinte ele foi demitido sem nenhuma explicacao."
        )

        problems = validate_package(package, censor, Language.PORTUGUESE)

        assert len(problems) == 1
        assert problems[0].startswith("script_text: 'demitido' em \"")

    def test_resolved_gender_inconsistent_with_narrator_gender_is_reported(self):
        package = build_package(narrator_gender="female", resolved_gender="male")

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        assert problems == [
            "resolved_gender: 'male' não confere com narrator_gender 'female'"
        ]

    def test_unknown_narrator_gender_does_not_constrain_resolved_gender(self):
        package = build_package(narrator_gender="unknown", resolved_gender="male")

        assert validate_package(package, TextCensor(), Language.PORTUGUESE) == []

    def test_every_forbidden_word_is_listed(self):
        package = build_package(
            story_title="Ele viu sangue",
            script_text="Depois disso ele matou a vontade de voltar la, e morreu de rir.",
        )

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        fields = [p.split(":", 1)[0] for p in problems]
        assert fields == ["story_title", "script_text", "script_text"]


class TestPreparedStoriesConfig:
    """The bot config gains a `prepared_stories` block, with usable defaults.

    Every existing config.yaml predates this feature, so loading one without
    the block must keep working and still point `ship` at the prod server.
    """

    def test_defaults_when_the_block_is_absent(self):
        config = TelegramBotConfig()

        assert (
            config.prepared_stories.remote
            == "gustavo@192.168.1.100:~/video-generator/.storage/prepared"
        )
        assert config.prepared_stories.inbox_dir == ".storage/prepared"
        assert config.prepared_stories.fill_with_discovery is True

    def test_block_overrides_only_what_it_names(self):
        config = TelegramBotConfig.model_validate(
            {"prepared_stories": {"fill_with_discovery": False}}
        )

        assert config.prepared_stories.fill_with_discovery is False
        assert config.prepared_stories.inbox_dir == ".storage/prepared"


# ---------------------------------------------------------------------------
# Two-part packages (version 2)
# ---------------------------------------------------------------------------


PART1_CTA = "Curta e me siga para a parte 2."


def two_part_payload(**overrides) -> dict:
    payload = package_payload()
    del payload["script_text"]
    payload.update(
        {
            "version": 2,
            "part1_text": (
                "Ele olhou bem nos olhos da propria filha e jurou que nao "
                f"tinha nada. {PART1_CTA}"
            ),
            "part2_text": (
                "As mensagens no celular dele nao deixavam duvida. "
                "Curta, me siga e deixe nos comentarios."
            ),
        }
    )
    payload.update(overrides)
    return payload


def build_two_part(**overrides) -> TwoPartStoryPackage:
    return TwoPartStoryPackage.model_validate(two_part_payload(**overrides))


class TestTwoPartStoryPackage:
    def test_json_round_trip(self):
        raw = json.dumps(two_part_payload())

        package = TwoPartStoryPackage.model_validate_json(raw)
        reloaded = TwoPartStoryPackage.model_validate_json(package.model_dump_json())

        assert reloaded == package
        assert reloaded.version == 2
        assert reloaded.created_at == datetime(2026, 9, 21, 10, 40, 12)

    def test_shares_the_identity_of_a_single_part_package(self):
        package = build_two_part()
        post = package.post

        assert package.post_id == "1vuze4m"
        assert package.original_post_md == f"# {post.title}\n\n{post.content}\n"

    def test_to_story_script_maps_to_the_existing_dataclass(self):
        package = build_two_part()

        script = package.to_story_script()

        assert isinstance(script, StoryScript)
        assert script.title == package.story_title
        assert script.part1 == package.part1_text
        assert script.part2 == package.part2_text
        assert script.narrator_gender == package.narrator_gender
        assert script.resolved_gender == package.resolved_gender

    def test_to_prepared_stories_suffixes_the_title_of_each_part(self):
        package = build_two_part()

        part1, part2 = package.to_prepared_stories()

        assert part1.story_title == f"{package.story_title} - Parte 1"
        assert part2.story_title == f"{package.story_title} - Parte 2"
        assert part1.script_text == package.part1_text
        assert part2.script_text == package.part2_text
        for part in (part1, part2):
            assert isinstance(part, PreparedStory)
            assert part.post == package.post
            assert part.resolved_gender == package.resolved_gender
            assert part.original_post_md == package.original_post_md

    @pytest.mark.parametrize("field", ["part1_text", "part2_text"])
    def test_empty_parts_are_rejected(self, field):
        with pytest.raises(ValidationError):
            TwoPartStoryPackage.model_validate(two_part_payload(**{field: "   "}))

    def test_version_one_payload_is_not_a_two_part_package(self):
        with pytest.raises(ValidationError):
            TwoPartStoryPackage.model_validate(package_payload())

    def test_extra_keys_are_ignored(self):
        package = TwoPartStoryPackage.model_validate(
            two_part_payload(notes="cortada na confissao")
        )

        assert not hasattr(package, "notes")


class TestLoadPackage:
    def test_version_one_loads_as_a_single_part_package(self):
        package = load_package(json.dumps(package_payload()))

        assert isinstance(package, PreparedStoryPackage)
        assert package.script_text == package_payload()["script_text"]

    def test_version_two_loads_as_a_two_part_package(self):
        package = load_package(json.dumps(two_part_payload()))

        assert isinstance(package, TwoPartStoryPackage)
        assert package.part1_text.endswith(PART1_CTA)

    def test_unknown_version_is_rejected_with_a_stable_message(self):
        with pytest.raises(ValueError) as exc:
            load_package(json.dumps(package_payload(version=3)))

        assert "unsupported package version" in str(exc.value)

    def test_missing_version_is_rejected_the_same_way(self):
        payload = package_payload()
        del payload["version"]

        with pytest.raises(ValueError) as exc:
            load_package(json.dumps(payload))

        assert "unsupported package version" in str(exc.value)

    def test_broken_json_raises_a_value_error(self):
        with pytest.raises(ValueError):
            load_package("{not json at all")

    def test_a_server_that_only_knows_version_one_rejects_a_two_part_package(self):
        """SC-009: the guarantee that an old server produces nothing from a v2."""
        with pytest.raises(ValidationError):
            PreparedStoryPackage.model_validate(two_part_payload())


class TestValidateTwoPartPackage:
    def test_valid_package_has_no_problems(self):
        problems = validate_package(build_two_part(), TextCensor(), Language.PORTUGUESE)

        assert problems == []

    def test_language_mismatch_is_reported(self):
        problems = validate_package(
            build_two_part(language="en"), TextCensor(), Language.PORTUGUESE
        )

        assert problems == ["language: package=en server=pt"]

    def test_forbidden_word_in_each_part_is_reported_with_its_field(self):
        package = build_two_part(
            story_title="Ele viu sangue na cozinha",
            part1_text=(
                "O vizinho quase matou a planta que ela cuidava ha anos. "
                f"{PART1_CTA}"
            ),
            part2_text="No fim ele pegou a arma que guardava na gaveta.",
        )

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        fields = [problem.split(":", 1)[0] for problem in problems]
        assert fields == ["story_title", "part1_text", "part2_text"]
        assert problems[1].startswith("part1_text: 'matou' em \"")
        assert "quase matou a planta" in problems[1]
        assert problems[2].startswith("part2_text: 'arma' em \"")

    def test_part1_without_the_cta_is_reported(self):
        package = build_two_part(part1_text="Ele jurou que nao tinha nada.")

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        assert problems == [f'part1_text: precisa terminar com "{PART1_CTA}"']

    def test_trailing_whitespace_after_the_cta_is_accepted(self):
        package = build_two_part(
            part1_text=f"Ele jurou que nao tinha nada. {PART1_CTA}  \n"
        )

        assert validate_package(package, TextCensor(), Language.PORTUGUESE) == []

    def test_a_language_without_a_fixed_cta_skips_the_rule(self):
        package = build_two_part(
            language="en",
            part1_text="He swore there was nothing going on.",
            part2_text="The messages said otherwise.",
        )

        assert validate_package(package, TextCensor(), Language.ENGLISH) == []

    def test_gender_coherence_still_applies(self):
        package = build_two_part(narrator_gender="female", resolved_gender="male")

        problems = validate_package(package, TextCensor(), Language.PORTUGUESE)

        assert problems == [
            "resolved_gender: 'male' não confere com narrator_gender 'female'"
        ]
