"""Tests for VideoService YouTube API key configuration"""

import pytest
from unittest.mock import Mock, patch
import os

from src.services.video_service import VideoService
from src.entities.config import MainConfig, VideoConfig


class TestVideoServiceConfiguration:
    """Test VideoService configuration handling"""

    def test_video_service_uses_config_api_key(self):
        """Test that VideoService uses API key from config when available"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = "test_config_api_key"
        
        with patch('src.services.video_service.build') as mock_build:
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_config_api_key")
            assert service._youtube_service is not None

    def test_video_service_falls_back_to_env_var(self):
        """Test that VideoService falls back to environment variable when config key is None"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = None
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_env_api_key'}):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_env_api_key")
            assert service._youtube_service is not None

    def test_video_service_no_api_key_available(self):
        """Test that VideoService handles case when no API key is available"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = None
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {}, clear=True):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_not_called()
            assert service._youtube_service is None

    def test_video_service_no_config_provided(self):
        """Test that VideoService falls back to env var when no config is provided"""
        # Arrange
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_env_api_key'}):
            # Act
            service = VideoService(config=None)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_env_api_key")
            assert service._youtube_service is not None

    def test_video_service_config_without_video_config(self):
        """Test that VideoService handles config without video_config attribute"""
        # Arrange
        config = Mock()
        config.video_config = None
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_env_api_key'}):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_env_api_key")
            assert service._youtube_service is not None

    def test_video_service_config_priority_over_env(self):
        """Test that config API key takes priority over environment variable"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = "config_key_priority"
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'env_key_fallback'}):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="config_key_priority")
            assert service._youtube_service is not None


class TestVideoServiceConfigurationEdgeCases:
    """Test edge cases for VideoService configuration"""

    def test_video_service_empty_config_api_key(self):
        """Test that empty string API key falls back to environment variable"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = ""
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_env_api_key'}):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_env_api_key")
            assert service._youtube_service is not None

    def test_video_service_whitespace_config_api_key(self):
        """Test that whitespace-only API key falls back to environment variable"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = "   "
        
        with patch('src.services.video_service.build') as mock_build, \
             patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_env_api_key'}):
            # Act
            service = VideoService(config=config)
            
            # Assert
            mock_build.assert_called_once_with("youtube", "v3", developerKey="test_env_api_key")
            assert service._youtube_service is not None

    def test_get_video_ids_without_youtube_service(self):
        """Test that _get_video_ids raises exception when YouTube service is not initialized"""
        # Arrange
        config = MainConfig()
        config.video_config = VideoConfig()
        config.video_config.youtube_api_key = None
        
        with patch.dict(os.environ, {}, clear=True):
            service = VideoService(config=config)
            
            # Act & Assert
            with pytest.raises(Exception, match="YouTube service not initialized"):
                service._get_video_ids("test_channel_id")

