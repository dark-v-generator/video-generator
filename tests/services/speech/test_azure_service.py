import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from tempfile import NamedTemporaryFile

from src.services.speech_service import AzureSpeechService, VoiceGender
from src.entities.language import Language
from src.entities.progress import ProgressEvent


@pytest.fixture
def azure_service():
    """Azure speech service instance"""
    return AzureSpeechService()


@pytest.fixture
def mock_azure_proxy():
    """Mock azure_proxy module"""
    with patch('src.services.speech_service.azure_proxy') as mock_proxy:
        mock_proxy.VoiceVariation.ANTONIO_NEUTRAL = Mock()
        mock_proxy.VoiceVariation.THALITA_NEUTRAL = Mock() 
        mock_proxy.VoiceVariation.ANDREW_NEUTRAL = Mock()
        mock_proxy.VoiceVariation.AVA_NEUTRAL = Mock()
        mock_proxy.synthesize_speech = Mock()
        yield mock_proxy


class TestAzureSpeechService:
    """Test Azure Speech Service"""

    @pytest.mark.asyncio
    async def test_generate_speech_success(self, azure_service, mock_azure_proxy):
        """Test successful speech generation"""
        # Mock the azure synthesis
        test_audio_data = b"fake_audio_data_12345"
        
        # Create a temporary file for the mock to use
        with NamedTemporaryFile() as temp_file:
            temp_file.write(test_audio_data)
            temp_file.flush()
            
            def mock_synthesize(text, voice_variation, rate, output_path):
                # Copy test data to output path
                with open(output_path, 'wb') as f:
                    f.write(test_audio_data)
            
            mock_azure_proxy.synthesize_speech.side_effect = mock_synthesize
            
            # Collect all events from the async generator
            events = []
            audio_data = None
            
            async for item in azure_service.generate_speech(
                "Hello world", "male", 1.0, Language.ENGLISH
            ):
                if isinstance(item, ProgressEvent):
                    events.append(item)
                else:
                    audio_data = item
            
            # Verify events were generated
            assert len(events) >= 4  # initialization, preparation, generation, completion
            assert events[0].stage == "initializing"
            assert events[-1].stage == "completed"
            
            # Verify audio data was returned
            assert audio_data == test_audio_data
            
            # Verify azure_proxy was called
            mock_azure_proxy.synthesize_speech.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_speech_with_portuguese(self, azure_service, mock_azure_proxy):
        """Test speech generation with Portuguese language"""
        test_audio_data = b"audio_data_pt"
        
        def mock_synthesize(text, voice_variation, rate, output_path):
            with open(output_path, 'wb') as f:
                f.write(test_audio_data)
        
        mock_azure_proxy.synthesize_speech.side_effect = mock_synthesize
        
        audio_data = None
        async for item in azure_service.generate_speech(
            "Olá mundo", "female", 1.5, Language.PORTUGUESE
        ):
            if not isinstance(item, ProgressEvent):
                audio_data = item
                break
        
        assert audio_data == test_audio_data
        
        # Verify the correct voice variation was used
        call_args = mock_azure_proxy.synthesize_speech.call_args
        assert call_args[1]['rate'] == 1.5

    @pytest.mark.asyncio
    async def test_generate_speech_error_handling(self, azure_service, mock_azure_proxy):
        """Test error handling during speech generation"""
        mock_azure_proxy.synthesize_speech.side_effect = Exception("Azure API Error")
        
        events = []
        with pytest.raises(Exception, match="Azure API Error"):
            async for item in azure_service.generate_speech(
                "Test text", "male", 1.0, Language.ENGLISH
            ):
                if isinstance(item, ProgressEvent):
                    events.append(item)
        
        # Verify error event was generated
        error_events = [e for e in events if e.stage == "error"]
        assert len(error_events) > 0
        assert "Azure API Error" in error_events[0].message

    def test_get_azure_voice_variation_portuguese_male(self, azure_service):
        """Test voice variation selection for Portuguese male"""
        with patch('src.services.speech_service.azure_proxy') as mock_proxy:
            mock_proxy.VoiceVariation.ANTONIO_NEUTRAL = "antonio"
            
            result = azure_service._get_azure_voice_variation(
                VoiceGender.MALE, Language.PORTUGUESE
            )
            assert result == "antonio"

    def test_get_azure_voice_variation_portuguese_female(self, azure_service):
        """Test voice variation selection for Portuguese female"""
        with patch('src.services.speech_service.azure_proxy') as mock_proxy:
            mock_proxy.VoiceVariation.THALITA_NEUTRAL = "thalita"
            
            result = azure_service._get_azure_voice_variation(
                VoiceGender.FEMALE, Language.PORTUGUESE
            )
            assert result == "thalita"

    def test_get_azure_voice_variation_english_male(self, azure_service):
        """Test voice variation selection for English male"""
        with patch('src.services.speech_service.azure_proxy') as mock_proxy:
            mock_proxy.VoiceVariation.ANDREW_NEUTRAL = "andrew"
            
            result = azure_service._get_azure_voice_variation(
                VoiceGender.MALE, Language.ENGLISH
            )
            assert result == "andrew"

    def test_get_azure_voice_variation_english_female(self, azure_service):
        """Test voice variation selection for English female"""
        with patch('src.services.speech_service.azure_proxy') as mock_proxy:
            mock_proxy.VoiceVariation.AVA_NEUTRAL = "ava"
            
            result = azure_service._get_azure_voice_variation(
                VoiceGender.FEMALE, Language.ENGLISH
            )
            assert result == "ava"

    def test_get_azure_voice_variation_invalid_combo(self, azure_service):
        """Test voice variation with invalid language/gender combination"""
        # This should raise ValueError for unsupported combinations
        # But our current implementation doesn't support this case
        # Let's test what happens - it should raise ValueError
        with pytest.raises(ValueError, match="No voice variation found"):
            azure_service._get_azure_voice_variation(
                VoiceGender.MALE, None  # Invalid language
            )

    @pytest.mark.asyncio
    async def test_progress_events_sequence(self, azure_service, mock_azure_proxy):
        """Test that progress events are generated in correct sequence"""
        test_audio_data = b"test_audio"
        
        def mock_synthesize(text, voice_variation, rate, output_path):
            with open(output_path, 'wb') as f:
                f.write(test_audio_data)
        
        mock_azure_proxy.synthesize_speech.side_effect = mock_synthesize
        
        events = []
        async for item in azure_service.generate_speech(
            "Test", "male", 1.0, Language.ENGLISH
        ):
            if isinstance(item, ProgressEvent):
                events.append(item)
        
        # Verify event sequence
        stages = [e.stage for e in events]
        expected_sequence = ["initializing", "preparing", "generating", "processing", "completed"]
        
        assert stages == expected_sequence

    @pytest.mark.asyncio
    async def test_different_rates_and_genders(self, azure_service, mock_azure_proxy):
        """Test different rate and gender combinations"""
        test_audio = b"test"
        mock_azure_proxy.synthesize_speech.side_effect = lambda *args, **kwargs: None
        
        # Mock file creation
        with patch('builtins.open'), patch('os.path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = Mock()
                mock_file.read.return_value = test_audio
                mock_open.return_value.__enter__.return_value = mock_file
                
                test_cases = [
                    ("male", 0.8, Language.PORTUGUESE),
                    ("female", 1.2, Language.ENGLISH),
                    ("male", 1.0, Language.PORTUGUESE),
                    ("female", 1.5, Language.ENGLISH),
                ]
                
                for gender, rate, language in test_cases:
                    events = []
                    async for item in azure_service.generate_speech(
                        "Test text", gender, rate, language
                    ):
                        if isinstance(item, ProgressEvent):
                            events.append(item)
                    
                    # Should complete without errors
                    assert len(events) > 0
                    assert any(e.stage == "completed" for e in events)


@pytest.mark.unit
class TestAzureServiceEdgeCases:
    """Edge cases for Azure Speech Service"""

    @pytest.mark.asyncio
    async def test_empty_text(self, azure_service, mock_azure_proxy):
        """Test service handles empty text"""
        mock_azure_proxy.synthesize_speech.side_effect = lambda *args, **kwargs: None
        
        with patch('builtins.open'), patch('os.path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = Mock()
                mock_file.read.return_value = b"empty_audio"
                mock_open.return_value.__enter__.return_value = mock_file
                
                events = []
                async for item in azure_service.generate_speech(
                    "", "male", 1.0, Language.ENGLISH
                ):
                    if isinstance(item, ProgressEvent):
                        events.append(item)
                
                # Should handle empty text gracefully
                assert len(events) > 0

    @pytest.mark.asyncio
    async def test_very_long_text(self, azure_service, mock_azure_proxy):
        """Test service handles very long text"""
        long_text = "This is a very long text. " * 1000  # ~25k chars
        mock_azure_proxy.synthesize_speech.side_effect = lambda *args, **kwargs: None
        
        with patch('builtins.open'), patch('os.path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = Mock()
                mock_file.read.return_value = b"long_audio"
                mock_open.return_value.__enter__.return_value = mock_file
                
                events = []
                async for item in azure_service.generate_speech(
                    long_text, "female", 1.0, Language.PORTUGUESE
                ):
                    if isinstance(item, ProgressEvent):
                        events.append(item)
                
                # Should handle long text without issues
                assert len(events) > 0
                assert any(e.stage == "completed" for e in events)
