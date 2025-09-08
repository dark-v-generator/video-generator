import pytest
from unittest.mock import Mock, patch, AsyncMock, mock_open
from src.services.video_service import VideoService
from src.models.progress import ProgressEvent
from src.entities.editor.video_clip import VideoClip
from src.entities.editor.audio_clip import AudioClip
from src.entities.editor.image_clip import ImageClip
from src.entities.editor.captions_clip import CaptionsClip


class TestVideoService:
    """Test VideoService functionality"""
    
    @pytest.fixture
    def service(self):
        with patch('src.services.video_service.build') as mock_build:
            mock_youtube_service = Mock()
            mock_build.return_value = mock_youtube_service
            return VideoService()
    
    @pytest.mark.asyncio
    async def test_create_video_compilation_success(self, service):
        """Test successful video compilation creation"""
        # Arrange
        mock_video_ids = ["video1", "video2", "video3"]
        
        mock_video = Mock()
        mock_video.clip.duration = 10.0
        
        mock_config = Mock()
        mock_config.youtube_channel_id = "test_channel"
        mock_config.low_quality = False
        
        # Mock the internal methods of the service
        with patch.object(service, '_get_video_ids', return_value=mock_video_ids) as mock_get_ids:
            with patch.object(service, '_download_youtube_video') as mock_download:
                # Mock the async generator for _download_youtube_video - now returns bytes
                async def mock_download_gen(video_id, low_quality):
                    yield ProgressEvent.create("downloading", f"Downloading {video_id}", progress=50)
                    yield b"fake_video_bytes"  # Return bytes instead of VideoClip
                
                mock_download.side_effect = mock_download_gen
                
                with patch('src.services.video_service.video_clip.VideoClip') as mock_video_clip_class:
                    mock_video_clip = Mock()
                    mock_video_clip.clip.duration = 10.0  # Set a numeric duration
                    mock_video_clip_class.return_value = mock_video_clip
                    
                    # Act
                    events = []
                    final_result = None
                    async for event in service.create_video_compilation(30, mock_config):
                        if isinstance(event, ProgressEvent):
                            events.append(event)
                        else:
                            final_result = event
                    
                    # Assert
                    assert len(events) >= 4  # initializing, fetching, downloading, completed
                    assert events[0].stage == "initializing"
                    assert events[0].progress == 0
                    
                    # Find the completed event
                    completed_events = [e for e in events if e.stage == "completed"]
                    assert len(completed_events) > 0
                    assert completed_events[0].progress == 100
                    
                    assert final_result is not None
                    assert final_result == mock_video_clip
                    
                    # Verify internal method calls
                    mock_get_ids.assert_called_once_with("test_channel", max_results=500)
                    assert mock_download.call_count >= 3  # Should download at least 3 videos
    
    @pytest.mark.asyncio
    async def test_create_video_compilation_with_default_config(self, service):
        """Test video compilation with default config"""
        # Arrange
        mock_video = Mock()
        mock_video.clip.duration = 50.0  # Long enough to exceed min_duration
        
        with patch.object(service, '_get_video_ids', return_value=["video1"]) as mock_get_ids:
            with patch.object(service, '_download_youtube_video') as mock_download:
                # Mock the async generator - now returns bytes
                async def mock_download_gen(video_id, low_quality):
                    yield ProgressEvent.create("downloading", f"Downloading {video_id}", progress=50)
                    yield b"fake_video_bytes"  # Return bytes instead of VideoClip
                
                mock_download.side_effect = mock_download_gen
                
                with patch('src.services.video_service.video_clip.VideoClip') as mock_video_clip_class:
                    mock_video_clip = Mock()
                    mock_video_clip.clip.duration = 50.0  # Set a numeric duration
                    mock_video_clip_class.return_value = mock_video_clip
                    
                    with patch('src.entities.config.VideoConfig') as mock_config_class:
                        mock_config = Mock()
                        mock_config.youtube_channel_id = "default_channel"
                        mock_config.low_quality = False
                        mock_config_class.return_value = mock_config
                        
                        # Act
                        events = []
                        async for event in service.create_video_compilation(30, None):  # None config
                            if isinstance(event, ProgressEvent):
                                events.append(event)
                        
                        # Assert
                        assert len(events) >= 4
                        mock_config_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_video_compilation_error_handling(self, service):
        """Test error handling in video compilation"""
        # Arrange
        with patch.object(service, '_get_video_ids', side_effect=Exception("YouTube API error")):
            # Act
            events = []
            exception_raised = False
            try:
                async for event in service.create_video_compilation(30, None):
                    if isinstance(event, ProgressEvent):
                        events.append(event)
                        if event.stage == "error":
                            # Continue to get the exception
                            continue
            except Exception as e:
                exception_raised = True
                assert "YouTube API error" in str(e)
            
            # Assert
            assert exception_raised, "Expected exception to be raised"
            error_events = [e for e in events if e.stage == "error"]
            assert len(error_events) > 0
            assert "YouTube API error" in error_events[0].message
    
    def test_generate_video_success(self, service):
        """Test successful video generation with all components"""
        # Arrange
        mock_audio = Mock(spec=AudioClip)
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        mock_background = Mock()
        mock_background.clip.size = (1920, 1080)
        
        mock_cover = Mock(spec=ImageClip)
        mock_captions = Mock(spec=CaptionsClip)
        
        mock_config = Mock()
        mock_config.end_silece_seconds = 2
        mock_config.width = 1920
        mock_config.height = 1080
        mock_config.padding = 20
        mock_config.cover_duration = 5
        mock_config.watermark_path = None
        
        # Act
        result = service.generate_video(
            audio=mock_audio,
            background_video=mock_background,
            cover=mock_cover,
            captions=mock_captions,
            config=mock_config
        )
        
        # Assert
        assert result == mock_background
        mock_audio.add_end_silence.assert_called_once_with(2)
        mock_background.resize.assert_called_once_with(1920, 1080)
        mock_background.ajust_duration.assert_called_once_with(30.0)
        mock_background.set_audio.assert_called_once_with(mock_audio)
        mock_background.merge.assert_called()  # Should be called for cover
        mock_background.insert_captions.assert_called_once_with(mock_captions)
    
    def test_generate_video_with_watermark(self, service):
        """Test video generation with watermark"""
        # Arrange
        mock_audio = Mock(spec=AudioClip)
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        mock_background = Mock()
        mock_background.clip.size = (1920, 1080)
        
        mock_config = Mock()
        mock_config.end_silece_seconds = 2
        mock_config.width = 1920
        mock_config.height = 1080
        mock_config.padding = 20
        mock_config.cover_duration = 5
        mock_config.watermark_path = "/path/to/watermark.png"
        
        with patch('src.services.video_service.image_clip.ImageClip') as mock_image_clip:
            mock_watermark = Mock()
            mock_image_clip.return_value = mock_watermark
            
            # Act
            result = service.generate_video(
                audio=mock_audio,
                background_video=mock_background,
                config=mock_config
            )
            
            # Assert
            mock_image_clip.assert_called_once_with("/path/to/watermark.png")
            mock_watermark.fit_width.assert_called_once_with(1920, 20)
            mock_watermark.center.assert_called_once_with(1920, 1080)
            mock_watermark.set_duration.assert_called_once_with(30.0)
            assert mock_background.merge.call_count == 1  # Called for watermark
    
    def test_generate_video_minimal_components(self, service):
        """Test video generation with minimal components (no cover, no captions)"""
        # Arrange
        mock_audio = Mock(spec=AudioClip)
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        mock_background = Mock()
        mock_background.clip.size = (1920, 1080)
        
        mock_config = Mock()
        mock_config.end_silece_seconds = 2
        mock_config.width = 1920
        mock_config.height = 1080
        mock_config.watermark_path = None
        
        # Act
        result = service.generate_video(
            audio=mock_audio,
            background_video=mock_background,
            config=mock_config
        )
        
        # Assert
        assert result == mock_background
        mock_background.merge.assert_not_called()  # No cover or watermark
        mock_background.insert_captions.assert_not_called()  # No captions


class TestVideoServiceEdgeCases:
    """Edge cases for VideoService"""
    
    @pytest.fixture
    def service(self):
        with patch('src.services.video_service.build') as mock_build:
            mock_youtube_service = Mock()
            mock_build.return_value = mock_youtube_service
            return VideoService()
    
    @pytest.mark.asyncio
    async def test_create_video_compilation_empty_video_list(self, service):
        """Test video compilation with empty video list"""
        # Arrange
        with patch.object(service, '_get_video_ids', return_value=[]):
            with patch('src.services.video_service.video_clip.VideoClip') as mock_video_clip_class:
                mock_video_clip = Mock()
                mock_video_clip.clip.duration = 0.0  # Empty video list should have 0 duration
                mock_video_clip_class.return_value = mock_video_clip
                
                # Create a mock config since None will cause issues
                mock_config = Mock()
                mock_config.youtube_channel_id = "test_channel"
                mock_config.low_quality = False
                
                # Act
                events = []
                final_result = None
                async for event in service.create_video_compilation(30, mock_config):
                    if isinstance(event, ProgressEvent):
                        events.append(event)
                    else:
                        final_result = event
                
                # Assert
                assert len(events) >= 3  # initializing, fetching, completed
                assert final_result == mock_video_clip  # Should return empty video clip
    
    @pytest.mark.asyncio
    async def test_create_video_compilation_short_videos(self, service):
        """Test video compilation where individual videos are very short"""
        # Arrange
        mock_video_ids = ["v1", "v2", "v3", "v4", "v5", "v6", "v7"]
        
        # Create short videos that require multiple to reach min_duration
        mock_video = Mock()
        mock_video.clip.duration = 5.0  # Each video is 5 seconds
        
        mock_config = Mock()
        mock_config.youtube_channel_id = "test_channel"
        mock_config.low_quality = False
        
        with patch.object(service, '_get_video_ids', return_value=mock_video_ids):
            with patch.object(service, '_download_youtube_video') as mock_download:
                # Mock the async generator - now returns bytes
                async def mock_download_gen(video_id, low_quality):
                    yield ProgressEvent.create("downloading", f"Downloading {video_id}", progress=50)
                    yield b"fake_video_bytes"  # Return bytes instead of VideoClip
                
                mock_download.side_effect = mock_download_gen
                
                with patch('src.services.video_service.video_clip.VideoClip') as mock_video_clip_class:
                    mock_video_clip = Mock()
                    mock_video_clip.clip.duration = 5.0  # Set a numeric duration
                    mock_video_clip_class.return_value = mock_video_clip
                    
                    # Act
                    events = []
                    async for event in service.create_video_compilation(30, mock_config):  # Need 30 seconds
                        if isinstance(event, ProgressEvent):
                            events.append(event)
                    
                    # Assert
                    # Should download multiple videos to reach 30 seconds (at least 6 videos)
                    assert mock_download.call_count >= 6
                    assert mock_video_clip.concat.call_count >= 6
    
    def test_generate_video_with_default_config(self, service):
        """Test video generation with default config"""
        # Arrange
        mock_audio = Mock(spec=AudioClip)
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        mock_background = Mock()
        mock_background.clip.size = (1920, 1080)
        
        with patch('src.entities.config.VideoConfig') as mock_config_class:
            mock_config = Mock()
            mock_config.end_silece_seconds = 2
            mock_config.width = 1920
            mock_config.height = 1080
            mock_config.watermark_path = None
            mock_config_class.return_value = mock_config
            
            # Act
            result = service.generate_video(
                audio=mock_audio,
                background_video=mock_background,
                config=None  # Default config
            )
            
            # Assert
            mock_config_class.assert_called_once()
            assert result == mock_background


class TestVideoServiceDownloadMethod:
    """Test the _download_youtube_video method specifically"""
    
    @pytest.fixture
    def service(self):
        with patch('src.services.video_service.build') as mock_build:
            mock_youtube_service = Mock()
            mock_build.return_value = mock_youtube_service
            return VideoService()
    
    @pytest.mark.asyncio
    async def test_download_youtube_video_success(self, service):
        """Test successful YouTube video download"""
        with patch('src.services.video_service.YouTube') as mock_youtube_class:
            with patch('src.services.video_service.tempfile.NamedTemporaryFile') as mock_temp:
                with patch('builtins.open', mock_open(read_data=b"fake_video_bytes")) as mock_file:
                    # Arrange
                    mock_yt = Mock()
                    mock_yt.title = "Test Video"
                    mock_youtube_class.return_value = mock_yt
                    
                    mock_stream = Mock()
                    mock_stream.filesize = 1000000
                    mock_stream.title = "Test Video"
                    mock_stream.video_id = "test_video_id"
                    mock_yt.streams.filter.return_value.order_by.return_value.desc.return_value.first.return_value = mock_stream
                    
                    mock_temp_file = Mock()
                    mock_temp_file.name = "/tmp/test.mp4"
                    mock_temp.return_value.__enter__.return_value = mock_temp_file
                    
                    # Act
                    events = []
                    final_result = None
                    async for event in service._download_youtube_video("test_video_id", False):
                        if isinstance(event, ProgressEvent):
                            events.append(event)
                        else:
                            final_result = event
                    
                    # Assert
                    # Note: Progress events may not be generated in test due to mocking
                    assert final_result == b"fake_video_bytes"
                    
                    # Verify YouTube API calls
                    mock_youtube_class.assert_called_once_with("https://www.youtube.com/watch?v=test_video_id", "WEB_CREATOR", use_oauth=True)
                    mock_stream.download.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_youtube_video_low_quality(self, service):
        """Test YouTube video download with low quality"""
        with patch('src.services.video_service.YouTube') as mock_youtube_class:
            with patch('src.services.video_service.tempfile.NamedTemporaryFile'):
                with patch('builtins.open', mock_open(read_data=b"fake_video_bytes")):
                    # Arrange
                    mock_yt = Mock()
                    mock_yt.title = "Test Video"
                    mock_youtube_class.return_value = mock_yt
                    
                    mock_stream = Mock()
                    mock_stream.filesize = 1000000
                    mock_stream.title = "Test Video"
                    mock_stream.video_id = "test_video_id"
                    mock_yt.streams.filter.return_value.order_by.return_value.desc.return_value.last.return_value = mock_stream
                    
                    # Act
                    events = []
                    async for event in service._download_youtube_video("test_video_id", True):  # low_quality=True
                        if isinstance(event, ProgressEvent):
                            events.append(event)
                    
                    # Assert
                    mock_yt.streams.filter.return_value.order_by.return_value.desc.return_value.last.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_youtube_video_no_streams(self, service):
        """Test YouTube video download when no streams are available"""
        with patch('src.services.video_service.YouTube') as mock_youtube_class:
            # Arrange
            mock_yt = Mock()
            mock_yt.streams.filter.return_value.order_by.return_value.desc.return_value.first.return_value = None
            mock_youtube_class.return_value = mock_yt
            
            # Act & Assert
            events = []
            exception_raised = False
            try:
                async for event in service._download_youtube_video("test_video_id", False):
                    if isinstance(event, ProgressEvent):
                        events.append(event)
            except AttributeError:
                # This will happen when trying to access attributes of None stream
                exception_raised = True
            
            assert exception_raised
    
    @pytest.mark.asyncio
    async def test_download_youtube_video_download_error(self, service):
        """Test YouTube video download when download fails"""
        with patch('src.services.video_service.YouTube') as mock_youtube_class:
            # Arrange
            mock_yt = Mock()
            mock_yt.title = "Test Video"
            mock_youtube_class.return_value = mock_yt
            
            mock_stream = Mock()
            mock_stream.download.side_effect = Exception("Download failed")
            mock_stream.filesize = 1000000
            mock_stream.title = "Test Video"
            mock_stream.video_id = "test_video_id"
            mock_yt.streams.filter.return_value.order_by.return_value.desc.return_value.first.return_value = mock_stream
            
            # Act & Assert
            exception_raised = False
            try:
                async for event in service._download_youtube_video("test_video_id", False):
                    pass
            except Exception as e:
                exception_raised = True
                assert "Download failed" in str(e)
            
            assert exception_raised
