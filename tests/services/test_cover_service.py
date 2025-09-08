import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.services.cover_service import CoverService
from src.entities.cover import RedditCover
from src.entities.config import MainConfig, CoverConfig


class TestCoverService:
    """Test CoverService functionality"""

    @pytest.fixture
    def cover_service(self):
        return CoverService()

    @pytest.fixture
    def sample_reddit_cover(self):
        return RedditCover(
            title="Test Reddit Post Title",
            community="TestSubreddit",
            author="test_user",
            image_url="https://example.com/image.jpg"
        )

    @pytest.fixture
    def sample_config(self):
        config = MainConfig()
        config.cover_config = CoverConfig(title_font_size=64)
        return config

    @patch('src.services.cover_service.async_playwright')
    @pytest.mark.asyncio
    async def test_generate_cover_returns_bytes(
        self,
        mock_playwright,
        cover_service,
        sample_reddit_cover,
        sample_config
    ):
        """Test that generate_cover returns PNG bytes"""
        # Mock the PNG file content
        mock_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00'
        
        # Mock Playwright components
        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock(return_value=mock_png_bytes)
        
        mock_page = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.screenshot = AsyncMock(return_value=mock_png_bytes)
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_playwright.return_value = mock_playwright_instance
        
        result = await cover_service.generate_cover(sample_reddit_cover, sample_config)
        
        # Verify result is bytes
        assert isinstance(result, bytes)
        assert result == mock_png_bytes
        
        # Verify Playwright was called correctly
        mock_playwright_instance.chromium.launch.assert_called_once()
        mock_browser.new_page.assert_called_once()
        mock_page.set_content.assert_called_once()
        mock_page.query_selector.assert_called_once_with('.post-cover')
        mock_element.screenshot.assert_called_once_with(type='png', omit_background=True)
        mock_browser.close.assert_called_once()

    @patch('src.services.cover_service.async_playwright')
    @pytest.mark.asyncio
    async def test_generate_cover_fallback_screenshot(
        self,
        mock_playwright,
        cover_service,
        sample_reddit_cover,
        sample_config
    ):
        """Test fallback to full page screenshot when element not found"""
        mock_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00'
        
        mock_page = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)  # Element not found
        mock_page.screenshot = AsyncMock(return_value=mock_png_bytes)
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_playwright.return_value = mock_playwright_instance
        
        result = await cover_service.generate_cover(sample_reddit_cover, sample_config)
        
        # Verify result is bytes
        assert isinstance(result, bytes)
        assert result == mock_png_bytes
        
        # Verify fallback screenshot was used
        mock_page.query_selector.assert_called_once_with('.post-cover')
        mock_page.screenshot.assert_called_once_with(type='png', full_page=True, omit_background=True)

    @patch('src.services.cover_service.async_playwright')
    @pytest.mark.asyncio
    async def test_generate_cover_error_handling(
        self,
        mock_playwright,
        cover_service,
        sample_reddit_cover,
        sample_config
    ):
        """Test error handling in cover generation"""
        # Mock Playwright to raise an exception
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch = AsyncMock(side_effect=Exception("Browser launch failed"))
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_playwright.return_value = mock_playwright_instance
        
        with pytest.raises(Exception, match="Browser launch failed"):
            await cover_service.generate_cover(sample_reddit_cover, sample_config)

    def test_generate_reddit_cover_html_method(
        self,
        cover_service,
        sample_reddit_cover,
        sample_config
    ):
        """Test the HTML generation method directly"""
        html_bytes = cover_service._generate_reddit_cover_html(
            sample_reddit_cover, 
            sample_config.cover_config
        )
        
        assert isinstance(html_bytes, bytes)
        html_string = html_bytes.decode('utf-8')
        
        # Verify HTML contains expected data
        assert "Test Reddit Post Title" in html_string
        assert "TestSubreddit" in html_string
        assert "test_user" in html_string
        assert "https://example.com/image.jpg" in html_string
        assert "64px" in html_string


class TestCoverServiceEdgeCases:
    """Edge cases for CoverService"""

    @pytest.fixture
    def cover_service(self):
        return CoverService()

    @patch('src.services.cover_service.async_playwright')
    @pytest.mark.asyncio
    async def test_empty_cover_data(
        self,
        mock_playwright,
        cover_service
    ):
        """Test with empty cover data"""
        empty_cover = RedditCover(title="", community="", author="", image_url="")
        config = MainConfig()
        
        mock_png_bytes = b'fake_png_data'
        
        # Mock Playwright components
        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock(return_value=mock_png_bytes)
        
        mock_page = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_playwright.return_value = mock_playwright_instance
        
        result = await cover_service.generate_cover(empty_cover, config)
        
        assert isinstance(result, bytes)
        assert result == mock_png_bytes

    @patch('src.services.cover_service.async_playwright')
    @pytest.mark.asyncio
    async def test_special_characters_in_cover(
        self,
        mock_playwright,
        cover_service
    ):
        """Test with special characters in cover data"""
        special_cover = RedditCover(
            title="Test with émojis 🎉 and spéciál chars",
            community="TestSubreddit",
            author="tëst_üsér",
            image_url="https://example.com/image.jpg"
        )
        config = MainConfig()
        
        mock_png_bytes = b'fake_png_data'
        
        # Mock Playwright components
        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock(return_value=mock_png_bytes)
        
        mock_page = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()
        mock_page.set_content = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = AsyncMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_playwright.return_value = mock_playwright_instance
        
        result = await cover_service.generate_cover(special_cover, config)
        
        assert isinstance(result, bytes)
        assert result == mock_png_bytes

    def test_html_generation_with_custom_font_size(self, cover_service):
        """Test HTML generation with different font sizes"""
        cover = RedditCover(title="Test", community="Test", author="Test", image_url="")
        
        # Test with custom font size
        config = CoverConfig(title_font_size=48)
        html_bytes = cover_service._generate_reddit_cover_html(cover, config)
        html_string = html_bytes.decode('utf-8')
        
        assert "48px" in html_string
        
        # Test with different font size
        config = CoverConfig(title_font_size=72)
        html_bytes = cover_service._generate_reddit_cover_html(cover, config)
        html_string = html_bytes.decode('utf-8')
        
        assert "72px" in html_string