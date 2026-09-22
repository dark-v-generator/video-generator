"""Regression test: the CLI and the server must send the same editorial prompt.

FR-003 — the assistant working on the laptop follows exactly the text that
``PromptLLMProxy.generate_story`` would send to the paid model, so the
editorial rules keep living in a single template.
"""

import json
from types import SimpleNamespace

import pytest

from src.entities.configs.proxies.llm import LLMProviderConfig, PromptLLMConfig
from src.entities.language import Language
from src.proxies import llm_prompt_proxy
from src.proxies.llm_prompt_proxy import PromptLLMProxy
from src.proxies.prompts.render import render_story_prompt

TITLE = "No second date and I can't be happier"
CONTENT = "I work as a waiter in a fancy restaurant.\n\nHe asked me to stay away."


@pytest.mark.asyncio
async def test_render_matches_the_prompt_the_proxy_sends(monkeypatch):
    sent: list[str] = []

    async def fake_acompletion(*, model, messages, **kwargs):
        sent.append(messages[0]["content"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {"title": "t", "narrator_gender": "male", "script": "s"}
                        )
                    ),
                    finish_reason="stop",
                )
            ]
        )

    monkeypatch.setattr(llm_prompt_proxy.litellm, "acompletion", fake_acompletion)

    proxy = PromptLLMProxy(
        PromptLLMConfig(
            provider_config=LLMProviderConfig(provider="openrouter", model="any/model")
        )
    )
    await proxy.generate_story(
        title=TITLE, content=CONTENT, target_language=Language.PORTUGUESE
    )

    rendered = render_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert sent == [rendered]


def test_rendered_prompt_starts_with_the_template_opening():
    rendered = render_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert rendered.startswith("You are an expert TikTok scriptwriter.")


def test_rendered_prompt_embeds_the_post_and_the_target_language():
    rendered = render_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert TITLE in rendered
    assert CONTENT in rendered
    assert "Portuguese (Brazil)" in rendered
    assert "# EXAMPLES" not in rendered
