from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from enum import Enum
from datetime import timezone

class ProgressEvent(BaseModel):
    """Progress event for speech generation"""
    stage: str = Field(..., description="Current stage of the process")
    progress: float | None = Field(None, ge=0.0, le=100.0, description="Progress percentage (0-100)")
    message: str = Field("", description="Human-readable progress message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the progress")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of the event")
    
    @classmethod
    def create(
        cls, 
        stage: str,
        message: str, 
        progress: float | None = None, 
        details: Optional[Dict[str, Any]] = None
    ) -> "ProgressEvent":
        """Create a progress event with current timestamp"""
        from datetime import datetime
        return cls(
            stage=stage,
            progress=progress,
            message=message,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat()
        )


# Removed SpeechGenerationResult - now returning bytes directly

