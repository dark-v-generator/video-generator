from typing import AsyncIterable
import litellm

from src.adapters.proxies.interfaces import ILLMProxy
from src.entities.configs.llm import PromptLLMConfig
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger
import os
import json
import yaml
from jinja2 import Environment, FileSystemLoader

# Set up litellm configuration if necessary
# Disable litellm telemetry
litellm.telemetry = False


class PromptLLMProxy(ILLMProxy):
    def __init__(self, config: PromptLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config

    def _get_model_string(self) -> str:
        provider = self.config.provider
        model = self.config.model
        if provider == "openai":
            return model
        elif provider == "ollama":
            return f"ollama/{model}"
        elif provider == "google":
            return f"gemini/{model}"
        return model

    def _get_system_prompt(self, target_language: Language) -> str:
        return f"""
You are an expert translator and text adapter.
Your task is to take the user's raw input text and translate/adapt it into highly engaging, naturally flowing {get_language_name(target_language)}.

Make the tone suitable and conversational, ensuring the core message translates accurately and adaptively.

Return **ONLY** the adapted translated text. Do not add any outside commentary or notes.
        """.strip()

    async def translate_and_adapt(
        self, text: str, target_language: Language
    ) -> AsyncIterable[str]:
        model_str = self._get_model_string()
        self._logger.info(f"Using LiteLLM to translate and adapt via {model_str}")

        messages = [
            {"role": "system", "content": self._get_system_prompt(target_language)},
            {"role": "user", "content": text},
        ]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        model_str = self._get_model_string()
        self._logger.info(f"Generating 2-part story via LiteLLM {model_str}")

        # 1. Load Examples
        examples = []
        yaml_path = os.path.join(os.path.dirname(__file__), "dspy_examples.yaml")
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    examples = data

        # 2. Render Template
        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("two_part_story.jinja2")

        prompt = template.render(
            target_language=get_language_name(target_language),
            examples=examples,
            reddit_title=title,
            reddit_text=content,
        )

        messages = [
            {"role": "user", "content": prompt},
        ]

        # 3. Call LiteLLM with JSON format
        kwargs = {}
        # Simple JSON mode enforcer for models that support it
        if "gpt" in model_str or "gemini" in model_str:
            kwargs["response_format"] = {"type": "json_object"}

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs,
        )

        response_text = response.choices[0].message.content

        # 4. Parse the JSON response
        try:
            # Strip markdown json blocks if returned
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            result = json.loads(response_text)
            return {
                "title": result.get("title", ""),
                "part1": result.get("part1", ""),
                "part2": result.get("part2", ""),
            }
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM JSON response: {response_text}")
            raise RuntimeError(f"Could not parse valid JSON from LLM: {e}")
