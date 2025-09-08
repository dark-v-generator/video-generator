from pathlib import Path
from typing import List, Optional

from .interfaces import IFileRepository
from ..core.config import settings
from ..core.logging_config import get_logger


class LocalFileRepository(IFileRepository):
    """Local file system repository with configurable base path"""

    def __init__(self):
        """Initialize with optional base path override"""
        self._base_path = Path(settings.file_storage_base_path, "repository")
        # Create base directory if it doesn't exist
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._logger = get_logger(__name__)

    def save_record(self, collection_name: str, record_id: str, content: bytes) -> None:
        """Save record to local file system"""
        file_path = self._base_path / collection_name / f"{record_id}.yaml"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

    def load_record(self, collection_name: str, record_id: str) -> Optional[bytes]:
        """Load record from local file system"""
        file_path = self._base_path / collection_name / f"{record_id}.yaml"
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def delete_record(self, collection_name: str, record_id: str) -> bool:
        """Delete record from local file system"""
        file_path = self._base_path / collection_name / f"{record_id}.yaml"
        if not file_path.exists():
            return False
        file_path.unlink()
        return True

    def record_exists(self, collection_name: str, record_id: str) -> bool:
        """Check if record exists in local file system"""
        file_path = self._base_path / collection_name / f"{record_id}.yaml"
        return file_path.exists()

    def list_record_ids(self, collection_name: str) -> List[str]:
        """List records in local file system"""
        return [f.stem for f in (self._base_path / collection_name).glob("*.yaml")]
