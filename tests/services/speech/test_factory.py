import pytest
from unittest.mock import Mock

from src.services.speech_service import (
    SpeechServiceFactory, 
    AzureSpeechService, 
    CoquiSpeechService, 
    ElevenLabsSpeechService
)
from src.entities.config import MainConfig, SpeechConfig


@pytest.fixture
def main_config_with_azure_speech_config():
    """Config with new speech_config format"""
    config = MainConfig()
    config.speech_config = SpeechConfig(provider="azure")
    return config


@pytest.fixture
def main_config_with_coqui_speech_config():
    """Config specifically for Azure"""
    config = MainConfig()
    config.speech_config = SpeechConfig(provider="coqui")
    return config

@pytest.fixture
def main_config_with_elevenlabs_speech_config():
    """Config specifically for Coqui"""
    config = MainConfig()
    config.speech_config = SpeechConfig(provider="coqui")
    return config


@pytest.fixture
def config_with_elevenlabs():
    """Config specifically for ElevenLabs"""
    config = MainConfig()
    config.speech_config = SpeechConfig(provider="elevenlabs")
    return config


class TestSpeechServiceFactory:
    """Test Speech Service Factory"""

    def test_create_azure_service_explicit(self):
        """Test creating Azure service explicitly"""
        service = SpeechServiceFactory.create_speech_service("azure")
        assert isinstance(service, AzureSpeechService)

    def test_create_azure_service_default(self):
        """Test creating Azure service as default"""
        service = SpeechServiceFactory.create_speech_service()
        assert isinstance(service, AzureSpeechService)

    def test_create_coqui_service(self):
        """Test creating Coqui service"""
        service = SpeechServiceFactory.create_speech_service("coqui")
        assert isinstance(service, CoquiSpeechService)

    def test_create_elevenlabs_service(self):
        """Test creating ElevenLabs service"""
        service = SpeechServiceFactory.create_speech_service("elevenlabs")
        assert isinstance(service, ElevenLabsSpeechService)

    def test_create_service_from_new_config_format(self, main_config_with_coqui_speech_config):
        """Test creating service from new config format"""
        service = SpeechServiceFactory.create_speech_service(config=main_config_with_coqui_speech_config)
        assert isinstance(service, CoquiSpeechService)

    def test_create_azure_from_config(self, main_config_with_azure_speech_config):
        """Test creating Azure service from config"""
        service = SpeechServiceFactory.create_speech_service(config=main_config_with_azure_speech_config)
        assert isinstance(service, AzureSpeechService)

    def test_create_coqui_from_config(self, main_config_with_coqui_speech_config):
        """Test creating Coqui service from config"""
        service = SpeechServiceFactory.create_speech_service(config=main_config_with_coqui_speech_config)
        assert isinstance(service, CoquiSpeechService)

    def test_create_elevenlabs_from_config(self, config_with_elevenlabs):
        """Test creating ElevenLabs service from config"""
        service = SpeechServiceFactory.create_speech_service(config=config_with_elevenlabs)
        assert isinstance(service, ElevenLabsSpeechService)

    def test_config_overrides_provider_param(self, main_config_with_coqui_speech_config):
        """Test that config provider overrides the provider parameter"""
        # Pass 'azure' as provider but config has 'coqui'
        service = SpeechServiceFactory.create_speech_service("azure", main_config_with_coqui_speech_config)
        assert isinstance(service, CoquiSpeechService)

    def test_new_config_takes_precedence_over_old(self):
        """Test new config format takes precedence over old format"""
        config = MainConfig()
        config.speech_config = SpeechConfig(provider="coqui")  # New format
        
        service = SpeechServiceFactory.create_speech_service(config=config)
        assert isinstance(service, CoquiSpeechService)

    def test_case_insensitive_provider(self):
        """Test provider names are case insensitive"""
        services = [
            SpeechServiceFactory.create_speech_service("AZURE"),
            SpeechServiceFactory.create_speech_service("Azure"),
            SpeechServiceFactory.create_speech_service("azure"),
        ]
        
        assert all(isinstance(s, AzureSpeechService) for s in services)

    def test_unknown_provider_defaults_to_azure(self):
        """Test unknown provider defaults to Azure"""
        service = SpeechServiceFactory.create_speech_service("unknown_provider")
        assert isinstance(service, AzureSpeechService)

    def test_create_all_supported_providers(self):
        """Test creating all supported provider types"""
        providers = [
            ("azure", AzureSpeechService),
            ("coqui", CoquiSpeechService),
            ("elevenlabs", ElevenLabsSpeechService),
        ]
        
        for provider, expected_class in providers:
            service = SpeechServiceFactory.create_speech_service(provider)
            assert isinstance(service, expected_class)



    def test_config_without_any_speech_setting_defaults_azure(self):
        """Test config without any speech setting defaults to Azure"""
        config = MainConfig()
        # Don't set speech_provider or speech_config
        
        service = SpeechServiceFactory.create_speech_service(config=config)
        assert isinstance(service, CoquiSpeechService)


@pytest.mark.unit
class TestSpeechServiceFactoryEdgeCases:
    """Edge cases for Speech Service Factory"""

    def test_empty_provider_string(self):
        """Test empty provider string defaults to Azure"""
        service = SpeechServiceFactory.create_speech_service("")
        assert isinstance(service, AzureSpeechService)

    def test_none_provider(self):
        """Test None provider defaults to Azure"""
        service = SpeechServiceFactory.create_speech_service(None)
        assert isinstance(service, CoquiSpeechService)

    def test_whitespace_provider(self):
        """Test whitespace-only provider defaults to Azure"""
        service = SpeechServiceFactory.create_speech_service("   ")
        assert isinstance(service, AzureSpeechService)

    def test_config_with_empty_speech_config(self):
        """Test config with empty speech_config object"""
        config = MainConfig()
        config.speech_config = SpeechConfig(provider="")
        
        service = SpeechServiceFactory.create_speech_service(config=config)
        assert isinstance(service, AzureSpeechService)

    def test_config_with_none_speech_config(self):
        """Test config with None speech_config"""
        config = MainConfig()
        
        service = SpeechServiceFactory.create_speech_service(config=config)
        assert isinstance(service, CoquiSpeechService)

    def test_config_with_special_characters_in_provider(self):
        """Test config handles special characters in provider name"""
        config = MainConfig()
        config.speech_config = SpeechConfig(provider="azure@#$%")
        
        # Should default to Azure for invalid provider
        service = SpeechServiceFactory.create_speech_service(config=config)
        assert isinstance(service, AzureSpeechService)

    def test_mixed_case_in_config(self):
        """Test mixed case provider names in config"""
        test_cases = [
            ("ELEVENLABS", ElevenLabsSpeechService),
            ("CoquI", CoquiSpeechService),
            ("AzUrE", AzureSpeechService),
        ]
        
        for provider, expected_class in test_cases:
            config = MainConfig()
            config.speech_config = SpeechConfig(provider=provider)
            
            service = SpeechServiceFactory.create_speech_service(config=config)
            assert isinstance(service, expected_class)
