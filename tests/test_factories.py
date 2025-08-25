"""
Integration tests for all factory classes to ensure they work together properly.
Individual factory tests are in their respective modules.
"""

import pytest
from unittest.mock import Mock, patch

from src.services.llm.factory import LLMServiceFactory
from src.services.speech_service import SpeechServiceFactory
from src.entities.config import MainConfig, LLMConfig, SpeechConfig
from src.models.progress import ProgressEvent
from src.entities.history import History
from src.entities.language import Language


@pytest.fixture
def comprehensive_config():
    """Comprehensive config with all service configurations"""
    config = MainConfig()
    config.llm_config = LLMConfig(
        provider="openai",
        model="gpt-4o-mini", 
        temperature=0.7,
        max_tokens=2000
    )
    config.speech_config = SpeechConfig(
        provider="azure",
        default_voice="en-US-AriaNeural",
        default_rate=1.0
    )
    return config


class TestFactoryIntegration:
    """Integration tests for factory classes"""

    def test_all_llm_providers_can_be_created(self, comprehensive_config):
        """Test that all LLM providers can be instantiated"""
        providers = ["openai", "local", "anthropic"]
        
        for provider in providers:
            service = LLMServiceFactory.create_llm_service(provider, comprehensive_config)
            assert service is not None
            assert hasattr(service, 'enhance_history')
            assert hasattr(service, 'enhance_captions')
            assert hasattr(service, 'generate_engagement_phrase')
            assert hasattr(service, 'divide_history')

    def test_all_speech_providers_can_be_created(self, comprehensive_config):
        """Test that all Speech providers can be instantiated"""
        providers = ["azure", "coqui", "elevenlabs"]
        
        for provider in providers:
            service = SpeechServiceFactory.create_speech_service(provider, comprehensive_config)
            assert service is not None
            assert hasattr(service, 'generate_speech')

    def test_factories_respect_config_settings(self):
        """Test that factories respect configuration settings"""
        # Config with OpenAI LLM and ElevenLabs Speech
        config = MainConfig()
        config.llm_config = LLMConfig(provider="openai")
        config.speech_config = SpeechConfig(provider="elevenlabs")
        
        llm_service = LLMServiceFactory.create_llm_service(config=config)
        speech_service = SpeechServiceFactory.create_speech_service(config=config)
        
        # Verify correct services were created
        from src.services.llm.openai_service import OpenAILLMService
        from src.services.speech_service import ElevenLabsSpeechService
        
        assert isinstance(llm_service, OpenAILLMService)
        assert isinstance(speech_service, ElevenLabsSpeechService)

    def test_factories_handle_mismatched_configs(self):
        """Test factories handle mismatched old/new config formats"""
        config = MainConfig()
        config.speech_provider = "coqui"  # Old format
        config.speech_config = SpeechConfig(provider="azure")  # New format
        
        # Should use new format (azure)
        speech_service = SpeechServiceFactory.create_speech_service(config=config)
        
        from src.services.speech_service import AzureSpeechService
        assert isinstance(speech_service, AzureSpeechService)

    def test_factories_work_with_minimal_config(self):
        """Test factories work with minimal configuration"""
        minimal_config = MainConfig()
        
        llm_service = LLMServiceFactory.create_llm_service(config=minimal_config)
        speech_service = SpeechServiceFactory.create_speech_service(config=minimal_config)
        
        # Should create default services
        assert llm_service is not None
        assert speech_service is not None

    def test_factory_error_handling(self):
        """Test factories handle errors gracefully"""
        # Test with None config
        llm_service = LLMServiceFactory.create_llm_service("openai", None)
        speech_service = SpeechServiceFactory.create_speech_service("azure", None)
        
        assert llm_service is not None
        assert speech_service is not None

    def test_case_insensitive_across_factories(self, comprehensive_config):
        """Test that all factories handle case-insensitive provider names"""
        test_cases = [
            ("OPENAI", "AZURE"),
            ("OpenAI", "Azure"), 
            ("openai", "azure"),
            ("OpEnAi", "aZuRe")
        ]
        
        for llm_provider, speech_provider in test_cases:
            llm_service = LLMServiceFactory.create_llm_service(llm_provider, comprehensive_config)
            speech_service = SpeechServiceFactory.create_speech_service(speech_provider, comprehensive_config)
            
            assert llm_service is not None
            assert speech_service is not None

    def test_unknown_providers_default_behavior(self, comprehensive_config):
        """Test that unknown providers default to expected services"""
        # Unknown providers should default to OpenAI and Azure respectively
        llm_service = LLMServiceFactory.create_llm_service("unknown_llm", comprehensive_config)
        speech_service = SpeechServiceFactory.create_speech_service("unknown_speech", comprehensive_config)
        
        from src.services.llm.openai_service import OpenAILLMService
        from src.services.speech_service import AzureSpeechService
        
        assert isinstance(llm_service, OpenAILLMService)
        assert isinstance(speech_service, AzureSpeechService)


@pytest.mark.unit
class TestFactoryConfiguration:
    """Test factory configuration handling"""

    def test_config_precedence_llm(self):
        """Test LLM factory uses config when no provider specified"""
        config = MainConfig()
        config.llm_config = LLMConfig(provider="anthropic")
        
        # Config should be used when provider is None
        service = LLMServiceFactory.create_llm_service(None, config)
        
        from src.services.llm.anthropic_service import AnthropicLLMService
        assert isinstance(service, AnthropicLLMService)

    def test_config_precedence_speech(self):
        """Test Speech factory configuration precedence"""
        config = MainConfig()
        config.speech_config = SpeechConfig(provider="elevenlabs")
        
        # Config should override parameter  
        service = SpeechServiceFactory.create_speech_service("azure", config)
        
        from src.services.speech_service import ElevenLabsSpeechService
        assert isinstance(service, ElevenLabsSpeechService)

    def test_service_configuration_passed_correctly(self):
        """Test that configuration is passed correctly to services"""
        config = MainConfig()
        config.llm_config = LLMConfig(
            provider="openai",
            model="custom-model",
            temperature=0.9,
            max_tokens=5000
        )
        
        service = LLMServiceFactory.create_llm_service(config=config)
        
        assert service.config == config
        assert service.model == "custom-model"
        assert service.temperature == 0.9
        assert service.max_tokens == 5000




@pytest.mark.integration  
class TestFactoryServiceInteraction:
    """Test that services created by factories can interact properly"""

    @pytest.mark.asyncio
    async def test_llm_service_basic_functionality(self, comprehensive_config):
        """Test that LLM services created by factory have basic functionality"""
        service = LLMServiceFactory.create_llm_service("local", comprehensive_config)
        
        # Should be able to call methods without errors
        tokens = []
        async for token in service.enhance_history("Title", "Content", Language.ENGLISH):
            tokens.append(token)
            if len(tokens) >= 3:  # Just get a few tokens to verify it's working
                break
        
        # Should receive some tokens (strings)
        assert len(tokens) > 0
        assert all(isinstance(token, str) for token in tokens)

    @pytest.mark.asyncio 
    async def test_speech_service_basic_functionality(self, comprehensive_config):
        """Test that Speech services created by factory have basic functionality"""
        service = SpeechServiceFactory.create_speech_service("elevenlabs", comprehensive_config)
        
        # Should be able to call methods without immediate errors
        # (though actual functionality may require API keys)
        assert hasattr(service, 'generate_speech')
        assert callable(service.generate_speech)
