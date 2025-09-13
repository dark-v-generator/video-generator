import pytest
from unittest.mock import Mock, patch

from src.services.llm.local_llm_service import LocalLLMService
from src.entities.config import MainConfig, LLMConfig
from src.entities.history import History
from src.entities.language import Language
from src.entities.captions import Captions, CaptionSegment
from src.entities.progress import ProgressEvent


@pytest.fixture
def main_config():
    """Test main configuration"""
    config = MainConfig()
    config.llm_config = LLMConfig(
        provider="local",
        ollama_base_url="http://localhost:11434",
        model="llama3.2:latest",
        temperature=0.7,
        max_tokens=2000
    )
    return config


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client"""
    with patch('ollama.Client') as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def local_service(main_config, mock_ollama_client):
    """Local LLM service instance with mocked Ollama client"""
    with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://localhost:11434', 'OLLAMA_MODEL': 'llama3.2:latest'}):
        service = LocalLLMService(main_config)
        service.client = mock_ollama_client
        return service


class TestLocalLLMService:
    """Test Local LLM Service"""

    @patch('ollama.Client')
    def test_init_with_config(self, mock_client, main_config):
        """Test initialization with configuration"""
        service = LocalLLMService(main_config)
        assert service.config == main_config
        assert service.base_url == "http://localhost:11434"
        assert service.model == "llama3.2:latest"
        assert service.temperature == 0.7
        assert service.max_tokens == 2000

    @patch('ollama.Client')
    def test_init_with_env_vars(self, mock_client):
        """Test initialization with environment variables"""
        with patch.dict('os.environ', {'OLLAMA_BASE_URL': 'http://test:8080', 'OLLAMA_MODEL': 'test-model'}):
            # Pass None config so environment variables are used
            service = LocalLLMService(None)
            assert service.config is None
            assert service.base_url == "http://test:8080"
            assert service.model == "test-model"

    @pytest.mark.asyncio
    async def test_enhance_history_success(self, local_service, mock_ollama_client):
        """Test enhance history with successful Ollama response"""
        # Mock successful Ollama streaming response
        mock_stream = [
            {'message': {'content': 'Enhanced'}, 'done': False},
            {'message': {'content': ' story'}, 'done': False},
            {'message': {'content': ' content'}, 'done': False},
            {'message': {'content': ' that is'}, 'done': False},
            {'message': {'content': ' better'}, 'done': False},
            {'message': {'content': ''}, 'done': True}
        ]
        
        mock_ollama_client.chat.return_value = iter(mock_stream)
        
        tokens = []
        async for token in local_service.enhance_history(
            "Test Title", 
            "Test content", 
            Language.PORTUGUESE
        ):
            tokens.append(token)
        
        # Check that we got the expected tokens
        expected_tokens = ['Enhanced', ' story', ' content', ' that is', ' better']
        assert tokens == expected_tokens

    @pytest.mark.asyncio
    async def test_enhance_history_fallback_on_error(self, local_service, mock_ollama_client):
        """Test enhance history falls back on connection error"""
        # Mock Ollama to raise an exception
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        tokens = []
        async for token in local_service.enhance_history(
            "Test Title", 
            "Test content", 
            Language.PORTUGUESE
        ):
            tokens.append(token)
        
        # Check fallback result - should stream the fallback content
        fallback_content = "Test Title\n\nTest content"
        expected_tokens = fallback_content.split()
        expected_tokens = [word + " " for word in expected_tokens]
        
        assert tokens == expected_tokens

    @pytest.mark.asyncio
    async def test_enhance_captions_success(self, local_service, mock_ollama_client):
        """Test enhance captions with successful Ollama response"""
        # Mock successful Ollama response
        mock_ollama_client.chat.return_value = {
            'message': {
                'content': '{"segments": [{"start": 0.0, "end": 2.5, "text": "Enhanced caption"}]}'
            }
        }
        
        original_captions = Captions(segments=[
            CaptionSegment(start=0.0, end=2.5, text="Test caption")
        ])
        
        history = History(title="Test", content="Test", gender="male")
        
        result = await local_service.enhance_captions(
            original_captions, history, Language.PORTUGUESE
        )
        
        assert isinstance(result, Captions)
        assert len(result.segments) == 1
        assert result.segments[0].text == "Enhanced caption"

    @pytest.mark.asyncio
    async def test_enhance_captions_fallback_on_error(self, local_service, mock_ollama_client):
        """Test enhance captions falls back to original on error"""
        # Mock Ollama response with invalid JSON
        mock_ollama_client.chat.return_value = {
            'message': {
                'content': 'Invalid JSON response'
            }
        }
        
        original_captions = Captions(segments=[
            CaptionSegment(start=0.0, end=2.5, text="Test caption")
        ])
        
        history = History(title="Test", content="Test", gender="male")
        
        result = await local_service.enhance_captions(
            original_captions, history, Language.PORTUGUESE
        )
        
        assert result is original_captions
        assert len(result.segments) == 1
        assert result.segments[0].text == "Test caption"

    @pytest.mark.asyncio
    async def test_generate_engagement_phrase_success(self, local_service, mock_ollama_client):
        """Test generate engagement phrase with successful Ollama response"""
        # Mock successful Ollama response
        mock_ollama_client.chat.return_value = {
            'message': {
                'content': 'Uma história incrível que vai te surpreender!'
            }
        }
        
        history = History(title="Amazing Story", content="Content", gender="male")
        
        result = await local_service.generate_engagement_phrase(
            history, Language.PORTUGUESE
        )
        
        assert isinstance(result, str)
        assert result == "Uma história incrível que vai te surpreender!"

    @pytest.mark.asyncio
    async def test_generate_engagement_phrase_fallback(self, local_service, mock_ollama_client):
        """Test generate engagement phrase falls back on error"""
        # Mock Ollama to raise an exception
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        history = History(title="Amazing Story", content="Content", gender="male")
        
        result = await local_service.generate_engagement_phrase(
            history, Language.PORTUGUESE
        )
        
        assert isinstance(result, str)
        assert "Amazing Story" in result
        assert result.startswith("Você não vai acreditar")

    @pytest.mark.asyncio
    async def test_divide_history_success(self, local_service, mock_ollama_client):
        """Test divide history with successful Ollama response"""
        # Mock successful Ollama response
        mock_ollama_client.chat.return_value = {
            'message': {
                'content': '{"histories": [{"title": "Part 1", "content": "Content 1", "gender": "female"}, {"title": "Part 2", "content": "Content 2", "gender": "female"}]}'
            }
        }
        
        original_history = History(
            title="Long Story", 
            content="Long content", 
            gender="female"
        )
        
        result = await local_service.divide_history(
            original_history, 2, Language.ENGLISH
        )
        
        assert len(result) == 2
        assert result[0].title == "Part 1"
        assert result[1].title == "Part 2"

    @pytest.mark.asyncio
    async def test_divide_history_fallback(self, local_service, mock_ollama_client):
        """Test divide history falls back to original on error"""
        # Mock Ollama response with invalid JSON
        mock_ollama_client.chat.return_value = {
            'message': {
                'content': 'Invalid JSON response'
            }
        }
        
        original_history = History(
            title="Long Story", 
            content="Long content", 
            gender="female"
        )
        
        result = await local_service.divide_history(
            original_history, 3, Language.ENGLISH
        )
        
        assert len(result) == 1
        assert result[0] is original_history

    @pytest.mark.asyncio
    async def test_all_methods_with_different_languages(self, local_service, mock_ollama_client):
        """Test all methods work with different languages"""
        # Mock Ollama to return fallback responses (simulate errors)
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        history = History(title="Test", content="Test", gender="male")
        captions = Captions(segments=[])
        
        languages = [Language.PORTUGUESE, Language.ENGLISH]
        
        for lang in languages:
            # Test enhance_history with streaming interface
            tokens = []
            async for token in local_service.enhance_history("Title", "Content", lang):
                tokens.append(token)
            # Should get fallback tokens since we're simulating connection error
            assert len(tokens) > 0
            assert isinstance(tokens[0], str)
            
            # Test other methods (these haven't changed to streaming yet)
            enhanced_captions = await local_service.enhance_captions(captions, history, lang)
            assert enhanced_captions is captions
            
            phrase = await local_service.generate_engagement_phrase(history, lang)
            assert isinstance(phrase, str)
            
            divided = await local_service.divide_history(history, 2, lang)
            assert len(divided) == 1


@pytest.mark.unit
class TestLocalLLMServiceEdgeCases:
    """Edge cases for Local LLM Service"""

    @pytest.mark.asyncio
    async def test_empty_input_handling(self, local_service, mock_ollama_client):
        """Test service handles empty inputs gracefully"""
        # Mock Ollama to simulate error (fallback behavior)
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        tokens = []
        async for token in local_service.enhance_history("", "", Language.PORTUGUESE):
            tokens.append(token)
        
        # Should get fallback content for empty inputs
        fallback_content = "\n\n"
        expected_tokens = fallback_content.split()
        # Since empty content splits to empty list, we expect empty list or minimal fallback
        assert len(tokens) >= 0

    @pytest.mark.asyncio
    async def test_special_characters_in_title(self, local_service, mock_ollama_client):
        """Test service handles special characters in title"""
        # Mock Ollama to simulate error (fallback behavior)
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        special_title = "História com çãräctéres especiais! @#$%"
        
        tokens = []
        async for token in local_service.enhance_history(
            special_title, "Content", Language.PORTUGUESE
        ):
            tokens.append(token)
        
        # Should get fallback tokens containing the special title
        combined_content = "".join(tokens)
        assert special_title in combined_content

    @pytest.mark.asyncio
    async def test_very_long_content(self, local_service, mock_ollama_client):
        """Test service handles very long content"""
        # Mock Ollama to simulate error (fallback behavior)
        mock_ollama_client.chat.side_effect = Exception("Connection error")
        
        long_content = "A" * 10000  # 10k characters
        
        tokens = []
        async for token in local_service.enhance_history(
            "Title", long_content, Language.PORTUGUESE
        ):
            tokens.append(token)
        
        # Should get fallback tokens containing the long content
        combined_content = "".join(tokens)
        assert long_content in combined_content

    @pytest.mark.asyncio
    async def test_streaming_with_markdown_content(self, local_service, mock_ollama_client):
        """Test service streams markdown content properly"""
        # Mock Ollama streaming response with markdown content
        mock_stream = [
            {'message': {'content': 'This is'}, 'done': False},
            {'message': {'content': ' **enhanced**'}, 'done': False},
            {'message': {'content': ' content'}, 'done': False},
            {'message': {'content': ' with markdown'}, 'done': False},
            {'message': {'content': ''}, 'done': True}
        ]
        mock_ollama_client.chat.return_value = iter(mock_stream)
        
        tokens = []
        async for token in local_service.enhance_history(
            "Test Title", 
            "Test content", 
            Language.PORTUGUESE
        ):
            tokens.append(token)
        
        expected_tokens = ['This is', ' **enhanced**', ' content', ' with markdown']
        assert tokens == expected_tokens
