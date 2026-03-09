from typing import AsyncIterable
import litellm

from src.adapters.proxies.interfaces import ILLMProxy
from src.entities.configs.llm import PromptLLMConfig
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger

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
