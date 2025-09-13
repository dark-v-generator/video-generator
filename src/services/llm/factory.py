from ...core.config import settings
from .interfaces import ILLMService
from .openai_service import OpenAILLMService
from .local_llm_service import LocalLLMService
from src.core.logging_config import get_logger


class LLMServiceFactory:
    """Factory for creating LLM service instances"""

    @staticmethod
    def create_llm_service() -> ILLMService:
        """
        Create an LLM service instance based on the provider.

        Args:
            provider: The LLM provider to use ("openai", "local", "anthropic")
            config: Main configuration object

        Returns:
            An instance of ILLMService
        """
        logger = get_logger(__name__)
        # Explicit provider takes precedence, config is only used as fallback
        provider = settings.llm_provider

        logger.info(f"Creating LLM service for provider: {provider}")
        match provider:
            case "openai":
                return OpenAILLMService()
            case "local":
                return LocalLLMService()
            case _:
                raise ValueError(f"Invalid provider: {provider}")
