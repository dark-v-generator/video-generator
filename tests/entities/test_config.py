import pytest
from src.entities.config import MainConfig, LLMConfig, SpeechConfig, VideoConfig, CaptionsConfig, CoverConfig


class TestLLMConfig:
    """Test LLM Configuration"""

    def test_default_values(self):
        """Test LLM config default values"""
        config = LLMConfig()
        
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000

    def test_custom_values(self):
        """Test LLM config with custom values"""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-sonnet",
            temperature=0.5,
            max_tokens=4000
        )
        
        assert config.provider == "anthropic"
        assert config.model == "claude-3-sonnet"
        assert config.temperature == 0.5
        assert config.max_tokens == 4000

    def test_validation_bounds(self):
        """Test LLM config validation"""
        # Temperature should be between 0 and 1 (though pydantic doesn't enforce this by default)
        config = LLMConfig(temperature=1.5)
        assert config.temperature == 1.5  # Pydantic allows this, validation would be in service


class TestSpeechConfig:
    """Test Speech Configuration"""

    def test_default_values(self):
        """Test Speech config default values"""
        config = SpeechConfig()
        
        assert config.provider == "coqui"
        assert config.default_voice == ""
        assert config.default_rate == 1.0

    def test_custom_values(self):
        """Test Speech config with custom values"""
        config = SpeechConfig(
            provider="elevenlabs",
            default_voice="rachel",
            default_rate=1.2
        )
        
        assert config.provider == "elevenlabs"
        assert config.default_voice == "rachel"
        assert config.default_rate == 1.2

    def test_different_providers(self):
        """Test different speech providers"""
        providers = ["azure", "coqui", "elevenlabs"]
        
        for provider in providers:
            config = SpeechConfig(provider=provider)
            assert config.provider == provider


class TestMainConfig:
    """Test Main Configuration"""

    def test_default_initialization(self):
        """Test main config default initialization"""
        config = MainConfig()
        
        assert isinstance(config.llm_config, LLMConfig)
        assert isinstance(config.speech_config, SpeechConfig)
        assert isinstance(config.video_config, VideoConfig)
        assert isinstance(config.captions_config, CaptionsConfig)
        assert isinstance(config.cover_config, CoverConfig)
        
        assert config.seed is None

    def test_llm_config_integration(self):
        """Test LLM config integration in main config"""
        config = MainConfig()
        config.llm_config.provider = "anthropic"
        config.llm_config.model = "claude-3-haiku"
        
        assert config.llm_config.provider == "anthropic"
        assert config.llm_config.model == "claude-3-haiku"

    def test_speech_config_integration(self):
        """Test Speech config integration in main config"""
        config = MainConfig()
        config.speech_config.provider = "coqui"
        config.speech_config.default_rate = 1.5
        
        assert config.speech_config.provider == "coqui"
        assert config.speech_config.default_rate == 1.5

    def test_custom_seed(self):
        """Test custom seed"""
        config = MainConfig()
        config.seed = "CUSTOM_SEED_123"
        
        assert config.seed == "CUSTOM_SEED_123"

    def test_int_seed_generation(self):
        """Test int_seed method"""
        config = MainConfig()
        config.seed = "TESTSEED"
        
        int_seed = config.int_seed()
        
        assert isinstance(int_seed, int)
        assert int_seed > 0

    def test_int_seed_consistency(self):
        """Test int_seed method returns consistent results"""
        config = MainConfig()
        config.seed = "CONSISTENT_SEED"
        
        seed1 = config.int_seed()
        seed2 = config.int_seed()
        
        assert seed1 == seed2

    def test_different_seeds_produce_different_ints(self):
        """Test different string seeds produce different integer seeds"""
        config1 = MainConfig()
        config1.seed = "SEED_ONE"
        
        config2 = MainConfig()
        config2.seed = "SEED_TWO"
        
        assert config1.int_seed() != config2.int_seed()

    def test_nested_config_modification(self):
        """Test modifying nested configurations"""
        config = MainConfig()
        
        # Modify LLM config
        config.llm_config = LLMConfig(
            provider="local",
            model="llama-3.1",
            temperature=0.3,
            max_tokens=8000
        )
        
        # Modify Speech config
        config.speech_config = SpeechConfig(
            provider="azure",
            default_voice="pt-BR-AntonioNeural",
            default_rate=0.9
        )
        
        assert config.llm_config.provider == "local"
        assert config.llm_config.model == "llama-3.1"
        assert config.speech_config.provider == "azure"
        assert config.speech_config.default_voice == "pt-BR-AntonioNeural"


@pytest.mark.unit
class TestConfigEdgeCases:
    """Edge cases for configuration models"""

    def test_empty_string_values(self):
        """Test configuration with empty string values"""
        llm_config = LLMConfig(provider="", model="")
        speech_config = SpeechConfig(provider="", default_voice="")
        
        assert llm_config.provider == ""
        assert llm_config.model == ""
        assert speech_config.provider == ""
        assert speech_config.default_voice == ""

    def test_extreme_numeric_values(self):
        """Test configuration with extreme numeric values"""
        llm_config = LLMConfig(temperature=0.0, max_tokens=1)
        speech_config = SpeechConfig(default_rate=0.1)
        
        assert llm_config.temperature == 0.0
        assert llm_config.max_tokens == 1
        assert speech_config.default_rate == 0.1

    def test_unicode_in_string_fields(self):
        """Test configuration with unicode characters"""
        config = MainConfig()
        config.seed = "SEED_WITH_ÀCCÉNTS_ÄÖÜ"
        
        assert "ÀCCÉNTS" in config.seed

    def test_very_long_strings(self):
        """Test configuration with very long strings"""
        long_seed = "SEED_" + "A" * 1000
        
        config = MainConfig()
        config.seed = long_seed
        
        assert len(config.seed) > 1000

    def test_special_characters_in_config(self):
        """Test configuration with special characters"""
        speech_config = SpeechConfig(
            provider="azure",
            default_voice="voice-with-dashes_and_underscores.v1"
        )
        
        assert "dashes_and_underscores" in speech_config.default_voice

    def test_config_serialization_compatibility(self):
        """Test that configs can be serialized (important for YAML/JSON)"""
        config = MainConfig()
        config.llm_config.provider = "anthropic"
        config.speech_config.provider = "elevenlabs"
        
        # Should be able to convert to dict (pydantic feature)
        config_dict = config.model_dump()
        
        assert isinstance(config_dict, dict)
        assert config_dict["llm_config"]["provider"] == "anthropic"
        assert config_dict["speech_config"]["provider"] == "elevenlabs"

