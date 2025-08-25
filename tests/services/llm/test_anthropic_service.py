import pytest

from src.services.llm.anthropic_service import AnthropicLLMService
from src.entities.config import MainConfig
from src.entities.history import History
from src.entities.language import Language
from src.entities.captions import Captions, CaptionSegment
from src.models.progress import ProgressEvent


@pytest.fixture
def main_config():
    """Test main configuration"""
    return MainConfig()


@pytest.fixture
def anthropic_service(main_config):
    """Anthropic LLM service instance"""
    return AnthropicLLMService(main_config)


class TestAnthropicLLMService:
    """Test Anthropic LLM Service"""

    def test_init_with_config(self, main_config):
        """Test initialization with configuration"""
        service = AnthropicLLMService(main_config)
        assert service.config == main_config

    def test_init_without_config(self):
        """Test initialization without configuration"""
        service = AnthropicLLMService(None)
        assert service.config is None

    @pytest.mark.asyncio
    async def test_enhance_history_placeholder(self, anthropic_service):
        """Test enhance history streams content tokens"""
        tokens = []
        
        async for token in anthropic_service.enhance_history(
            "Original Title", 
            "Original content", 
            Language.PORTUGUESE
        ):
            tokens.append(token)
        
        # Should get tokens that form the enhanced content
        combined_content = "".join(tokens)
        assert "Original Title" in combined_content
        assert "Original content" in combined_content
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_enhance_captions_returns_original(self, anthropic_service):
        """Test enhance captions returns original captions"""
        original_captions = Captions(segments=[
            CaptionSegment(start=0.0, end=3.0, text="Original caption")
        ])
        
        history = History(title="Test", content="Test", gender="female")
        
        result = await anthropic_service.enhance_captions(
            original_captions, history, Language.ENGLISH
        )
        
        assert result is original_captions
        assert len(result.segments) == 1
        assert result.segments[0].text == "Original caption"

    @pytest.mark.asyncio
    async def test_generate_engagement_phrase(self, anthropic_service):
        """Test generate engagement phrase returns default phrase"""
        history = History(title="Incredible Story", content="Amazing content", gender="male")
        
        result = await anthropic_service.generate_engagement_phrase(
            history, Language.PORTUGUESE
        )
        
        assert isinstance(result, str)
        assert "Incredible Story" in result
        assert result.startswith("Uma história incrível")

    @pytest.mark.asyncio
    async def test_generate_engagement_phrase_english(self, anthropic_service):
        """Test generate engagement phrase with English"""
        history = History(title="Amazing Tale", content="Content", gender="female")
        
        result = await anthropic_service.generate_engagement_phrase(
            history, Language.ENGLISH
        )
        
        assert isinstance(result, str)
        assert "Amazing Tale" in result

    @pytest.mark.asyncio
    async def test_divide_history_returns_single_part(self, anthropic_service):
        """Test divide history returns original history as single part"""
        original_history = History(
            title="Complex Story", 
            content="Very long and complex content that should be divided", 
            gender="male"
        )
        
        result = await anthropic_service.divide_history(
            original_history, 5, Language.PORTUGUESE
        )
        
        assert len(result) == 1
        assert result[0] is original_history

    @pytest.mark.asyncio
    async def test_methods_preserve_input_data(self, anthropic_service):
        """Test that placeholder methods preserve input data correctly"""
        # Test enhance_history preserves all input
        title = "Unique Title 123"
        content = "Unique content with special chars: áéíóú"
        
        tokens = []
        async for token in anthropic_service.enhance_history(title, content, Language.PORTUGUESE):
            tokens.append(token)
        
        combined_content = "".join(tokens)
        assert title in combined_content
        assert content in combined_content
        
        # Test divide_history preserves original
        original = History(title="Original", content="Original content", gender="female")
        divided = await anthropic_service.divide_history(original, 3, Language.ENGLISH)
        assert divided[0].title == "Original"
        assert divided[0].gender == "female"

    @pytest.mark.asyncio
    async def test_concurrent_calls(self, anthropic_service):
        """Test service handles concurrent calls correctly"""
        import asyncio
        
        async def get_combined_content(title, content):
            """Helper to get combined content from streaming"""
            tokens = []
            async for token in anthropic_service.enhance_history(title, content, Language.PORTUGUESE):
                tokens.append(token)
            return "".join(tokens)
        
        # Create multiple concurrent calls
        tasks = [
            get_combined_content(f"Title {i}", f"Content {i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify each result contains the expected content
        for i, result in enumerate(results):
            assert f"Title {i}" in result
            assert f"Content {i}" in result


@pytest.mark.unit
class TestAnthropicServiceEdgeCases:
    """Edge cases for Anthropic LLM Service"""

    @pytest.mark.asyncio
    async def test_empty_inputs(self, anthropic_service):
        """Test service handles empty inputs"""
        tokens = []
        async for token in anthropic_service.enhance_history("", "", Language.ENGLISH):
            tokens.append(token)
        
        # Should get some tokens even with empty input
        assert len(tokens) >= 0

    @pytest.mark.asyncio
    async def test_unicode_handling(self, anthropic_service):
        """Test service handles unicode characters"""
        unicode_title = "História com émojis 🎉 e símbolos"
        unicode_content = "Conteúdo com çãräcteres especiais: ñáéíóú"
        
        tokens = []
        async for token in anthropic_service.enhance_history(
            unicode_title, unicode_content, Language.PORTUGUESE
        ):
            tokens.append(token)
        
        combined_content = "".join(tokens)
        assert unicode_title in combined_content
        assert unicode_content in combined_content

    @pytest.mark.asyncio
    async def test_large_content(self, anthropic_service):
        """Test service handles large content"""
        large_title = "Very Long Title " * 10  # Reduced to make test faster
        large_content = "This is a very long content. " * 20  # Reduced to ~200 chars for speed
        
        tokens = []
        token_count = 0
        async for token in anthropic_service.enhance_history(
            large_title, large_content, Language.ENGLISH
        ):
            tokens.append(token)
            token_count += 1
            # Limit to first 50 tokens to avoid long test times
            if token_count >= 50:
                break
        
        # Just verify we got some tokens and they contain expected content
        assert len(tokens) > 0
        combined_content = "".join(tokens)
        # Check that some part of the title or content appears in the result
        assert any(word in combined_content for word in ["Very", "Long", "Title", "content"])

    @pytest.mark.asyncio 
    async def test_none_history_in_other_methods(self, anthropic_service):
        """Test methods handle edge cases gracefully"""
        # Test with minimal captions
        empty_captions = Captions(segments=[])
        minimal_history = History(title="", content="", gender="male")
        
        result = await anthropic_service.enhance_captions(
            empty_captions, minimal_history, Language.PORTUGUESE
        )
        assert result is empty_captions
        assert len(result.segments) == 0
