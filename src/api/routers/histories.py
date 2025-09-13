import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncIterable
from pydantic import BaseModel

from ...services.interfaces import IHistoryService, ISpeechService
from ...services.llm.interfaces import ILLMService
from ...entities.language import Language
from ...entities.progress import ProgressEvent
from ..dependencies import (
    HistoryServiceDep,
    LLMServiceDep,
    FileStorageDep,
    SpeechServiceDep,
)
from ...adapters.repositories.interfaces import IFileStorage
from ...core.logging_config import get_logger
from ...entities.speech_voice import SpeechVoice

router = APIRouter(prefix="/histories", tags=["histories"])

logger = get_logger(__name__)


class ScrapRedditRequest(BaseModel):
    url: str
    gender: str = "male"
    language: str = "portuguese"


class GenerateVideoRequest(BaseModel):
    history_id: str
    title: Optional[str] = None
    content: Optional[str] = None
    gender: Optional[str] = None
    speech: bool = True
    captions: bool = True
    enhance_captions: bool = False
    cover: bool = True
    low_quality: bool = False
    rate: float = 1.0
    voice_id: str = None


class UpdateHistoryRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    gender: Optional[str] = None
    language: Optional[str] = None
    cover_image_url: Optional[str] = None
    cover_author: Optional[str] = None
    cover_community: Optional[str] = None
    cover_title: Optional[str] = None


@router.get("/", response_model=List[dict])
async def list_histories(
    history_service: IHistoryService = HistoryServiceDep,
):
    """List all Reddit histories"""
    histories = history_service.list_histories()

    # Convert to dict for JSON serialization
    return [
        {
            "id": h.id,
            "title": h.history.title,
            "language": h.language,
            "last_updated_at": (
                h.last_updated_at.isoformat() if h.last_updated_at else None
            ),
            "has_speech": bool(h.speech_file_id),
            "has_captions": bool(h.captions_file_id),
            "has_cover": bool(h.cover_file_id),
            "has_video": bool(h.final_video_file_id),
        }
        for h in histories
    ]


@router.get("/list-voices")
async def list_voices(
    speech_service: ISpeechService = SpeechServiceDep,
) -> List[SpeechVoice]:
    """List all available voices"""
    return speech_service.list_voices()


@router.get("/{history_id}")
async def get_history(
    history_id: str,
    history_service: IHistoryService = HistoryServiceDep,
    file_storage: IFileStorage = FileStorageDep,
):
    """Get a specific Reddit history"""
    history = history_service.get_reddit_history(history_id)

    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    return {
        "id": history.id,
        "title": history.history.title,
        "content": history.history.content,
        "gender": history.history.gender,
        "language": history.language,
        "cover": {
            "image_url": history.cover.image_url,
            "author": history.cover.author,
            "community": history.cover.community,
            "title": history.cover.title,
        },
        "paths": {
            "speech": file_storage.get_file_url(
                history.speech_file_id, extension=".mp3", filename="speech.mp3"
            ),
            "cover": file_storage.get_file_url(
                history.cover_file_id, extension=".jpg", filename="cover.jpg"
            ),
            "final_video": file_storage.get_file_url(
                history.final_video_file_id,
                extension=".mp4",
                filename="final_video.mp4",
            ),
        },
        "last_updated_at": (
            history.last_updated_at.isoformat() if history.last_updated_at else None
        ),
    }


@router.patch("/{history_id}")
async def update_history(
    history_id: str,
    request: UpdateHistoryRequest,
    history_service: IHistoryService = HistoryServiceDep,
):
    """Update specific fields of a Reddit history"""
    reddit_history = history_service.get_reddit_history(history_id)

    if not reddit_history:
        raise HTTPException(status_code=404, detail="History not found")

    # Track what fields were updated for the response
    updated_fields = []

    # Update history fields if provided
    if request.title is not None:
        reddit_history.history.title = request.title
        updated_fields.append("title")

    if request.content is not None:
        reddit_history.history.content = request.content
        updated_fields.append("content")

    if request.gender is not None:
        reddit_history.history.gender = request.gender
        updated_fields.append("gender")

    if request.language is not None:
        # Convert language string to Language enum and validate
        try:
            language = Language(request.language.upper())
            reddit_history.language = language.value
            updated_fields.append("language")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language: {request.language}. Valid options: {[lang.value.lower() for lang in Language]}",
            )

    # Update cover fields if provided
    if request.cover_image_url is not None:
        reddit_history.cover.image_url = request.cover_image_url
        updated_fields.append("cover_image_url")

    if request.cover_author is not None:
        reddit_history.cover.author = request.cover_author
        updated_fields.append("cover_author")

    if request.cover_community is not None:
        reddit_history.cover.community = request.cover_community
        updated_fields.append("cover_community")

    if request.cover_title is not None:
        reddit_history.cover.title = request.cover_title
        updated_fields.append("cover_title")

    # Only save if at least one field was updated
    if updated_fields:
        history_service.save_reddit_history(reddit_history)

        return {
            "message": "History updated successfully",
            "history_id": history_id,
            "updated_fields": updated_fields,
            "history": {
                "id": reddit_history.id,
                "title": reddit_history.history.title,
                "content": reddit_history.history.content,
                "gender": reddit_history.history.gender,
                "language": reddit_history.language,
                "cover": {
                    "image_url": reddit_history.cover.image_url,
                    "author": reddit_history.cover.author,
                    "community": reddit_history.cover.community,
                    "title": reddit_history.cover.title,
                },
                "last_updated_at": (
                    reddit_history.last_updated_at.isoformat()
                    if reddit_history.last_updated_at
                    else None
                ),
            },
        }
    else:
        return {
            "message": "No fields to update",
            "history_id": history_id,
            "updated_fields": [],
        }


@router.post("/scrap")
async def scrap_reddit_post(
    request: ScrapRedditRequest,
    history_service: IHistoryService = HistoryServiceDep,
):
    """Only scrapes Reddit content, no enhancement"""
    # Convert language string to Language enum
    try:
        language = Language(request.language.upper())
    except ValueError:
        language = Language.PORTUGUESE

    reddit_history = await history_service.srcap_reddit_post(request.url, language)

    return {
        "id": reddit_history.id,
        "message": "Reddit post scraped successfully",
        "title": reddit_history.history.title,
    }


@router.post("/generate-video")
async def generate_video(
    request: GenerateVideoRequest,
    history_service: IHistoryService = HistoryServiceDep,
):
    """Generate video for a Reddit history and stream progress events"""
    reddit_history = history_service.get_reddit_history(request.history_id)

    if not reddit_history:
        raise HTTPException(status_code=404, detail="History not found")

    # Update history fields if provided
    if request.title:
        reddit_history.history.title = request.title
    if request.content:
        reddit_history.history.content = request.content
    if request.gender:
        reddit_history.history.gender = request.gender

    # Save updated history
    history_service.save_reddit_history(reddit_history)

    async def generate_video_stream():
        """Stream video generation progress events"""
        # Generate speech if requested
        if request.speech:
            async for event in history_service.generate_speech(
                reddit_history,
                request.rate,
                request.voice_id,
            ):
                if isinstance(event, ProgressEvent):
                    yield f"data: {json.dumps(event.model_dump())}\n\n"

        # Generate captions if requested
        if request.captions:
            event = ProgressEvent.create(
                "generating",
                "Generating captions",
                details={"component": "captions"},
            )
            yield f"data: {json.dumps(event.model_dump())}\n\n"
            await history_service.generate_captions(
                reddit_history.id, request.rate, request.enhance_captions
            )

        # Generate cover if requested
        if request.cover:
            async for event in history_service.generate_cover(reddit_history):
                if isinstance(event, ProgressEvent):
                    yield f"data: {json.dumps(event.model_dump())}\n\n"

        # Generate final video
        async for event in history_service.generate_reddit_video(
            reddit_history, low_quality=request.low_quality
        ):
            if isinstance(event, ProgressEvent):
                yield f"data: {json.dumps(event.model_dump())}\n\n"

    return StreamingResponse(
        generate_video_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post("/enhance-text/{history_id}")
async def enhance_history_text(
    history_id: str,
    history_service: IHistoryService = HistoryServiceDep,
    llm_service: ILLMService = LLMServiceDep,
):
    """Enhance history text using LLM with streaming progress"""
    reddit_history = history_service.get_reddit_history(history_id)

    if not reddit_history:
        raise HTTPException(status_code=404, detail="History not found")

    # Stream enhanced text from LLM service and create History
    async def event_stream() -> AsyncIterable[str]:
        enhanced_content = ""
        # Send initial progress event
        initial_event = ProgressEvent.create(
            "initializing",
            "Starting text enhancement",
            progress=0,
            details={"history_id": history_id, "provider": "llm"},
        )
        yield f"data: {initial_event.model_dump_json()}\n\n"

        # Stream tokens from LLM and accumulate content
        token_count = 0
        async for token in llm_service.enhance_history(
            reddit_history.history.title,
            reddit_history.history.content,
            reddit_history.get_language(),
        ):
            enhanced_content += token
            token_count += 1

            # Send progress every 10 tokens to avoid too many events
            progress_event = ProgressEvent.create(
                "generating",
                f"Generating enhanced content... ({token_count} tokens)",
                details={"token": token, "current_length": len(enhanced_content)},
            )
            yield f"data: {progress_event.model_dump_json()}\n\n"

        # Create enhanced history from the accumulated content
        # Keep original title and gender, use enhanced content
        from src.entities.history import History

        enhanced_history = History(
            title=reddit_history.history.title,
            content=enhanced_content.strip(),
            gender=reddit_history.history.gender,
        )

        # Save the enhanced history
        reddit_history.history = enhanced_history
        history_service.save_reddit_history(reddit_history)

        # Send final completion event
        completion_event = ProgressEvent.create(
            "completed",
            "Text enhancement saved successfully",
            progress=100,
            details={
                "history_id": history_id,
                "saved": True,
                "enhanced_content_length": len(enhanced_content),
                "total_tokens": token_count,
            },
        )
        yield f"data: {completion_event.model_dump_json()}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{history_id}")
async def delete_history(
    history_id: str,
    history_service: IHistoryService = HistoryServiceDep,
):
    """Delete a Reddit history"""
    success = history_service.delete_reddit_history(history_id)

    if not success:
        raise HTTPException(status_code=404, detail="History not found")

    return {"message": "History deleted successfully"}
