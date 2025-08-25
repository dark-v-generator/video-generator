import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.history_service import HistoryService
from src.models.progress import ProgressEvent
from src.entities.reddit_history import RedditHistory
from src.entities.history import History
from src.entities.cover import RedditCover
from src.entities.config import MainConfig
from src.entities.language import Language
from aiohttp import ClientResponseError


class TestHistoryServiceVideoGenerationSimple:
    """Simplified test for HistoryService video generation functionality"""
    
    @pytest.fixture
    def mock_dependencies(self):
        return {
            'history_repository': Mock(),
            'config_service': Mock(),
            'speech_service': AsyncMock(),
            'captions_service': Mock(),
            'cover_service': AsyncMock(),
            'video_service': Mock(),
            'llm_service': AsyncMock(),
            'file_repository': Mock(),
        }
    
    @pytest.fixture
    def service(self, mock_dependencies):
        return HistoryService(**mock_dependencies)
    
    @pytest.fixture
    def sample_reddit_history(self):
        history = History(
            title="Test Video Title",
            content="This is test content for video generation",
            gender="male"
        )
        cover = RedditCover(
            image_url="https://example.com/image.jpg",
            author="test_author",
            community="test_community",
            title="Test Title"
        )
        return RedditHistory(
            id="test-id-123",
            cover=cover,
            history=history,
            language=Language.ENGLISH.value,
            speech_path="/path/to/speech.mp3",
            # No captions_path or cover_path to avoid file system issues
        )
    
    @pytest.fixture
    def sample_config(self):
        config = Mock(spec=MainConfig)
        config.video_config = Mock()
        config.video_config.low_quality = False
        config.video_config.low_resolution = False
        config.video_config.height = 1080
        config.video_config.width = 1920
        config.video_config.padding = 20
        config.video_config.cover_duration = 5
        config.video_config.end_silece_seconds = 2
        config.video_config.ffmpeg_params = []
        
        config.captions_config = Mock()
        config.captions_config.font_size = 48
        config.captions_config.stroke_width = 2
        config.captions_config.marging = 10
        
        return config
    
    @pytest.mark.asyncio
    async def test_generate_reddit_video_basic_flow(self, service, sample_reddit_history, sample_config, mock_dependencies):
        """Test basic video generation flow with minimal components"""
        # Arrange
        mock_audio = Mock()
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        mock_background_video = Mock()
        mock_final_video = Mock()
        mock_final_video.clip = Mock()
        
        # Mock video service to return progress events and final video
        async def mock_create_video_compilation(duration, config):
            yield ProgressEvent.create("initializing", "Starting background video", progress=0)
            yield ProgressEvent.create("downloading", "Downloading background video clips", progress=50)
            yield ProgressEvent.create("completed", "Background video ready", progress=100)
            yield mock_background_video
        
        mock_dependencies['video_service'].create_video_compilation = mock_create_video_compilation
        mock_dependencies['video_service'].generate_video.return_value = mock_final_video
        mock_dependencies['file_repository'].get_file_url.return_value = "/url/to/video.mp4"
        
        with patch('src.services.history_service.audio_clip.AudioClip', return_value=mock_audio):
            # Act
            events = []
            final_result = None
            async for event in service.generate_reddit_video(sample_reddit_history, sample_config):
                if isinstance(event, ProgressEvent):
                    events.append(event)
                else:
                    final_result = event
            
            # Assert
            assert len(events) >= 3  # initializing, downloading events, generating
            assert events[0].stage == "initializing"
            assert events[0].progress is None  # No specific progress in initializing
            
            # Find generating stage
            generating_events = [e for e in events if e.stage == "generating"]
            assert len(generating_events) > 0
            
            assert final_result is not None
            assert final_result == sample_reddit_history
            assert sample_reddit_history.final_video_path == "/url/to/video.mp4"
            
            # Verify service calls
            mock_dependencies['video_service'].generate_video.assert_called_once()
            mock_dependencies['history_repository'].save_reddit_history.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_reddit_video_no_speech_error(self, service, sample_reddit_history, sample_config, mock_dependencies):
        """Test video generation fails when no speech is available"""
        # Arrange
        sample_reddit_history.speech_path = None
        
        # Act & Assert
        events = []
        exception_raised = False
        try:
            async for event in service.generate_reddit_video(sample_reddit_history, sample_config):
                if isinstance(event, ProgressEvent):
                    events.append(event)
                    if event.stage == "error":
                        continue
        except Exception as e:
            exception_raised = True
            assert "No speech audio available" in str(e)
        
        # Assert
        assert exception_raised, "Expected exception to be raised"
        error_events = [e for e in events if e.stage == "error"]
        assert len(error_events) > 0
        assert "No speech audio available" in error_events[0].message
    
    @pytest.mark.asyncio
    async def test_generate_reddit_video_low_quality_config(self, service, sample_reddit_history, sample_config, mock_dependencies):
        """Test that low quality settings are applied correctly"""
        # Arrange
        mock_audio = Mock()
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        async def mock_create_video_compilation(duration, config):
            yield ProgressEvent.create("completed", "Background ready", progress=100)
            yield Mock()  # background video
        
        mock_dependencies['video_service'].create_video_compilation = mock_create_video_compilation
        mock_dependencies['video_service'].generate_video.return_value = Mock()
        mock_dependencies['file_repository'].get_file_url.return_value = "/url/to/video.mp4"
        
        with patch('src.services.history_service.audio_clip.AudioClip', return_value=mock_audio):
            # Act
            events = []
            async for event in service.generate_reddit_video(sample_reddit_history, sample_config, low_quality=True):
                if isinstance(event, ProgressEvent):
                    events.append(event)
            
            # Assert
            # Check that low quality configuration is applied (no specific events for this now)
            # The configuration is applied directly without separate progress events
            assert len(events) >= 3  # Should still have basic progress events
            
            # Verify config modifications
            assert sample_config.video_config.low_quality is True
            assert sample_config.video_config.low_resolution is True
            # Size should be scaled down (400/1080 ratio)
            expected_ratio = 400 / 1080
            assert sample_config.video_config.height == int(round(1080 * expected_ratio))
            assert sample_config.video_config.width == int(round(1920 * expected_ratio))
    
    @pytest.mark.asyncio
    async def test_generate_reddit_video_progress_events_structure(self, service, sample_reddit_history, sample_config, mock_dependencies):
        """Test that progress events have correct structure and progression"""
        # Arrange
        mock_audio = Mock()
        mock_audio.clip = Mock()
        mock_audio.clip.duration = 30.0
        
        async def mock_create_video_compilation(duration, config):
            yield ProgressEvent.create("downloading", "Video 1", progress=25)
            yield ProgressEvent.create("downloading", "Video 2", progress=50)
            yield ProgressEvent.create("completed", "All videos ready", progress=100)
            yield Mock()  # background video
        
        mock_dependencies['video_service'].create_video_compilation = mock_create_video_compilation
        mock_dependencies['video_service'].generate_video.return_value = Mock()
        mock_dependencies['file_repository'].get_file_url.return_value = "/url/to/video.mp4"
        
        with patch('src.services.history_service.audio_clip.AudioClip', return_value=mock_audio):
            # Act
            events = []
            async for event in service.generate_reddit_video(sample_reddit_history, sample_config):
                if isinstance(event, ProgressEvent):
                    events.append(event)
            
            # Assert
            # Check that we have the expected event stages in the simplified implementation
            stages = [e.stage for e in events]
            assert "initializing" in stages
            assert "generating" in stages
            
            # Should also have video service events (downloading)
            downloading_events = [e for e in events if e.stage == "downloading"]
            assert len(downloading_events) > 0  # From video service background creation
            
            # Check that we have video service events (forwarded from create_video_compilation)
            video_service_events = [e for e in events if e.stage in ["initializing", "downloading", "completed"]]
            assert len(video_service_events) >= 2  # Should have forwarded events from video service


class TestHistoryServiceCoverDownload:
    """Test cover image downloading functionality"""
    
    @pytest.fixture
    def mock_dependencies(self):
        return {
            'history_repository': Mock(),
            'config_service': Mock(),
            'speech_service': AsyncMock(),
            'captions_service': Mock(),
            'cover_service': AsyncMock(),
            'video_service': Mock(),
            'llm_service': AsyncMock(),
            'file_repository': Mock(),
        }
    
    @pytest.fixture
    def service(self, mock_dependencies):
        return HistoryService(**mock_dependencies)
    
    @pytest.fixture
    def sample_config(self):
        return MainConfig()
    
    @pytest.fixture
    def sample_reddit_history_with_cover(self):
        history = History(
            title="Test Video Title",
            content="This is test content for video generation",
            gender="male"
        )
        cover = RedditCover(
            image_url="https://example.com/image.jpg",
            author="test_author",
            community="test_community",
            title="Test Title"
        )
        return RedditHistory(
            id="test-id-123",
            cover=cover,
            history=history,
            language=Language.ENGLISH.value,
            speech_path="/path/to/speech.mp3",
            cover_path="https://example.com/api/files/histories/test-id-123/cover.png",  # External URL
        )
    
    @pytest.mark.asyncio
    async def test_generate_video_downloads_cover_successfully(self, service, mock_dependencies, sample_reddit_history_with_cover, sample_config):
        """Test that cover image is downloaded successfully from URL"""
        # Arrange
        mock_png_bytes = b"fake_png_data"
        
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.read.return_value = mock_png_bytes
        mock_response.raise_for_status.return_value = None
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        # Mock speech service
        mock_audio = Mock()
        mock_audio.clip.duration = 60.0
        mock_dependencies['speech_service'].load_speech_from_file.return_value = mock_audio
        
        # Mock video service
        async def mock_create_video_compilation(duration, config):
            yield ProgressEvent.create("downloading", "Downloading videos", progress=50)
            yield Mock()  # Return mock video clip
        
        mock_dependencies['video_service'].create_video_compilation = mock_create_video_compilation
        mock_dependencies['video_service'].generate_video.return_value = Mock()
        mock_dependencies['file_repository'].get_file_url.return_value = "/url/to/video.mp4"
        
        with patch('src.services.history_service.audio_clip.AudioClip', return_value=mock_audio), \
             patch('aiohttp.ClientSession', return_value=mock_session), \
             patch('src.services.history_service.image_clip.ImageClip') as mock_image_clip:
            
            # Act
            events = []
            async for event in service.generate_reddit_video(sample_reddit_history_with_cover, sample_config):
                if isinstance(event, ProgressEvent):
                    events.append(event)
            
            # Assert
            # Check that cover downloading event was emitted
            downloading_cover_events = [e for e in events if e.stage == "downloading_cover"]
            assert len(downloading_cover_events) == 1
            assert downloading_cover_events[0].message == "Downloading cover image"
            assert downloading_cover_events[0].details["url"] == sample_reddit_history_with_cover.cover_path
            
            # Check that ImageClip was called with bytes
            mock_image_clip.assert_called_once_with(file_path="", bytes=mock_png_bytes)
            
            # Check that aiohttp was used to download
            mock_session.get.assert_called_once_with(sample_reddit_history_with_cover.cover_path)
            mock_response.read.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_video_handles_cover_download_failure(self, service, mock_dependencies, sample_reddit_history_with_cover, sample_config):
        """Test that video generation continues when cover download fails"""
        # Arrange
        # Mock aiohttp to raise an exception
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.side_effect = ClientResponseError(None, None, status=404, message="Not Found")
        mock_session.get.return_value.__aexit__.return_value = None
        
        # Mock speech service
        mock_audio = Mock()
        mock_audio.clip.duration = 60.0
        mock_dependencies['speech_service'].load_speech_from_file.return_value = mock_audio
        
        # Mock video service
        async def mock_create_video_compilation(duration, config):
            yield ProgressEvent.create("downloading", "Downloading videos", progress=50)
            yield Mock()  # Return mock video clip
        
        mock_dependencies['video_service'].create_video_compilation = mock_create_video_compilation
        mock_dependencies['video_service'].generate_video.return_value = Mock()
        mock_dependencies['file_repository'].get_file_url.return_value = "/url/to/video.mp4"
        
        with patch('src.services.history_service.audio_clip.AudioClip', return_value=mock_audio), \
             patch('aiohttp.ClientSession', return_value=mock_session), \
             patch('src.services.history_service.image_clip.ImageClip') as mock_image_clip:
            
            # Act
            events = []
            async for event in service.generate_reddit_video(sample_reddit_history_with_cover, sample_config):
                if isinstance(event, ProgressEvent):
                    events.append(event)
            
            # Assert
            # Check that cover downloading event was still emitted
            downloading_cover_events = [e for e in events if e.stage == "downloading_cover"]
            assert len(downloading_cover_events) == 1
            
            # Check that ImageClip was NOT called since download failed
            mock_image_clip.assert_not_called()
            
            # Video generation should continue without cover
            generating_events = [e for e in events if e.stage == "generating"]
            assert len(generating_events) > 0
