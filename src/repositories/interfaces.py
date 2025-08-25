from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path

from ..entities.config import MainConfig
from ..entities.reddit_history import RedditHistory
from ..entities.history import History


class IConfigRepository(ABC):
    @abstractmethod
    def load_config(self) -> MainConfig:
        """Load configuration from file"""
        ...

    @abstractmethod
    def save_config(self, config: MainConfig) -> None:
        """Save configuration to file"""
        ...


class IHistoryRepository(ABC):
    @abstractmethod
    def save_reddit_history(self, history: RedditHistory) -> None:
        """Save Reddit history to storage"""
        ...

    @abstractmethod
    def load_reddit_history(self, history_id: str) -> Optional[RedditHistory]:
        """Load Reddit history by ID"""
        ...

    @abstractmethod
    def list_history_ids(self) -> List[str]:
        """List all history IDs"""
        ...

    @abstractmethod
    def delete_reddit_history(self, history_id: str) -> bool:
        """Delete Reddit history"""
        ...

    @abstractmethod
    def history_exists(self, history_id: str) -> bool:
        """Check if history exists"""
        ...

    @abstractmethod
    def save_speech_file(self, history_id: str, speech_bytes: bytes) -> None:
        """Save speech file to storage"""
        ...

    @abstractmethod
    def save_captions_file(self, history_id: str, captions_bytes: bytes) -> None:
        """Save captions file to storage"""
        ...

    @abstractmethod
    def save_cover_file(self, history_id: str, cover_bytes: bytes) -> None:
        """Save cover file to storage"""
        ...

    @abstractmethod
    def save_final_video_file(self, history_id: str, final_video_bytes: bytes) -> None:
        """Save final video file to storage"""
        ...

    @abstractmethod
    def get_speech_bytes(self, history_id: str) -> Optional[bytes]:
        """Get speech bytes from storage"""
        ...

    @abstractmethod
    def get_captions_bytes(self, history_id: str) -> Optional[bytes]:
        """Get captions bytes from storage"""
        ...

    @abstractmethod
    def get_cover_bytes(self, history_id: str) -> Optional[bytes]:
        """Get cover bytes from storage"""
        ...

    @abstractmethod
    def get_final_video_bytes(self, history_id: str) -> Optional[bytes]:
        """Get final video bytes from storage"""
        ...


class IFileRepository(ABC):
    @abstractmethod
    def save_record(self, collection_name: str, record_id: str, content: bytes) -> None:
        """Save record to storage"""
        ...

    @abstractmethod
    def load_record(self, collection_name: str, record_id: str) -> Optional[bytes]:
        """Load record from storage"""
        ...

    @abstractmethod
    def delete_record(self, collection_name: str, record_id: str) -> bool:
        """Delete record from storage"""
        ...

    @abstractmethod
    def record_exists(self, collection_name: str, record_id: str) -> bool:
        """Check if record exists"""
        ...

    @abstractmethod
    def list_record_ids(self, collection_name: str) -> List[str]:
        """List record ids"""
        ...


class IFileStorage(ABC):
    @abstractmethod
    def save_file(self, content: bytes, custom_id: str | None = None) -> str:
        """Save record to storage"""
        ...

    @abstractmethod
    def load_file(self, id: str | None) -> bytes | None:
        """Load record from storage"""
        ...

    @abstractmethod
    def delete_file(self, id: str | None) -> bool:
        """Delete record from storage"""
        ...

    @abstractmethod
    def get_file_url(self, id: str | None) -> str | None:
        """Get file URL for a given record ID"""
        ...
