import mimetypes
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import tempfile

from ...repositories.interfaces import IFileStorage
from ..dependencies import FileStorageDep


router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}")
async def serve_file(
    file_id: str,
    extension: Optional[str] = "",
    filename: Optional[str] = None,
    file_repository: IFileStorage = FileStorageDep,
):
    """Serve uploaded files"""

    content = file_repository.load_file(file_id)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    filename = filename or file_id

    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmpfile:
        tmpfile.write(content)
        tmpfile.seek(0)
        temp_file_path = tmpfile.name
        media_type, _ = mimetypes.guess_type(str(temp_file_path))

        return FileResponse(
            path=str(temp_file_path),
            media_type=media_type or "application/octet-stream",
            filename=filename,
        )
