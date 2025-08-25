"""
Tests for HistoryRepository folder structure changes.

This module tests the updated folder structure from histories/{id}.yaml 
to histories/{id}/history.yaml, including backward compatibility.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock
from pathlib import Path

from src.repositories.history_repository import FileHistoryRepository
from src.entities.reddit_history import RedditHistory
from src.entities.history import History
from src.entities.cover import RedditCover
from src.entities.language import Language


class TestHistoryRepositoryFolderStructure:
    """Test HistoryRepository with new folder structure"""
    
    @pytest.fixture
    def mock_file_repository(self):
        """Create a mock file repository"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_file_repository):
        """Create repository with mocked file repository"""
        return FileHistoryRepository(mock_file_repository)
    
    @pytest.fixture
    def sample_reddit_history(self):
        """Create a sample RedditHistory for testing"""
        return RedditHistory(
            id="test-history-123",
            cover=RedditCover(
                image_url="https://example.com/image.png",
                author="test_author",
                community="r/test",
                title="Test Title"
            ),
            history=History(
                title="Test Title",
                content="Test content",
                gender="male"
            ),
            folder_path="/path/to/histories/test-history-123",
            language=Language.ENGLISH.value
        )
    
    def test_save_reddit_history_new_format(self, repository, mock_file_repository, sample_reddit_history):
        """Test saving Reddit history uses new folder structure"""
        # Act
        repository.save_reddit_history(sample_reddit_history)
        
        # Assert
        mock_file_repository.save_file.assert_called_once()
        call_args = mock_file_repository.save_file.call_args
        file_path = call_args[0][0]  # First argument
        
        # Should use new format: histories/{id}/history.yaml
        assert file_path == "histories/test-history-123/history.yaml"
        
        # Verify folder_path was updated correctly
        assert sample_reddit_history.folder_path.endswith("test-history-123")
    
    def test_save_reddit_history_updates_folder_path(self, repository, mock_file_repository):
        """Test saving Reddit history updates folder_path if incorrect"""
        # Arrange
        history = RedditHistory(
            id="test-history-456",
            history=History(title="Test", content="Content", gender="male"),
            folder_path="/wrong/path",  # Incorrect folder path
            language=Language.ENGLISH.value
        )
        
        # Act
        repository.save_reddit_history(history)
        
        # Assert
        assert history.folder_path.endswith("test-history-456")
        mock_file_repository.save_file.assert_called_once()
        call_args = mock_file_repository.save_file.call_args
        file_path = call_args[0][0]
        assert file_path == "histories/test-history-456/history.yaml"
    
    def test_load_reddit_history_new_format_exists(self, repository, mock_file_repository):
        """Test loading Reddit history when new format exists"""
        # Arrange
        yaml_content = """
id: test-history-123
history:
  title: Test Title
  content: Test content
  gender: male
folder_path: /path/to/histories/test-history-123
language: en
""".strip()
        
        mock_file_repository.load_file.return_value = yaml_content.encode('utf-8')
        
        # Act
        result = repository.load_reddit_history("test-history-123")
        
        # Assert
        assert result is not None
        assert result.id == "test-history-123"
        assert result.history.title == "Test Title"
        
        # Should try new format first
        mock_file_repository.load_file.assert_called_once_with("histories/test-history-123/history.yaml")
    
    def test_load_reddit_history_fallback_to_legacy(self, repository, mock_file_repository):
        """Test loading Reddit history falls back to legacy format"""
        # Arrange
        yaml_content = """
id: test-history-456
history:
  title: Legacy Title
  content: Legacy content
  gender: female
folder_path: /old/path/histories/test-history-456
language: pt
""".strip()
        
        # Mock: new format doesn't exist, legacy format exists
        def mock_load_file(path):
            if path.endswith("/history.yaml"):
                return None  # New format doesn't exist
            elif path.endswith(".yaml"):
                return yaml_content.encode('utf-8')  # Legacy format exists
            return None
        
        mock_file_repository.load_file.side_effect = mock_load_file
        
        # Act
        result = repository.load_reddit_history("test-history-456")
        
        # Assert
        assert result is not None
        assert result.id == "test-history-456"
        assert result.history.title == "Legacy Title"
        
        # Should have tried both formats
        assert mock_file_repository.load_file.call_count == 2
        calls = mock_file_repository.load_file.call_args_list
        assert calls[0][0][0] == "histories/test-history-456/history.yaml"  # New format first
        assert calls[1][0][0] == "histories/test-history-456.yaml"  # Legacy format second
    
    def test_load_reddit_history_updates_folder_path(self, repository, mock_file_repository):
        """Test loading Reddit history updates folder_path if incorrect"""
        # Arrange
        yaml_content = """
id: test-history-789
history:
  title: Test Title
  content: Test content
  gender: male
folder_path: /wrong/old/path
language: en
""".strip()
        
        mock_file_repository.load_file.return_value = yaml_content.encode('utf-8')
        
        # Act
        result = repository.load_reddit_history("test-history-789")
        
        # Assert
        assert result is not None
        assert result.folder_path.endswith("test-history-789")
    
    def test_load_reddit_history_not_found(self, repository, mock_file_repository):
        """Test loading Reddit history when neither format exists"""
        # Arrange
        mock_file_repository.load_file.return_value = None
        
        # Act
        result = repository.load_reddit_history("nonexistent-history")
        
        # Assert
        assert result is None
        
        # Should have tried both formats
        assert mock_file_repository.load_file.call_count == 2
    
    def test_list_history_ids_new_format(self, repository, mock_file_repository):
        """Test listing history IDs with new format"""
        # Arrange
        mock_file_repository.list_files.side_effect = [
            ["histories/id1/history.yaml", "histories/id2/history.yaml"],  # New format
            []  # Legacy format
        ]
        
        # Act
        result = repository.list_history_ids()
        
        # Assert
        assert set(result) == {"id1", "id2"}
        
        # Should have called list_files twice (new and legacy formats)
        assert mock_file_repository.list_files.call_count == 2
        calls = mock_file_repository.list_files.call_args_list
        assert calls[0][0][0] == "histories/*/history.yaml"
        assert calls[1][0][0] == "histories/*.yaml"
    
    def test_list_history_ids_legacy_format(self, repository, mock_file_repository):
        """Test listing history IDs with legacy format"""
        # Arrange
        mock_file_repository.list_files.side_effect = [
            [],  # New format
            ["histories/legacy1.yaml", "histories/legacy2.yaml"]  # Legacy format
        ]
        
        # Act
        result = repository.list_history_ids()
        
        # Assert
        assert set(result) == {"legacy1", "legacy2"}
    
    def test_list_history_ids_mixed_formats(self, repository, mock_file_repository):
        """Test listing history IDs with both new and legacy formats"""
        # Arrange
        mock_file_repository.list_files.side_effect = [
            ["histories/new1/history.yaml", "histories/new2/history.yaml"],  # New format
            ["histories/legacy1.yaml", "histories/legacy2.yaml"]  # Legacy format
        ]
        
        # Act
        result = repository.list_history_ids()
        
        # Assert
        assert set(result) == {"new1", "new2", "legacy1", "legacy2"}
    
    def test_list_history_ids_excludes_conflicts(self, repository, mock_file_repository):
        """Test listing history IDs excludes conflicting history.yaml in legacy format"""
        # Arrange
        mock_file_repository.list_files.side_effect = [
            ["histories/id1/history.yaml"],  # New format
            ["histories/history.yaml", "histories/id2.yaml"]  # Legacy format (with conflict)
        ]
        
        # Act
        result = repository.list_history_ids()
        
        # Assert
        # Should exclude "history" from legacy format to avoid conflicts
        assert set(result) == {"id1", "id2"}
    
    def test_delete_reddit_history_new_format(self, repository, mock_file_repository):
        """Test deleting Reddit history with new format (directory)"""
        # Arrange
        mock_file_repository.delete_directory.return_value = True
        
        # Act
        result = repository.delete_reddit_history("test-history-123")
        
        # Assert
        assert result is True
        mock_file_repository.delete_directory.assert_called_once_with("histories/test-history-123")
        mock_file_repository.delete_file.assert_not_called()
    
    def test_delete_reddit_history_fallback_to_legacy(self, repository, mock_file_repository):
        """Test deleting Reddit history falls back to legacy format"""
        # Arrange
        mock_file_repository.delete_directory.return_value = False  # Directory deletion fails
        mock_file_repository.delete_file.return_value = True  # File deletion succeeds
        
        # Act
        result = repository.delete_reddit_history("test-history-456")
        
        # Assert
        assert result is True
        mock_file_repository.delete_directory.assert_called_once_with("histories/test-history-456")
        mock_file_repository.delete_file.assert_called_once_with("histories/test-history-456.yaml")
    
    def test_delete_reddit_history_both_fail(self, repository, mock_file_repository):
        """Test deleting Reddit history when both formats fail"""
        # Arrange
        mock_file_repository.delete_directory.return_value = False
        mock_file_repository.delete_file.return_value = False
        
        # Act
        result = repository.delete_reddit_history("test-history-789")
        
        # Assert
        assert result is False
    
    def test_delete_reddit_history_exception_handling(self, repository, mock_file_repository):
        """Test deleting Reddit history handles exceptions gracefully"""
        # Arrange
        mock_file_repository.delete_directory.side_effect = Exception("Deletion error")
        
        # Act
        result = repository.delete_reddit_history("test-history-error")
        
        # Assert
        assert result is False
    
    def test_history_exists_new_format(self, repository, mock_file_repository):
        """Test checking if history exists with new format"""
        # Arrange
        mock_file_repository.file_exists.side_effect = lambda path: path.endswith("/history.yaml")
        
        # Act
        result = repository.history_exists("test-history-123")
        
        # Assert
        assert result is True
        mock_file_repository.file_exists.assert_called_once_with("histories/test-history-123/history.yaml")
    
    def test_history_exists_legacy_format(self, repository, mock_file_repository):
        """Test checking if history exists with legacy format"""
        # Arrange
        def mock_file_exists(path):
            if path.endswith("/history.yaml"):
                return False  # New format doesn't exist
            elif path.endswith(".yaml"):
                return True  # Legacy format exists
            return False
        
        mock_file_repository.file_exists.side_effect = mock_file_exists
        
        # Act
        result = repository.history_exists("test-history-456")
        
        # Assert
        assert result is True
        assert mock_file_repository.file_exists.call_count == 2
    
    def test_history_exists_not_found(self, repository, mock_file_repository):
        """Test checking if history exists when neither format exists"""
        # Arrange
        mock_file_repository.file_exists.return_value = False
        
        # Act
        result = repository.history_exists("nonexistent-history")
        
        # Assert
        assert result is False
        assert mock_file_repository.file_exists.call_count == 2


class TestHistoryRepositoryFolderStructureEdgeCases:
    """Edge cases for HistoryRepository folder structure changes"""
    
    @pytest.fixture
    def repository_with_mock(self):
        """Create repository with mocked file repository"""
        return FileHistoryRepository(Mock())
    
    def test_save_reddit_history_empty_folder_path(self, repository_with_mock):
        """Test saving Reddit history with empty folder_path"""
        # Arrange
        history = RedditHistory(
            id="empty-path-test",
            history=History(title="Test", content="Content", gender="male"),
            folder_path="",  # Empty folder path
            language=Language.ENGLISH.value
        )
        
        # Act
        repository_with_mock.save_reddit_history(history)
        
        # Assert
        assert history.folder_path.endswith("empty-path-test")
        repository_with_mock._file_repository.save_file.assert_called_once()
    
    def test_save_reddit_history_none_folder_path(self, repository_with_mock):
        """Test saving Reddit history with None folder_path"""
        # Arrange
        # Create history with valid folder_path first, then modify it
        history = RedditHistory(
            id="none-path-test",
            history=History(title="Test", content="Content", gender="male"),
            folder_path="/temp/path",  # Valid initial path
            language=Language.ENGLISH.value
        )
        # Manually set folder_path to None to test the edge case
        history.__dict__['folder_path'] = None
        
        # Act
        repository_with_mock.save_reddit_history(history)
        
        # Assert
        assert history.folder_path is not None
        assert history.folder_path.endswith("none-path-test")
    
    def test_load_reddit_history_invalid_yaml(self, repository_with_mock):
        """Test loading Reddit history with invalid YAML content"""
        # Arrange
        invalid_yaml = "invalid: yaml: content: [unclosed"
        repository_with_mock._file_repository.load_file.return_value = invalid_yaml.encode('utf-8')
        
        # Act
        result = repository_with_mock.load_reddit_history("invalid-yaml-test")
        
        # Assert
        assert result is None
    
    def test_load_reddit_history_unicode_decode_error(self, repository_with_mock):
        """Test loading Reddit history with invalid UTF-8 content"""
        # Arrange
        invalid_utf8 = b'\xff\xfe\x00\x00'  # Invalid UTF-8 bytes
        repository_with_mock._file_repository.load_file.return_value = invalid_utf8
        
        # Act
        result = repository_with_mock.load_reddit_history("invalid-utf8-test")
        
        # Assert
        assert result is None
    
    def test_list_history_ids_complex_paths(self, repository_with_mock):
        """Test listing history IDs with complex file paths"""
        # Arrange
        complex_paths = [
            "histories/id-with-dashes/history.yaml",
            "histories/id_with_underscores/history.yaml",
            "histories/123-numeric-id/history.yaml",
            "histories/very-long-id-with-many-characters-and-numbers-123456/history.yaml"
        ]
        
        repository_with_mock._file_repository.list_files.side_effect = [
            complex_paths,  # New format
            []  # Legacy format
        ]
        
        # Act
        result = repository_with_mock.list_history_ids()
        
        # Assert
        expected_ids = {
            "id-with-dashes",
            "id_with_underscores", 
            "123-numeric-id",
            "very-long-id-with-many-characters-and-numbers-123456"
        }
        assert set(result) == expected_ids
