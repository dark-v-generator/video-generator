import pytest

from src.capabilities.publishing.hashtags import (
    HashtagSuggester,
    normalize_hashtags,
    strip_trailing_hashtags,
)
from src.entities.language import Language
from tests.fakes.proxies import FakeLLMProxy


def test_normalize_hashtags_dedupes_and_caps_repeated_blocks():
    tags = normalize_hashtags(
        [
            "#chefeToxico #obedienciaCega #chefeToxico",
            "prazosPerdidos#fyp",
            "mãeTóxica",
            "extra",
        ]
    )

    assert tags == ["chefeToxico", "obedienciaCega", "prazosPerdidos"]


def test_normalize_hashtags_falls_back_to_defaults_when_empty():
    assert normalize_hashtags([]) == ["fyp", "storytime", "reddit"]


def test_normalize_hashtags_uses_defaults_only_to_fill_free_slots():
    assert normalize_hashtags(["chefeToxico"]) == ["chefeToxico", "fyp", "storytime"]


def test_strip_trailing_hashtags_keeps_title_and_removes_existing_block():
    assert (
        strip_trailing_hashtags(
            "Meu chefe me proibiu de decidir sozinho  #fyp #storytime #reddit"
        )
        == "Meu chefe me proibiu de decidir sozinho"
    )


class TestHashtagSuggester:
    @pytest.mark.asyncio
    async def test_configured_tags_come_before_the_models(self):
        llm = FakeLLMProxy()
        suggester = HashtagSuggester(llm, ["fyp"], Language.PORTUGUESE)

        tags = await suggester.suggest("Título", "Resumo")

        assert tags == ["fyp", "historia", "reddit"]
        assert llm.calls == [("generate_hashtags", "Título")]

    def test_normalize_does_not_ask_the_model(self):
        llm = FakeLLMProxy()
        suggester = HashtagSuggester(llm, ["fyp"], Language.PORTUGUESE)

        assert suggester.normalize(["#Minha História", "fyp"]) == [
            "fyp",
            "Minha",
            "Historia",
        ]
        assert llm.calls == []
