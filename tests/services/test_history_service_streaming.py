"""
Tests for HistoryService streaming speech generation functionality.

This module tests the new streaming speech generation method that was moved
from the API router to the HistoryService, following clean architecture principles.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from typing import AsyncIterable, Union

from src.services.history_service import HistoryService
from src.entities.reddit_history import RedditHistory
from src.entities.history import History
from src.entities.cover import RedditCover
from src.entities.config import MainConfig
from src.entities.language import Language
from src.models.progress import ProgressEvent


class TestHistoryServiceStreamingSpeech:
    """Test HistoryService streaming speech generation functionality"""
    
    @pytest.fixture
    def mock_history_repository(self):
        return Mock()
    
    @pytest.fixture
    def mock_config_service(self):
        return Mock()
    
    @pytest.fixture
    def mock_speech_service(self):
        mock = Mock()
        # Make generate_speech return an async generator
        async def mock_generate_speech(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50)
            yield b"fake_audio_data"
        mock.generate_speech = mock_generate_speech
        return mock
    
    @pytest.fixture
    def mock_captions_service(self):
        return Mock()
    
    @pytest.fixture
    def mock_cover_service(self):
        return Mock()
    
    @pytest.fixture
    def mock_video_service(self):
        return Mock()
    
    @pytest.fixture
    def mock_llm_service(self):
        return Mock()
    
    @pytest.fixture
    def mock_file_repository(self):
        mock = Mock()
        mock.save_file = Mock()
        mock.create_directory = Mock()
        mock.get_file_url = Mock(return_value="/api/files/test-history-123/speech.mp3")
        return mock
    
    @pytest.fixture
    def service(self, mock_history_repository, mock_config_service, mock_speech_service,
                mock_captions_service, mock_cover_service, mock_video_service, mock_llm_service,
                mock_file_repository):
        return HistoryService(
            history_repository=mock_history_repository,
            config_service=mock_config_service,
            speech_service=mock_speech_service,
            captions_service=mock_captions_service,
            cover_service=mock_cover_service,
            video_service=mock_video_service,
            llm_service=mock_llm_service,
            file_repository=mock_file_repository
        )
    
    @pytest.fixture
    def sample_reddit_history(self):
        """Create a sample RedditHistory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            history_id = "test-history-123"
            folder_path = os.path.join(temp_dir, "histories", history_id)
            
            return RedditHistory(
                id=history_id,
                cover=RedditCover(
                    image_url="https://example.com/image.png",
                    author="test_author",
                    community="r/test",
                    title="Test Title"
                ),
                history=History(
                    title="Test Title",
                    content="Test content for speech generation",
                    gender="male"
                ),
                folder_path=folder_path,
                language=Language.ENGLISH.value
            )
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample MainConfig for testing"""
        return MainConfig()
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_success(self, service, mock_speech_service, 
                                                   sample_reddit_history, sample_config):
        """Test successful streaming speech generation"""
        # Arrange
        audio_data = b"fake_audio_data"
        
        # Mock speech service to return progress events and final audio
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50)
            yield audio_data
        
        mock_speech_service.generate_speech = mock_speech_generator
        
        # Act
        events = []
        final_history = None
        
        async for event in service.generate_speech_streaming(
            sample_reddit_history, rate=1.0, config=sample_config
        ):
            if isinstance(event, ProgressEvent):
                events.append(event)
            else:
                final_history = event
        
        # Assert
        assert len(events) >= 4  # initializing, preparing, processing, saving, completed
        assert any(event.stage == "initializing" for event in events)
        assert any(event.stage == "preparing" for event in events)
        assert any(event.stage == "processing" for event in events)
        assert any(event.stage == "saving" for event in events)
        assert any(event.stage == "completed" for event in events)
        
        assert final_history is not None
        assert isinstance(final_history, RedditHistory)
        assert final_history.speech_path is not None
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_no_audio_data(self, service, mock_speech_service,
                                                         sample_reddit_history, sample_config):
        """Test streaming speech generation when no audio data is received"""
        # Arrange
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50)
            # No audio data yielded
        
        mock_speech_service.generate_speech = mock_speech_generator
        
        # Act & Assert
        events = []
        exception_raised = False
        
        try:
            async for event in service.generate_speech_streaming(
                sample_reddit_history, rate=1.0, config=sample_config
            ):
                if isinstance(event, ProgressEvent):
                    events.append(event)
        except Exception as e:
            exception_raised = True
            assert "No audio data received from speech service" in str(e)
        
        # Verify exception was raised and error event was yielded
        assert exception_raised
        error_events = [e for e in events if e.stage == "error"]
        assert len(error_events) > 0
        assert "No audio data received" in error_events[0].message
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_speech_service_error(self, service, mock_speech_service,
                                                                sample_reddit_history, sample_config):
        """Test streaming speech generation when speech service raises an error"""
        # Arrange
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50)
            raise Exception("Speech service error")
        
        mock_speech_service.generate_speech = mock_speech_generator
        
        # Act & Assert
        events = []
        exception_raised = False
        
        try:
            async for event in service.generate_speech_streaming(
                sample_reddit_history, rate=1.0, config=sample_config
            ):
                if isinstance(event, ProgressEvent):
                    events.append(event)
        except Exception as e:
            exception_raised = True
            # The exception could be the original or wrapped
            assert "Speech service error" in str(e)
        
        # Verify exception was raised and error event was yielded
        assert exception_raised
        error_events = [e for e in events if e.stage == "error"]
        assert len(error_events) > 0
        assert "Speech service error" in error_events[0].message
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_creates_directory(self, service, mock_speech_service,
                                                             sample_reddit_history, sample_config,
                                                             mock_file_repository):
        """Test that streaming speech generation saves file using repository"""
        # Arrange
        audio_data = b"fake_audio_data"
        
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50)
            yield audio_data
        
        mock_speech_service.generate_speech = mock_speech_generator
        
        # Update history ID for this test
        history_id = "test-history-456"
        sample_reddit_history.id = history_id
        
        # Act
        final_history = None
        async for event in service.generate_speech_streaming(
            sample_reddit_history, rate=1.0, config=sample_config
        ):
            if not isinstance(event, ProgressEvent):
                final_history = event
        
        # Assert
        assert final_history is not None
        # Verify file repository save_file was called with correct path and data
        mock_file_repository.save_file.assert_called_once_with(
            f"histories/{history_id}/speech.mp3", audio_data
        )
        # Verify get_file_url was called and speech_path was set
        mock_file_repository.get_file_url.assert_called_once_with(f"histories/{history_id}/speech.mp3")
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_progress_details(self, service, mock_speech_service,
                                                            sample_reddit_history, sample_config):
        """Test that progress events contain appropriate details"""
        # Arrange
        audio_data = b"fake_audio_data"
        
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Generating speech", progress=50, 
                                     details={"tokens": 100})
            yield audio_data
        
        mock_speech_service.generate_speech = mock_speech_generator
        
        # Act
        events = []
        async for event in service.generate_speech_streaming(
            sample_reddit_history, rate=1.0, config=sample_config
        ):
            if isinstance(event, ProgressEvent):
                events.append(event)
        
        # Assert
        initializing_events = [e for e in events if e.stage == "initializing"]
        assert len(initializing_events) > 0
        assert "history_id" in initializing_events[0].details
        assert initializing_events[0].details["history_id"] == sample_reddit_history.id
        
        preparing_events = [e for e in events if e.stage == "preparing"]
        assert len(preparing_events) > 0
        assert "text_length" in preparing_events[0].details
        assert "language" in preparing_events[0].details
        
        saving_events = [e for e in events if e.stage == "saving"]
        assert len(saving_events) > 0
        assert "file_path" in saving_events[0].details
        
        completed_events = [e for e in events if e.stage == "completed"]
        assert len(completed_events) > 0
        assert "speech_path" in completed_events[0].details


class TestHistoryServiceStreamingSpeechEdgeCases:
    """Edge cases for HistoryService streaming speech generation"""
    
    @pytest.fixture
    def service_with_mocks(self):
        """Create service with all mocked dependencies"""
        mock_file_repo = Mock()
        mock_file_repo.save_file = Mock()
        mock_file_repo.get_file_url = Mock(return_value="/api/files/test/speech.mp3")
        
        return HistoryService(
            history_repository=Mock(),
            config_service=Mock(),
            speech_service=Mock(),
            captions_service=Mock(),
            cover_service=Mock(),
            video_service=Mock(),
            llm_service=Mock(),
            file_repository=mock_file_repo
        )
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_empty_content(self, service_with_mocks):
        """Test streaming speech generation with empty content"""
        # Arrange
        reddit_history = RedditHistory(
            id="empty-test",
            history=History(title="", content="", gender="male"),
            folder_path="/tmp/test",
            language=Language.ENGLISH.value
        )
        
        audio_data = b"empty_audio"
        
        async def mock_speech_generator(*args, **kwargs):
            yield ProgressEvent.create("processing", "Processing empty content", progress=50)
            yield audio_data
        
        service_with_mocks._speech_service.generate_speech = mock_speech_generator
        service_with_mocks.save_reddit_history = Mock()
        
        # Act
        events = []
        final_history = None
        
        with patch('pathlib.Path'):
            async for event in service_with_mocks.generate_speech_streaming(
                reddit_history, rate=1.0, config=MainConfig()
            ):
                if isinstance(event, ProgressEvent):
                    events.append(event)
                else:
                    final_history = event
        
        # Assert
        assert final_history is not None
        preparing_events = [e for e in events if e.stage == "preparing"]
        assert len(preparing_events) > 0
        assert preparing_events[0].details["text_length"] == 2  # "\n " from empty title and content
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_different_languages(self, service_with_mocks):
        """Test streaming speech generation with different languages"""
        languages_to_test = [Language.ENGLISH, Language.PORTUGUESE]
        
        for language in languages_to_test:
            # Arrange
            reddit_history = RedditHistory(
                id=f"lang-test-{language.value}",
                history=History(title="Test", content="Content", gender="female"),
                folder_path="/tmp/test",
                language=language.value
            )
            
            async def mock_speech_generator(*args, **kwargs):
                yield ProgressEvent.create("processing", f"Processing {language.value}", progress=50)
                yield b"audio_data"
            
            service_with_mocks._speech_service.generate_speech = mock_speech_generator
            service_with_mocks.save_reddit_history = Mock()
            
            # Act
            events = []
            with patch('pathlib.Path'):
                async for event in service_with_mocks.generate_speech_streaming(
                    reddit_history, rate=1.5, config=MainConfig()
                ):
                    if isinstance(event, ProgressEvent):
                        events.append(event)
            
            # Assert
            preparing_events = [e for e in events if e.stage == "preparing"]
            assert len(preparing_events) > 0
            assert preparing_events[0].details["language"] == language.value
    
    @pytest.mark.asyncio
    async def test_generate_speech_streaming_concurrent_calls(self, service_with_mocks):
        """Test multiple concurrent streaming speech generation calls"""
        import asyncio
        
        # Arrange
        histories = [
            RedditHistory(
                id=f"concurrent-test-{i}",
                history=History(title=f"Title {i}", content=f"Content {i}", gender="male"),
                folder_path=f"/tmp/test-{i}",
                language=Language.ENGLISH.value
            )
            for i in range(3)
        ]
        
        def create_mock_speech_generator(history_id):
            async def mock_speech_generator(*args, **kwargs):
                yield ProgressEvent.create("processing", f"Processing {history_id}", progress=50)
                yield f"audio_data_{history_id}".encode()
            return mock_speech_generator
        
        service_with_mocks.save_reddit_history = Mock()
        
        async def process_history(history):
            service_with_mocks._speech_service.generate_speech = create_mock_speech_generator(history.id)
            
            events = []
            final_result = None
            
            with patch('pathlib.Path'):
                async for event in service_with_mocks.generate_speech_streaming(
                    history, rate=1.0, config=MainConfig()
                ):
                    if isinstance(event, ProgressEvent):
                        events.append(event)
                    else:
                        final_result = event
            
            return events, final_result
        
        # Act
        results = await asyncio.gather(*[process_history(h) for h in histories])
        
        # Assert
        assert len(results) == 3
        for i, (events, final_result) in enumerate(results):
            assert final_result is not None
            assert final_result.id == f"concurrent-test-{i}"
            assert len(events) >= 4  # At least initializing, preparing, processing, saving, completed