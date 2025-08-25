from ...repositories.interfaces import IConfigRepository
from .interfaces import ILLMService
from .openai_service import OpenAILLMService
from .local_llm_service import LocalLLMService
from src.core.logging_config import get_logger


class LLMServiceFactory:
    """Factory for creating LLM service instances"""

    @staticmethod
    def create_llm_service(config_repository: IConfigRepository) -> ILLMService:
        _logger = get_logger(__name__)
        """
        Create an LLM service instance based on the provider.

        Args:
            provider: The LLM provider to use ("openai", "local", "anthropic")
            config: Main configuration object

        Returns:
            An instance of ILLMService
        """
        # Explicit provider takes precedence, config is only used as fallback
        provider = config_repository.load_config().llm_config.provider

        _logger.info(f"Creating LLM service for provider: {provider}")
        if provider == "openai":
            return OpenAILLMService(config_repository)
        elif provider == "local":
            return LocalLLMService(config_repository)
        else:
            raise ValueError(f"Invalid provider: {provider}")
