from pathlib import Path
import uuid

from .interfaces import IFileStorage
from...core.config import settings


class LocalFileStorage(IFileStorage):
    """Local file system repository with configurable base path"""

    def __init__(self):
        """Initialize with optional base path override"""
        self._base_path = Path(settings.file_storage_base_path, "file.storage")
        # Create base directory if it doesn't exist
        self._base_path.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, custom_id: str | None = None) -> str:
        """Save file to storage"""
        file_id = custom_id or str(uuid.uuid4())
        file_path = self._base_path / file_id
        file_path.write_bytes(content)
        return file_id

    def load_file(self, id: str | None) -> bytes | None:
        """Load file from storage"""
        if id is None:
            return None
        path = self._base_path / id
        if not path.exists():
            return None
        return path.read_bytes()

    def delete_file(self, id: str | None) -> bool:
        """Delete file from storage"""
        if not id:
            return False
        file_path = self._base_path / id
        if not file_path.exists():
            return False
        file_path.unlink()
        return True

    def get_file_url(
        self, id: str | None, extension: str | None = None, filename: str | None = None
    ) -> str | None:
        if not id or not (self._base_path / id).exists():
            return None
        """Get file URL for a given file ID"""
        query_params = []
        if extension:
            query_params.append(f"extension={extension}")
        if filename:
            query_params.append(f"filename={filename}")
        query_string = "&".join(query_params)
        return f"/api/files/{id}?{query_string}"
