"""Regression test: the CLI and the server must send the same two-part prompt.

Same guarantee as ``test_render_story_prompt.py``, for the second format. The
two-part prompt also carries the worked examples, so the assistant on the
laptop sees exactly the reference scripts the paid model would see.
"""

import json
import os
from types import SimpleNamespace

import pytest
import yaml

from src.entities.configs.proxies.llm import LLMProviderConfig, PromptLLMConfig
from src.entities.language import Language
from src.proxies import llm_prompt_proxy
from src.proxies.llm_prompt_proxy import PromptLLMProxy
from src.proxies.prompts.render import render_two_part_story_prompt

TITLE = "No second date and I can't be happier"
CONTENT = "I work as a waiter in a fancy restaurant.\n\nHe asked me to stay away."

EXAMPLES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
    "proxies",
    "examples",
    "two_part_story.yaml",
)


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
                            {
                                "title": "t",
                                "narrator_gender": "male",
                                "part1": "p1",
                                "part2": "p2",
                            }
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
    await proxy.generate_two_part_story(
        title=TITLE, content=CONTENT, target_language=Language.PORTUGUESE
    )

    rendered = render_two_part_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert sent == [rendered]


def test_rendered_prompt_starts_with_the_template_opening():
    rendered = render_two_part_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert rendered.startswith("You are an expert TikTok scriptwriter.")
    assert "2-part story" in rendered


def test_rendered_prompt_embeds_the_post_and_the_target_language():
    rendered = render_two_part_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert TITLE in rendered
    assert CONTENT in rendered
    assert "Portuguese (Brazil)" in rendered


def test_rendered_prompt_carries_every_worked_example():
    with open(EXAMPLES_PATH, encoding="utf-8") as f:
        examples = yaml.safe_load(f)

    rendered = render_two_part_story_prompt(TITLE, CONTENT, Language.PORTUGUESE)

    assert len(examples) == 3
    assert rendered.count("Expected Output JSON:") == len(examples)
    for example in examples:
        assert example["original_post"]["title"] in rendered
        # The template writes the expected outputs through `tojson`, which
        # escapes non-ASCII, so the rendered form is what we look for.
        assert json.dumps(example["title"]) in rendered
