import pytest
from unittest.mock import Mock

from src.services.llm.factory import LLMServiceFactory
from src.services.llm.openai_service import OpenAILLMService
from src.services.llm.local_llm_service import LocalLLMService
from src.services.llm.anthropic_service import AnthropicLLMService
from src.entities.config import MainConfig, LLMConfig


@pytest.fixture
def main_config():
    """Test main configuration"""
    return MainConfig()


class TestLLMServiceFactory:
    """Test LLM Service Factory"""

    def test_create_openai_service_explicit(self, main_config):
        """Test creating OpenAI service explicitly"""
        service = LLMServiceFactory.create_llm_service("openai", main_config)
        
        assert isinstance(service, OpenAILLMService)
        assert service.config == main_config

    def test_create_openai_service_default(self, main_config):
        """Test creating OpenAI service as default"""
        service = LLMServiceFactory.create_llm_service(config=main_config)
        
        assert isinstance(service, OpenAILLMService)
        assert service.config == main_config

    def test_create_local_service(self, main_config):
        """Test creating local LLM service"""
        service = LLMServiceFactory.create_llm_service("local", main_config)
        
        assert isinstance(service, LocalLLMService)
        assert service.config == main_config

    def test_create_anthropic_service(self, main_config):
        """Test creating Anthropic service"""
        service = LLMServiceFactory.create_llm_service("anthropic", main_config)
        
        assert isinstance(service, AnthropicLLMService)
        assert service.config == main_config

    def test_create_service_case_insensitive(self, main_config):
        """Test provider names are case insensitive"""
        service1 = LLMServiceFactory.create_llm_service("OPENAI", main_config)
        service2 = LLMServiceFactory.create_llm_service("OpenAI", main_config)
        service3 = LLMServiceFactory.create_llm_service("openai", main_config)
        
        assert all(isinstance(s, OpenAILLMService) for s in [service1, service2, service3])

    def test_unknown_provider_defaults_to_openai(self, main_config):
        """Test unknown provider defaults to OpenAI"""
        service = LLMServiceFactory.create_llm_service("unknown_provider", main_config)
        
        assert isinstance(service, OpenAILLMService)

    def test_create_service_without_config(self):
        """Test creating service without configuration"""
        service = LLMServiceFactory.create_llm_service("openai", None)
        
        assert isinstance(service, OpenAILLMService)
        assert service.config is None

    def test_create_all_supported_providers(self, main_config):
        """Test creating all supported provider types"""
        providers = [
            ("openai", OpenAILLMService),
            ("local", LocalLLMService),
            ("anthropic", AnthropicLLMService),
        ]
        
        for provider, expected_class in providers:
            service = LLMServiceFactory.create_llm_service(provider, main_config)
            assert isinstance(service, expected_class)
            assert service.config == main_config


@pytest.mark.unit
class TestLLMServiceFactoryEdgeCases:
    """Edge cases for LLM Service Factory"""

    def test_empty_provider_string(self, main_config):
        """Test empty provider string defaults to OpenAI"""
        service = LLMServiceFactory.create_llm_service("", main_config)
        assert isinstance(service, OpenAILLMService)

    def test_none_provider(self, main_config):
        """Test None provider defaults to OpenAI"""
        service = LLMServiceFactory.create_llm_service(None, main_config)
        assert isinstance(service, OpenAILLMService)

    def test_whitespace_provider(self, main_config):
        """Test whitespace-only provider defaults to OpenAI"""
        service = LLMServiceFactory.create_llm_service("   ", main_config)
        assert isinstance(service, OpenAILLMService)
