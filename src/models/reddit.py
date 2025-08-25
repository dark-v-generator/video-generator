from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RedditHistoryResponse(BaseModel):
    """Response model for Reddit history"""
    id: str
    title: str
    content: str
    gender: str
    language: str
    author: str
    community: str
    community_image_url: str
    last_updated_at: Optional[datetime] = None
    has_speech: bool = False
    has_captions: bool = False
    has_cover: bool = False
    has_video: bool = False


class RedditHistoryCreate(BaseModel):
    """Request model for creating Reddit history"""
    url: str = Field(..., description="Reddit post URL")
    enhance_history: bool = Field(True, description="Whether to enhance the history using AI")
    language: str = Field("portuguese", description="Language for processing")


class VideoGenerationRequest(BaseModel):
    """Request model for video generation"""
    history_id: str = Field(..., description="ID of the Reddit history")
    title: Optional[str] = Field(None, description="Override title")
    content: Optional[str] = Field(None, description="Override content")
    gender: Optional[str] = Field(None, description="Override gender")
    speech: bool = Field(True, description="Generate speech")
    captions: bool = Field(True, description="Generate captions")
    enhance_captions: bool = Field(False, description="Use AI to enhance captions")
    cover: bool = Field(True, description="Generate cover image")
    low_quality: bool = Field(False, description="Generate low quality video")
    rate: float = Field(1.0, description="Speech rate")


class TaskStatusResponse(BaseModel):
    """Response model for task status"""
    history_id: str
    status: str  # started, running, completed, failed
    message: str
    progress: Optional[float] = None
