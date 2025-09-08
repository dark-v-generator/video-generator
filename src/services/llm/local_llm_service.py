import asyncio
from typing import Iterator, AsyncIterable, Optional

import ollama
from pydantic.json_schema import JsonSchemaValue
from ...core.config import settings
from ...repositories.interfaces import IConfigRepository
from ...entities.captions import Captions
from ...entities.history import History
from ...entities.language import Language
from .interfaces import ILLMService
from ...core.logging_config import get_logger


class LocalLLMService(ILLMService):
    """Local LLM implementation using Ollama"""

    def __init__(self, config_repository: IConfigRepository):
        self._config_repository = config_repository
        self.base_url = settings.ollama_base_url
        self.client = ollama.Client(host=self.base_url)
        self._logger = get_logger(__name__)

    def _chat_stream(
        self,
        prompt: str,
    ):
        config = self._config_repository.load_config()
        model = config.llm_config.model
        temperature = config.llm_config.temperature

        return self.client.chat(
            model=model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": temperature,
            },
            stream=True,
        )

    def _chat(
        self,
        prompt: str,
        format: Optional[JsonSchemaValue] = None,
    ):
        config = self._config_repository.load_config()
        model = config.llm_config.model
        temperature = config.llm_config.temperature

        return self.client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=format,
            options={
                "temperature": temperature,
            },
            stream=False,
        )

    async def enhance_history(
        self, title: str, content: str, language: Language
    ) -> AsyncIterable[str]:
        """Enhance a history using Ollama with real token streaming"""

        prompt = self.get_enhance_history_prompt(content, language)
        self._logger.info(f"Enhancing history with prompt: {prompt[:100]}...")
        for chunk in self._chat_stream(prompt):
            if chunk.message and chunk.message.content:
                token = chunk.message.content
                if token:
                    yield token
                    await asyncio.sleep(0.001)

            if chunk.done:
                break

    async def enhance_captions(
        self, captions: Captions, history: History, language: Language
    ) -> Captions:
        prompt = self.get_enhance_captions_prompt(history.content, language, captions)
        self._logger.info(f"Enhancing captions with prompt: {prompt[:100]}...")
        response = self._chat(prompt, format=Captions.model_json_schema())
        result = Captions.model_validate_json(response.message.content)
        return result
