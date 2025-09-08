import os
from typing import List, Optional
from datetime import datetime
import uuid

from .interfaces import IHistoryRepository, IFileRepository, IFileStorage
from ..entities.reddit_history import RedditHistory
from ..core.config import settings
from ..core.logging_config import get_logger


class FileHistoryRepository(IHistoryRepository):
    """File-based history repository using IFileRepository"""

    def __init__(self, file_repository: IFileRepository, file_storage: IFileStorage):
        """Initialize with file repository dependency"""
        self._file_repository = file_repository
        self._file_storage = file_storage
        self._histories_collection_name = settings.histories_collection_name
        self._logger = get_logger(__name__)

    def save_reddit_history(self, history: RedditHistory) -> None:
        """Save Reddit history using file repository"""
        history.last_updated_at = datetime.now()
        self._file_repository.save_record(
            self._histories_collection_name, history.id, history.to_bytes()
        )

    def load_reddit_history(self, history_id: str) -> Optional[RedditHistory]:
        """Load Reddit history using file repository"""
        history = self._file_repository.load_record(
            self._histories_collection_name, history_id
        )
        if history is None:
            return None
        return RedditHistory.from_bytes(history)

    def list_history_ids(self) -> List[str]:
        """List all history IDs using file repository"""
        return self._file_repository.list_record_ids(self._histories_collection_name)

    def delete_reddit_history(self, history_id: str) -> bool:
        """Delete Reddit history and associated files"""
        history = self.load_reddit_history(history_id)
        if history is None:
            return False
        if history.speech_file_id:
            self._file_storage.delete_file(history.speech_file_id)
        if history.captions_file_id:
            self._file_storage.delete_file(history.captions_file_id)
        if history.cover_file_id:
            self._file_storage.delete_file(history.cover_file_id)
        if history.final_video_file_id:
            self._file_storage.delete_file(history.final_video_file_id)
        return self._file_repository.delete_record(
            self._histories_collection_name, history_id
        )

    def history_exists(self, history_id: str) -> bool:
        """Check if history exists using file repository"""
        return self._file_repository.record_exists(
            self._histories_collection_name, history_id
        )

    def save_speech_file(self, history_id: str, speech_bytes: bytes) -> None:
        """Save speech file to storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            raise Exception("History not found")
        speech_file_id = history.speech_file_id or str(uuid.uuid4())
        history.speech_file_id = self._file_storage.save_file(
            speech_bytes, speech_file_id
        )
        self.save_reddit_history(history)

    def save_captions_file(self, history_id: str, captions_bytes: bytes) -> None:
        """Save captions file to storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            raise Exception("History not found")
        captions_file_id = history.captions_file_id or str(uuid.uuid4())
        history.captions_file_id = self._file_storage.save_file(
            captions_bytes, captions_file_id
        )
        self.save_reddit_history(history)

    def save_cover_file(self, history_id: str, cover_bytes: bytes) -> None:
        """Save cover file to storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            raise Exception("History not found")
        cover_file_id = history.cover_file_id or str(uuid.uuid4())
        history.cover_file_id = self._file_storage.save_file(cover_bytes, cover_file_id)
        self.save_reddit_history(history)

    def save_final_video_file(self, history_id: str, final_video_bytes: bytes) -> None:
        """Save final video file to storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            raise Exception("History not found")
        final_video_file_id = history.final_video_file_id or str(uuid.uuid4())
        history.final_video_file_id = self._file_storage.save_file(
            final_video_bytes, final_video_file_id
        )
        self.save_reddit_history(history)

    def get_speech_bytes(self, history_id: str) -> Optional[bytes]:
        """Get speech bytes from storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            return None
        return self._file_storage.load_file(history.speech_file_id)

    def get_captions_bytes(self, history_id: str) -> Optional[bytes]:
        """Get captions bytes from storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            return None
        return self._file_storage.load_file(history.captions_file_id)

    def get_cover_bytes(self, history_id: str) -> Optional[bytes]:
        """Get cover bytes from storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            return None
        return self._file_storage.load_file(history.cover_file_id)

    def get_final_video_bytes(self, history_id: str) -> Optional[bytes]:
        """Get final video bytes from storage"""
        history = self.load_reddit_history(history_id)
        if history is None:
            return None
        return self._file_storage.load_file(history.final_video_file_id)
