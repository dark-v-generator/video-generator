import pytest
from unittest.mock import Mock

from src.services.config_service import ConfigService
from src.repositories.interfaces import IConfigRepository, IFileRepository
from src.entities.config import MainConfig, LLMConfig, SpeechConfig


@pytest.fixture
def mock_config_repository():
    """Mock config repository"""
    mock = Mock(spec=IConfigRepository)
    mock.load_config = Mock()
    mock.save_config = Mock()
    mock.config_exists = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_file_repository():
    """Mock file repository"""
    mock = Mock(spec=IFileRepository)
    mock.save_file = Mock()
    mock.load_file = Mock()
    mock.delete_file = Mock()
    mock.file_exists = Mock(return_value=True)
    mock.create_directory = Mock()
    mock.list_files = Mock()
    mock.get_file_url = Mock()
    return mock


@pytest.fixture
def config_service(mock_config_repository, mock_file_repository):
    """Config service with mocked repositories"""
    return ConfigService(mock_config_repository, mock_file_repository)


@pytest.fixture
def sample_main_config():
    """Sample main configuration"""
    config = MainConfig()
    config.llm_config = LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.8,
        max_tokens=1500
    )
    config.speech_config = SpeechConfig(
        provider="azure",
        default_voice="en-US-AriaNeural",
        default_rate=1.0
    )
    config.seed = "TESTINGSEED"
    return config


class TestConfigService:
    """Test Config Service"""

    def test_init(self, config_service, mock_config_repository, mock_file_repository):
        """Test service initialization"""
        assert config_service._config_repository == mock_config_repository
        assert config_service._file_repository == mock_file_repository

    def test_get_main_config_success(self, config_service, mock_config_repository, sample_main_config):
        """Test successful retrieval of main config"""
        mock_config_repository.config_exists.return_value = True  # Config exists
        mock_config_repository.load_config.return_value = sample_main_config
        
        result = config_service.get_main_config()
        
        # Should just load existing config, no saving needed
        mock_config_repository.save_config.assert_not_called()
        assert result == sample_main_config
        assert result.llm_config.provider == "openai"
        assert result.speech_config.provider == "azure"
        mock_config_repository.load_config.assert_called_once()

    def test_get_main_config_when_not_exists(self, config_service, mock_config_repository):
        """Test get_main_config when config doesn't exist (creates new one)"""
        mock_config_repository.config_exists.return_value = False
        # Mock load_config to return a valid MainConfig after save
        mock_config_repository.load_config.return_value = MainConfig()
        
        result = config_service.get_main_config()
        
        # Should save a new config and then load it
        mock_config_repository.save_config.assert_called_once()
        mock_config_repository.load_config.assert_called_once()

    def test_get_main_config_when_exists(self, config_service, mock_config_repository, sample_main_config):
        """Test get_main_config when config exists"""
        mock_config_repository.config_exists.return_value = True
        mock_config_repository.load_config.return_value = sample_main_config
        
        result = config_service.get_main_config()
        
        # Should just load existing config
        mock_config_repository.save_config.assert_not_called()
        mock_config_repository.load_config.assert_called_once()
        assert result == sample_main_config

    def test_save_main_config_success(self, config_service, mock_config_repository, sample_main_config):
        """Test successful saving of main config"""
        config_dict = {
            "llm_config": {
                "provider": "anthropic",
                "model": "claude-3-sonnet",
                "temperature": 0.5,
                "max_tokens": 2500
            },
            "speech_config": {
                "provider": "elevenlabs",
                "default_voice": "rachel",
                "default_rate": 1.2
            },
            "seed": "NEWSEED123"
        }
        
        result = config_service.save_main_config(config_dict)
        
        # Should create MainConfig and save it
        mock_config_repository.save_config.assert_called_once()
        saved_config = mock_config_repository.save_config.call_args[0][0]
        assert isinstance(saved_config, MainConfig)
        assert isinstance(result, MainConfig)

    def test_save_main_config_with_partial_dict(self, config_service, mock_config_repository, sample_main_config):
        """Test saving config with partial dictionary"""
        partial_config = {
            "seed": "PARTIALSEED"
        }
        
        result = config_service.save_main_config(partial_config)
        
        # Should create MainConfig and save it
        mock_config_repository.save_config.assert_called_once()
        saved_config = mock_config_repository.save_config.call_args[0][0]
        assert isinstance(saved_config, MainConfig)
        assert isinstance(result, MainConfig)

    def test_save_main_config_handles_repository_error(self, config_service, mock_config_repository):
        """Test save_main_config handles repository errors"""
        config_dict = {"seed": "TESTINGSEED"}
        mock_config_repository.save_config.side_effect = Exception("Save failed")
        
        with pytest.raises(Exception, match="Save failed"):
            config_service.save_main_config(config_dict)

    def test_config_caching_behavior(self, config_service, mock_config_repository, sample_main_config):
        """Test that config service doesn't cache (loads fresh each time)"""
        mock_config_repository.load_config.return_value = sample_main_config
        
        # Call multiple times
        config1 = config_service.get_main_config()
        config2 = config_service.get_main_config()
        
        # Should call repository each time (no caching)
        assert mock_config_repository.load_config.call_count == 2
        assert config1 == sample_main_config
        assert config2 == sample_main_config

    def test_empty_config_dict_handling(self, config_service, mock_config_repository, sample_main_config):
        """Test saving empty config dictionary"""
        empty_dict = {}
        
        result = config_service.save_main_config(empty_dict)
        
        # Should create default MainConfig and save it
        mock_config_repository.save_config.assert_called_once()

    def test_config_property(self, config_service, mock_config_repository, sample_main_config):
        """Test the config property for dependency injection compatibility"""
        mock_config_repository.config_exists.return_value = True
        mock_config_repository.load_config.return_value = sample_main_config
        
        # Access config via property
        result = config_service.config
        
        assert isinstance(result, MainConfig)
        assert result == sample_main_config
        mock_config_repository.load_config.assert_called_once()

    def test_save_file(self, config_service, mock_file_repository):
        """Test saving a file"""
        file_content = b"fake file content"
        filename = "test.png"
        file_type = "watermark"
        
        result = config_service.save_file(file_content, filename, file_type)
        
        # Should save file and return path
        mock_file_repository.save_file.assert_called_once()
        assert result.startswith("uploads/watermark")
        assert result.endswith(".png")

    def test_get_file_url_existing_file(self, config_service, mock_file_repository):
        """Test getting URL for existing file"""
        file_path = "uploads/watermark.png"
        mock_file_repository.get_file_url.return_value = "/api/files/uploads/watermark.png"
        
        result = config_service.get_file_url(file_path)
        
        mock_file_repository.get_file_url.assert_called_once_with(file_path)
        assert result == "/api/files/uploads/watermark.png"

    def test_get_file_url_nonexistent_file(self, config_service, mock_file_repository):
        """Test getting URL for nonexistent file"""
        file_path = "uploads/nonexistent.png"
        mock_file_repository.get_file_url.side_effect = FileNotFoundError("File not found")
        
        result = config_service.get_file_url(file_path)
        
        mock_file_repository.get_file_url.assert_called_once_with(file_path)
        assert result is None

    def test_get_file_url_none_path(self, config_service):
        """Test getting URL for None file path"""
        result = config_service.get_file_url(None)
        assert result is None


@pytest.mark.unit
class TestConfigServiceEdgeCases:
    """Edge cases for Config Service"""

    def test_none_config_dict(self, config_service, mock_config_repository, sample_main_config):
        """Test saving None as config dictionary"""
        result = config_service.save_main_config(None)
        
        # Should create MainConfig and save it (None gets converted to empty dict)
        mock_config_repository.save_config.assert_called_once()
        saved_config = mock_config_repository.save_config.call_args[0][0]
        assert isinstance(saved_config, MainConfig)
        assert isinstance(result, MainConfig)

    def test_large_config_dict(self, config_service, mock_config_repository, sample_main_config):
        """Test saving very large config dictionary"""
        large_dict = {
            f"key_{i}": f"value_{i}" for i in range(1000)
        }
        large_dict.update({
            "llm_config": {"provider": "openai", "model": "gpt-4"},
            "speech_config": {"provider": "azure"}
        })
        
        # Service handles config creation
        
        result = config_service.save_main_config(large_dict)
        
        # Should create MainConfig and save it
        mock_config_repository.save_config.assert_called_once()
        assert isinstance(result, MainConfig)

    def test_config_with_nested_structures(self, config_service, mock_config_repository, sample_main_config):
        """Test saving config with deeply nested structures"""
        nested_config = {
            "llm_config": {
                "provider": "openai",
                "advanced_settings": {
                    "retry_config": {
                        "max_retries": 3,
                        "backoff_factor": 2.0,
                        "timeouts": [1, 2, 4, 8]
                    },
                    "model_overrides": {
                        "portuguese": "gpt-4o-mini-pt",
                        "english": "gpt-4o-mini-en"
                    }
                }
            }
        }
        
        # Service handles config creation
        
        result = config_service.save_main_config(nested_config)
        
        # Should create MainConfig and save it
        mock_config_repository.save_config.assert_called_once()
        assert isinstance(result, MainConfig)

    def test_config_with_special_characters(self, config_service, mock_config_repository, sample_main_config):
        """Test saving config with special characters"""
        special_config = {
            "custom_field": "Value with special chars: !@#$%^&*()",
            "unicode_test": "测试中文字符",
            "seed": "SEED_WITH_UNDERSCORE_123"
        }
        
        # Service handles config creation
        
        result = config_service.save_main_config(special_config)
        
        # Should create MainConfig and save it
        mock_config_repository.save_config.assert_called_once()
        assert isinstance(result, MainConfig)

    def test_repository_returns_invalid_type(self, config_service, mock_config_repository):
        """Test handling when repository returns invalid type"""
        # Repository returns a string instead of MainConfig
        mock_config_repository.load_config.return_value = "invalid_config"
        
        # Service should handle this gracefully and return default
        result = config_service.get_main_config()
        
        assert isinstance(result, MainConfig)

    def test_concurrent_config_operations(self, config_service, mock_config_repository, sample_main_config):
        """Test concurrent config get/save operations"""
        import threading
        import time
        
        mock_config_repository.load_config.return_value = sample_main_config
        # Service handles config creation
        
        results = []
        
        def get_config():
            time.sleep(0.01)  # Small delay to increase chance of race condition
            results.append(config_service.get_main_config())
        
        def save_config():
            time.sleep(0.01)
            results.append(config_service.save_main_config({"test": "value"}))
        
        # Run operations concurrently
        threads = [
            threading.Thread(target=get_config),
            threading.Thread(target=save_config),
            threading.Thread(target=get_config)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should complete successfully
        assert len(results) == 3
        assert all(isinstance(r, MainConfig) for r in results)
