"""Tests for the prepared-story package entity and its local validation."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.entities.language import Language
from src.entities.prepared_story import PreparedStoryPackage, extract_post_id
from src.services.prepared_story_validation import validate_package
from src.services.reddit_video_service import PreparedStory
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
        assert PreparedStoryPackage.model_validate(dumped).language is Language.PORTUGUESE

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
        problems = validate_package(
            build_package(), TextCensor(), Language.PORTUGUESE
        )

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
