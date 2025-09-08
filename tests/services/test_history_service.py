import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch, mock_open
from pathlib import Path

from src.services.history_service import HistoryService
from src.services.interfaces import (
    IConfigService, ISpeechService, ICaptionsService, 
    ICoverService, IVideoService
)
from src.services.llm.interfaces import ILLMService
from src.repositories.interfaces import IHistoryRepository, IFileRepository
from src.entities.config import MainConfig
from src.entities.history import History
from src.entities.reddit_history import RedditHistory
from src.entities.cover import RedditCover
from src.entities.language import Language
from src.entities.captions import Captions
from src.proxies.reddit_proxy import RedditPost
from src.models.progress import ProgressEvent


@pytest.fixture
def mock_history_repository():
    """Mock history repository"""
    mock = Mock(spec=IHistoryRepository)
    mock.save_reddit_history = Mock()
    mock.load_reddit_history = Mock()
    mock.delete_reddit_history = Mock(return_value=True)
    mock.list_history_ids = Mock(return_value=["id1", "id2"])
    return mock


@pytest.fixture
def mock_config_service():
    """Mock config service"""
    mock = Mock(spec=IConfigService)
    mock.get_main_config = Mock(return_value=MainConfig())
    return mock


@pytest.fixture
def mock_speech_service():
    """Mock speech service"""
    mock = AsyncMock(spec=ISpeechService)
    return mock


@pytest.fixture
def mock_captions_service():
    """Mock captions service"""
    mock = Mock(spec=ICaptionsService)
    return mock


@pytest.fixture
def mock_cover_service():
    """Mock cover service"""
    mock = Mock(spec=ICoverService)
    return mock


@pytest.fixture
def mock_video_service():
    """Mock video service"""
    mock = Mock(spec=IVideoService)
    return mock


@pytest.fixture
def mock_llm_service():
    """Mock LLM service"""
    mock = AsyncMock(spec=ILLMService)
    mock.enhance_history = AsyncMock(return_value=History(
        title="Enhanced Title", content="Enhanced content", gender="male"
    ))
    return mock


@pytest.fixture
def mock_file_repository():
    """Mock file repository"""
    mock = Mock(spec=IFileRepository)
    mock.save_file = Mock()
    mock.load_file = Mock()
    mock.delete_file = Mock(return_value=True)
    mock.file_exists = Mock(return_value=True)
    mock.create_directory = Mock()
    mock.get_file_url = Mock(return_value="/api/files/test-id-123/speech.mp3")
    return mock


@pytest.fixture
def history_service(
    mock_history_repository,
    mock_config_service, 
    mock_speech_service,
    mock_captions_service,
    mock_cover_service,
    mock_video_service,
    mock_llm_service,
    mock_file_repository
):
    """History service with mocked dependencies"""
    return HistoryService(
        mock_history_repository,
        mock_config_service,
        mock_speech_service,
        mock_captions_service,
        mock_cover_service,
        mock_video_service,
        mock_llm_service,
        mock_file_repository
    )


@pytest.fixture
def sample_reddit_post():
    """Sample Reddit post for testing"""
    return RedditPost(
        title="Amazing Story",
        content="This is an amazing story that happened",
        author="test_user",
        community="r/test",
        community_url_photo="https://example.com/photo.jpg"
    )


@pytest.fixture
def sample_reddit_history():
    """Sample Reddit history for testing"""
    history = History(title="Test Title", content="Test content", gender="male")
    cover = RedditCover(
        image_url="https://example.com/photo.jpg",
        author="test_user", 
        community="r/test",
        title="Test Title"
    )
    return RedditHistory(
        id="test-id-123",
        cover=cover,
        history=history,
        folder_path="/test/path",
        language=Language.PORTUGUESE.value
    )


class TestHistoryService:
    """Test History Service"""

    def test_init(self, history_service, mock_history_repository):
        """Test service initialization"""
        assert history_service._history_repository == mock_history_repository

    @patch('src.services.history_service.reddit_proxy')
    @patch('src.services.history_service.uuid.uuid4')
    @pytest.mark.asyncio
    async def test_srcap_reddit_post_with_enhancement(
        self, 
        mock_uuid,
        mock_reddit_proxy,
        history_service,
        sample_reddit_post,
        mock_llm_service
    ):
        """Test scraping Reddit post with enhancement"""
        # Setup mocks
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value="test-uuid")
        mock_reddit_proxy.get_reddit_post.return_value = sample_reddit_post
        
        config = MainConfig()
        
        # Test with enhancement
        result = await history_service.srcap_reddit_post(
            "https://reddit.com/test",
            enhance_history=True,
            config=config,
            language=Language.PORTUGUESE
        )
        
        # Verify LLM service was called
        mock_llm_service.enhance_history.assert_called_once_with(
            "Amazing Story",
            "This is an amazing story that happened",
            language=Language.PORTUGUESE
        )
        
        # Verify result
        assert isinstance(result, RedditHistory)
        assert result.id == "test-uuid"
        assert result.history.title == "Enhanced Title"  # From mock LLM service
        
        # Verify history was saved
        history_service._history_repository.save_reddit_history.assert_called_once()

    @patch('src.services.history_service.reddit_proxy')
    @patch('src.services.history_service.uuid.uuid4')
    @pytest.mark.asyncio
    async def test_srcap_reddit_post_without_enhancement(
        self,
        mock_uuid,
        mock_reddit_proxy,
        history_service,
        sample_reddit_post,
        mock_llm_service
    ):
        """Test scraping Reddit post without enhancement"""
        # Setup mocks
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value="test-uuid-2")
        mock_reddit_proxy.get_reddit_post.return_value = sample_reddit_post
        
        config = MainConfig()
        
        # Test without enhancement
        result = await history_service.srcap_reddit_post(
            "https://reddit.com/test",
            enhance_history=False,
            config=config,
            language=Language.ENGLISH
        )
        
        # Verify LLM service was NOT called
        mock_llm_service.enhance_history.assert_not_called()
        
        # Verify result uses original content
        assert result.history.title == "Amazing Story"
        assert result.history.content == "This is an amazing story that happened"

    def test_list_histories(self, history_service, mock_history_repository, sample_reddit_history):
        """Test listing histories"""
        mock_history_repository.load_reddit_history.return_value = sample_reddit_history
        
        config = MainConfig()
        result = history_service.list_histories(config)
        
        # Should load each history ID
        assert mock_history_repository.load_reddit_history.call_count == 2
        assert len(result) == 2

    def test_list_histories_with_none_result(self, history_service, mock_history_repository, sample_reddit_history):
        """Test listing histories when some return None"""
        mock_history_repository.list_history_ids.return_value = ["hist1", "hist2"]
        mock_history_repository.load_reddit_history.side_effect = [None, sample_reddit_history]
        
        config = MainConfig()
        result = history_service.list_histories(config)
        
        # Should filter out None results
        assert len(result) == 1

    def test_get_reddit_history(self, history_service, mock_history_repository, sample_reddit_history):
        """Test getting specific Reddit history"""
        mock_history_repository.load_reddit_history.return_value = sample_reddit_history
        
        config = MainConfig()
        result = history_service.get_reddit_history("test-id", config)
        
        assert result == sample_reddit_history
        mock_history_repository.load_reddit_history.assert_called_once_with("test-id")

    def test_save_reddit_history(self, history_service, mock_history_repository, sample_reddit_history):
        """Test saving Reddit history"""
        config = MainConfig()
        
        history_service.save_reddit_history(sample_reddit_history, config)
        
        mock_history_repository.save_reddit_history.assert_called_once_with(sample_reddit_history)

    def test_delete_reddit_history(self, history_service, mock_history_repository):
        """Test deleting Reddit history"""
        config = MainConfig()
        
        result = history_service.delete_reddit_history("test-id", config)
        
        assert result is True
        mock_history_repository.delete_reddit_history.assert_called_once_with("test-id")

    @patch('src.services.history_service.Path')
    @pytest.mark.asyncio
    async def test_generate_speech(
        self,
        mock_path,
        history_service,
        sample_reddit_history,
        mock_speech_service,
        mock_file_repository
    ):
        """Test speech generation"""
        # Create a proper async generator for mocking
        from src.models.progress import ProgressEvent
        
        async def mock_generate_speech_func(*args, **kwargs):
            yield ProgressEvent.create("generating", "Generating speech")
            yield b"fake_audio_data"
        
        # Patch the speech service method directly on the history service instance
        history_service._speech_service.generate_speech = mock_generate_speech_func
        
        # Mock Path resolve
        mock_path.return_value.resolve.return_value = "/resolved/path/speech.mp3"
        
        config = MainConfig()
        history_service.generate_speech(sample_reddit_history, 1.5, config)
        
        # Verify that file repository save_file was called
        mock_file_repository.save_file.assert_called_once_with(
            "test-id-123/speech.mp3", b"fake_audio_data"
        )
        
        # Verify get_file_url was called and speech_path was set
        mock_file_repository.get_file_url.assert_called_once_with("test-id-123/speech.mp3")
        assert sample_reddit_history.speech_path == "/api/files/test-id-123/speech.mp3"

    def test_generate_captions(
        self,
        history_service,
        sample_reddit_history,
        mock_captions_service
    ):
        """Test captions generation"""
        # Mock captions service
        mock_captions = Mock()
        mock_captions.stripped.return_value = mock_captions
        mock_captions.save_yaml = Mock()
        mock_captions_service.generate_captions.return_value = mock_captions
        
        # Set speech path
        sample_reddit_history.speech_path = "/test/speech.mp3"
        
        config = MainConfig()
        
        with patch('src.services.history_service.Path') as mock_path:
            mock_path.return_value.resolve.return_value = "/resolved/captions.yaml"
            
            history_service.generate_captions(
                sample_reddit_history, 1.0, config, enhance_captions=True
            )
        
        # Verify captions service was called
        mock_captions_service.generate_captions.assert_called_once_with(
            "/test/speech.mp3",
            enhance_captions=True,
            language=sample_reddit_history.get_language()
        )

    @pytest.mark.asyncio
    async def test_generate_cover(
        self,
        history_service,
        sample_reddit_history,
        mock_cover_service,
        mock_file_repository
    ):
        """Test cover generation streaming"""
        # Mock cover service to return PNG bytes
        mock_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # Sample PNG header
        mock_cover_service.generate_cover = AsyncMock(return_value=mock_png_bytes)
        
        # Mock file repository
        mock_file_repository.get_file_url.return_value = "/api/files/test/cover.png"
        
        config = MainConfig()
        
        # Collect all events from the async generator
        events = []
        final_history = None
        
        async for event in history_service.generate_cover(sample_reddit_history, config):
            if isinstance(event, ProgressEvent):
                events.append(event)
            else:
                final_history = event
        
        # Verify we got progress events
        assert len(events) >= 3  # starting, generating, saving, completed
        assert events[0].stage == "starting"
        assert events[-1].stage == "completed"
        
        # Verify cover service was called
        mock_cover_service.generate_cover.assert_called_once_with(
            sample_reddit_history.cover, config
        )
        
        # Verify file repository was used to save the file
        expected_cover_path = f"histories/{sample_reddit_history.id}/cover.png"
        mock_file_repository.save_file.assert_called_once_with(expected_cover_path, mock_png_bytes)
        mock_file_repository.get_file_url.assert_called_once_with(expected_cover_path)
        
        # Verify history was updated
        assert sample_reddit_history.cover_path == "/api/files/test/cover.png"
        assert final_history == sample_reddit_history

    def test_get_speech_text(self, history_service):
        """Test speech text generation"""
        history = History(title="Test Title", content="Test content", gender="male")
        
        result = history_service._get_speech_text(history)
        
        assert result == "Test Title\n Test content"


@pytest.mark.unit
class TestHistoryServiceEdgeCases:
    """Edge cases for History Service"""

    def test_empty_history_ids_list(self, history_service, mock_history_repository):
        """Test listing histories with empty ID list"""
        mock_history_repository.list_history_ids.return_value = []
        
        config = MainConfig()
        result = history_service.list_histories(config)
        
        assert result == []

    def test_delete_nonexistent_history(self, history_service, mock_history_repository):
        """Test deleting non-existent history"""
        mock_history_repository.delete_reddit_history.return_value = False
        
        config = MainConfig()
        result = history_service.delete_reddit_history("nonexistent", config)
        
        assert result is False

    @patch('src.services.history_service.reddit_proxy')
    @pytest.mark.asyncio
    async def test_srcap_reddit_post_api_error(
        self,
        mock_reddit_proxy,
        history_service
    ):
        """Test scraping with Reddit API error"""
        mock_reddit_proxy.get_reddit_post.side_effect = Exception("Reddit API Error")
        
        config = MainConfig()
        
        with pytest.raises(Exception, match="Reddit API Error"):
            await history_service.srcap_reddit_post(
                "https://reddit.com/test",
                enhance_history=False,
                config=config
            )

    def test_generate_speech_no_speech_path(self, history_service, sample_reddit_history, mock_file_repository):
        """Test speech generation when reddit_history has no speech_path set"""
        # Remove speech_path
        sample_reddit_history.speech_path = None
        
        # This should still work and set the speech_path
        config = MainConfig()
        
        with patch('src.services.history_service.Path') as mock_path:
            mock_path.return_value.resolve.return_value = "/new/speech/path.mp3"
            
            # Mock speech service with async generator function
            from src.models.progress import ProgressEvent
            
            async def mock_generate_speech_func(*args, **kwargs):
                yield ProgressEvent.create("generating", "Generating speech")
                yield b"fake_audio_data"
            
            # Patch the speech service method directly on the history service instance
            history_service._speech_service.generate_speech = mock_generate_speech_func
            
            history_service.generate_speech(sample_reddit_history, 1.0, config)
            
            # Verify file repository was called
            mock_file_repository.save_file.assert_called_once_with(
                "test-id-123/speech.mp3", b"fake_audio_data"
            )
            
            # Verify get_file_url was called and speech_path was set
            mock_file_repository.get_file_url.assert_called_once_with("test-id-123/speech.mp3")
            assert sample_reddit_history.speech_path == "/api/files/test-id-123/speech.mp3"
