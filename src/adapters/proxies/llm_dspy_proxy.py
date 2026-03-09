import dspy
from typing import AsyncIterable
from src.adapters.proxies.interfaces import ILLMProxy
from src.entities.configs.llm import DSPyLLMConfig
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger


class TranslateAndAdaptSignature(dspy.Signature):
    """
    You are an expert translator and text adapter.
    Your task is to take the user's raw input text and translate/adapt it into naturally flowing text, mantaining the same meaning and context.
    Make the tone suitable and conversational, ensuring the core message translates accurately and adaptively.
    """

    target_language = dspy.InputField(
        desc="The language to translate and adapt the text into."
    )
    raw_text = dspy.InputField(desc="Raw text content to be translated and adapted.")
    adapted_script = dspy.OutputField(
        desc="The final translated text as a single fluid paragraph without outside commentary."
    )


class DSPyLLMProxy(ILLMProxy):
    def __init__(self, config: DSPyLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config
        self._configure_dspy()

        # dspy.Predict allows us to generate based on the Signature
        self.translator = dspy.Predict(TranslateAndAdaptSignature)

    def _configure_dspy(self):
        provider = self.config.provider
        model_name = self.config.model

        # Initialize dynamically based on selected provider config
        if provider == "openai":
            lm = dspy.OpenAI(model=model_name, max_tokens=self.config.max_tokens)
        elif provider == "ollama":
            lm = dspy.LM(
                model=f"ollama_chat/{model_name}",
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
        elif provider == "google":
            lm = dspy.Google(model=model_name, max_tokens=self.config.max_tokens)
        else:
            raise ValueError(f"Unknown DSPy language model provider: {provider}")

        dspy.settings.configure(lm=lm)

    async def translate_and_adapt(
        self, text: str, target_language: Language
    ) -> AsyncIterable[str]:

        self._logger.info(
            f"Using DSPy to translate and adapt via {self.config.provider}/{self.config.model}"
        )

        # DSPy doesn't natively expose an abstract Async Streaming API universally
        # across all of its module types out of the box without complex custom LM extensions.
        # So we process it entirely and yield the block.

        result = self.translator(
            target_language=get_language_name(target_language), raw_text=text
        )

        # Fake streaming behavior to maintain interface consistency
        content = result.adapted_script
        chunk_size = 20
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]
