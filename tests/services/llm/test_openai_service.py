import pytest
import json
from unittest.mock import Mock, patch

from src.services.llm.openai_service import OpenAILLMService
from src.entities.config import MainConfig, LLMConfig
from src.entities.history import History
from src.entities.language import Language
from src.entities.captions import Captions, CaptionSegment
from src.entities.progress import ProgressEvent


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    return Mock()


@pytest.fixture
def llm_config():
    """Test LLM configuration"""
    return LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=2000
    )


@pytest.fixture
def main_config(llm_config):
    """Test main configuration with LLM config"""
    config = MainConfig()
    config.llm_config = llm_config
    return config


@pytest.fixture
def openai_service(main_config):
    """OpenAI LLM service instance"""
    return OpenAILLMService(main_config)


@pytest.fixture
def mock_chat_completion():
    """Mock OpenAI chat completion response"""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"title": "Enhanced Title", "content": "Enhanced content", "gender": "male"}'
    return mock_response


class TestOpenAILLMService:
    """Test OpenAI LLM Service"""

    def test_init_with_config(self, main_config):
        """Test initialization with configuration"""
        service = OpenAILLMService(main_config)
        assert service.config == main_config
        assert service.model == "gpt-4o-mini"
        assert service.temperature == 0.7
        assert service.max_tokens == 2000

    def test_init_without_config(self):
        """Test initialization without configuration uses defaults"""
        service = OpenAILLMService(None)
        assert service.config is None
        assert service.model == "gpt-4o-mini"
        assert service.temperature == 0.7
        assert service.max_tokens == 2000

    @pytest.mark.asyncio
    async def test_enhance_history_success(self, openai_service):
        """Test successful history enhancement streaming"""
        # Mock streaming response
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Enhanced"))]),
            Mock(choices=[Mock(delta=Mock(content=" story"))]),
            Mock(choices=[Mock(delta=Mock(content=" content"))]),
            Mock(choices=[Mock(delta=Mock(content=None))]),  # End of stream
        ]
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = iter(mock_chunks)
            
            tokens = []
            async for token in openai_service.enhance_history(
                "Original Title", 
                "Original content", 
                Language.PORTUGUESE
            ):
                tokens.append(token)
            
            # Check that we got the expected tokens
            assert tokens == ["Enhanced", " story", " content"]
            
            # Verify client was called with correct parameters
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs['model'] == "gpt-4o-mini"
            assert call_args.kwargs['temperature'] == 0.7
            assert call_args.kwargs['max_tokens'] == 2000
            assert call_args.kwargs['stream'] is True

    @pytest.mark.asyncio
    async def test_enhance_history_api_error(self, openai_service):
        """Test enhance history with API error"""
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            
            with pytest.raises(Exception, match="API Error"):
                async for token in openai_service.enhance_history(
                    "Title", "Content", Language.PORTUGUESE
                ):
                    pass  # Just iterate through to trigger the error

    @pytest.mark.asyncio
    async def test_enhance_captions_success(self, openai_service):
        """Test successful caption enhancement"""
        # Mock response for captions enhancement
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Enhanced caption 1"},
                {"start": 2.5, "end": 5.0, "text": "Enhanced caption 2"}
            ]
        })
        
        # Create test captions
        original_captions = Captions(segments=[
            CaptionSegment(start=0.0, end=2.5, text="Original caption 1"),
            CaptionSegment(start=2.5, end=5.0, text="Original caption 2")
        ])
        
        # Create test history
        history = History(title="Test Title", content="Test content", gender="male")
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            
            result = await openai_service.enhance_captions(
                original_captions, history, Language.PORTUGUESE
            )
            
            assert isinstance(result, Captions)
            assert len(result.segments) == 2
            assert result.segments[0].text == "Enhanced caption 1"
            assert result.segments[1].text == "Enhanced caption 2"
            assert result.segments[0].start == 0.0
            assert result.segments[1].end == 5.0

    @pytest.mark.asyncio
    async def test_generate_engagement_phrase_success(self, openai_service):
        """Test successful engagement phrase generation"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Você não vai acreditar no que aconteceu!"
        
        history = History(title="Amazing Story", content="This is amazing", gender="male")
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            
            result = await openai_service.generate_engagement_phrase(
                history, Language.PORTUGUESE
            )
            
            assert result == "Você não vai acreditar no que aconteceu!"
            
            # Verify max_tokens was limited for engagement phrases
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs['max_tokens'] == 100

    @pytest.mark.asyncio
    async def test_divide_history_success(self, openai_service):
        """Test successful history division"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "histories": [
                {"title": "Part 1", "content": "First part", "gender": "male"},
                {"title": "Part 2", "content": "Second part", "gender": "male"}
            ]
        })
        
        original_history = History(
            title="Long Story", 
            content="This is a long story that needs to be divided", 
            gender="male"
        )
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            
            result = await openai_service.divide_history(
                original_history, 2, Language.PORTUGUESE
            )
            
            assert len(result) == 2
            assert all(isinstance(h, History) for h in result)
            assert result[0].title == "Part 1"
            assert result[1].title == "Part 2"
            assert result[0].content == "First part"
            assert result[1].content == "Second part"

    @pytest.mark.asyncio
    async def test_empty_content_streaming(self, openai_service):
        """Test streaming with empty content"""
        # Mock streaming response with empty content
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content=""))]),
            Mock(choices=[Mock(delta=Mock(content=None))]),  # End of stream
        ]
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.return_value = iter(mock_chunks)
            
            tokens = []
            async for token in openai_service.enhance_history(
                "Title", "Content", Language.PORTUGUESE
            ):
                tokens.append(token)
            
            # Should get empty string token
            assert tokens == [""]


@pytest.mark.unit
class TestOpenAIServiceIntegration:
    """Integration-style tests for OpenAI service"""

    @patch('src.services.llm.openai_service.OpenAI')
    @pytest.mark.asyncio
    async def test_real_openai_client_initialization(self, mock_openai_class, main_config):
        """Test that OpenAI client is properly initialized"""
        mock_client_instance = Mock()
        mock_openai_class.return_value = mock_client_instance
        
        service = OpenAILLMService(main_config)
        
        # The client should be initialized in __init__
        mock_openai_class.assert_called_once()
        assert service.client == mock_client_instance
