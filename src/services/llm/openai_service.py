from typing import AsyncIterable
from openai import OpenAI

from ...core.config import settings

from src.entities.captions import Captions
from src.entities.history import History
from src.entities.language import Language
from .interfaces import ILLMService
from ...core.logging_config import get_logger


class OpenAILLMService(ILLMService):
    """OpenAI implementation of LLM service"""

    def __init__(self):
        # Todo change to lazy loading
        self._logger = get_logger(__name__)
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = OpenAI()
        return self.client

    async def enhance_history(
        self, title: str, content: str, language: Language
    ) -> AsyncIterable[str]:
        self._logger.info(
            f"Enhancing history with prompt: {self.get_enhance_history_prompt(content, language)[:100]}..."
        )
        stream = self._get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "user",
                    "content": self.get_enhance_history_prompt(content, language),
                },
            ],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    async def enhance_captions(
        self, captions: Captions, history: History, language: Language
    ) -> Captions:
        response = self._get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "user",
                    "content": self.get_enhance_captions_prompt(
                        history.content, language, captions
                    ),
                },
            ],
            response_format=Captions.model_json_schema(),
        )

        raw_data = response.choices[0].message.content
        return Captions.model_validate_json(raw_data)
