"""An empty model answer is classified by its finish reason, not guessed."""

from types import SimpleNamespace

import pytest

from src.capabilities.writing import (
    ModelStoryWriter,
    WriterContentBlockedError,
    WriterError,
    WriterTransientError,
)
from src.entities.configs.proxies.llm import LLMProviderConfig, PromptLLMConfig
from src.entities.language import Language
from src.entities.story import StoryOrigin
from src.proxies import llm_prompt_proxy
from src.proxies.llm_prompt_proxy import PromptLLMProxy

ORIGIN = StoryOrigin(
    url="https://www.reddit.com/r/x/comments/abc/t/",
    title="A vizinha e o bolo",
    content="Ela roubou meu bolo.",
    community="r/x",
    author="u/y",
    community_image_url="",
)


def _proxy_answering_empty(monkeypatch, finish_reason: str) -> PromptLLMProxy:
    async def empty_completion(**_):
        choice = SimpleNamespace(
            message=SimpleNamespace(content=""), finish_reason=finish_reason
        )
        return SimpleNamespace(choices=[choice])

    monkeypatch.setattr(llm_prompt_proxy.litellm, "acompletion", empty_completion)
    return PromptLLMProxy(
        PromptLLMConfig(
            provider_config=LLMProviderConfig(
                provider="openrouter", model="moonshotai/kimi-k2.6", max_tokens=20000
            )
        )
    )


async def _write(proxy: PromptLLMProxy):
    return await ModelStoryWriter(proxy).write(ORIGIN, language=Language.PORTUGUESE)


@pytest.mark.asyncio
async def test_token_limit_is_not_a_content_block(monkeypatch):
    proxy = _proxy_answering_empty(monkeypatch, "length")

    with pytest.raises(WriterError) as error:
        await _write(proxy)

    assert not isinstance(error.value, WriterContentBlockedError)
    assert not isinstance(error.value, WriterTransientError)
    assert "max_tokens" in str(error.value)


@pytest.mark.asyncio
async def test_content_filter_finish_reason_is_a_content_block(monkeypatch):
    proxy = _proxy_answering_empty(monkeypatch, "content_filter")

    with pytest.raises(WriterContentBlockedError):
        await _write(proxy)


@pytest.mark.asyncio
async def test_other_empty_answer_is_a_plain_writer_error(monkeypatch):
    proxy = _proxy_answering_empty(monkeypatch, "stop")

    with pytest.raises(WriterError) as error:
        await _write(proxy)

    assert type(error.value) is WriterError
    assert "finish_reason=stop" in str(error.value)
