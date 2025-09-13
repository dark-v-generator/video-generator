import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from ...entities.config import SpeechConfig, VideoConfig, CoverConfig, LLMConfig
from ...entities.config import CaptionsConfig
from ...services.interfaces import IConfigService

from ...adapters.repositories.interfaces import IFileStorage
from ..dependencies import ConfigServiceDep, FileStorageDep
from ...core.container import container


router = APIRouter(prefix="/config", tags=["configuration"])


class ConfigResponse(BaseModel):
    video_config: dict
    cover_config: dict
    captions_config: dict
    speech_config: dict
    llm_config: dict
    seed: str | None


class UpdateConfigRequest(BaseModel):
    video_config: Optional[dict] = None
    cover_config: Optional[dict] = None
    captions_config: Optional[dict] = None
    llm_config: Optional[dict] = None
    speech_config: Optional[dict] = None
    seed: Optional[str] = None


@router.get("/", response_model=ConfigResponse)
async def get_config(
    config_service: IConfigService = ConfigServiceDep,
    file_storage: IFileStorage = FileStorageDep,
):
    """Get current configuration"""
    config = config_service.get_config()

    return ConfigResponse(
        video_config={
            "end_silece_seconds": config.video_config.end_silece_seconds,
            "padding": config.video_config.padding,
            "cover_duration": config.video_config.cover_duration,
            "width": config.video_config.width,
            "height": config.video_config.height,
            "youtube_channel_id": config.video_config.youtube_channel_id,
            "watermark_file_url": file_storage.get_file_url(
                config.video_config.watermark_file_id,
                extension=".png",
                filename="watermark.png",
            ),
            "ffmpeg_params": config.video_config.ffmpeg_params,
        },
        cover_config={
            "title_font_size": config.cover_config.title_font_size,
        },
        captions_config={
            "upper": config.captions_config.upper,
            "font_file_url": file_storage.get_file_url(
                config.captions_config.font_file_id,
                extension=".ttf",
                filename="font.ttf",
            ),
            "font_size": config.captions_config.font_size,
            "color": config.captions_config.color,
            "stroke_color": config.captions_config.stroke_color,
            "stroke_width": config.captions_config.stroke_width,
            "upper_text": config.captions_config.upper_text,
            "marging": config.captions_config.marging,
            "fade_duration": config.captions_config.fade_duration,
        },
        speech_config={
            "provider": config.speech_config.provider,
        },
        llm_config={
            "provider": config.llm_config.provider,
            "model": config.llm_config.model,
            "temperature": config.llm_config.temperature,
            "max_tokens": config.llm_config.max_tokens,
        },
        seed=config.seed,
    )


@router.put("/")
async def update_config(
    config_service: IConfigService = ConfigServiceDep,
    watermark_file: Optional[UploadFile] = File(None),
    font_file: Optional[UploadFile] = File(None),
    video_config: Optional[str] = Form(None),
    cover_config: Optional[str] = Form(None),
    captions_config: Optional[str] = Form(None),
    speech_config: Optional[str] = Form(None),
    llm_config: Optional[str] = Form(None),
    seed: Optional[str] = Form(None),
):
    """Update configuration with optional file uploads"""
    current_config = config_service.get_config()

    # Update other configuration fields
    if video_config:
        video_config = VideoConfig.model_validate(json.loads(video_config))
        current_config.video_config = video_config

    if cover_config:
        cover_config = CoverConfig.model_validate(json.loads(cover_config))
        current_config.cover_config = cover_config

    if captions_config:
        captions_config = CaptionsConfig.model_validate(json.loads(captions_config))
        current_config.captions_config = captions_config

    if speech_config:
        speech_config = SpeechConfig.model_validate(json.loads(speech_config))
        current_config.speech_config = speech_config

    if llm_config:
        llm_config = LLMConfig.model_validate(json.loads(llm_config))
        current_config.llm_config = llm_config

    if seed:
        current_config.seed = seed

    # Handle file uploads
    if watermark_file:
        # Validate file type for watermark
        if not watermark_file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="Watermark file must be an image"
            )

        # Save file and get path
        file_content = await watermark_file.read()
        file_id = config_service.save_watermark(file_content)
        current_config.video_config.watermark_file_id = file_id

    if font_file:
        # Validate file type for font
        if not (
            font_file.filename.endswith(".ttf") or font_file.filename.endswith(".otf")
        ):
            raise HTTPException(
                status_code=400, detail="Font file must be .ttf or .otf"
            )

        # Save file and get path
        file_content = await font_file.read()
        font_path = config_service.save_font(file_content)
        current_config.captions_config.font_file_id = font_path

    # Save updated config
    config_service.save_config(current_config)

    # Reset providers so next resolution reflects new configuration
    # If speech provider changed, recreate speech and dependent history service
    if speech_config:
        container.speech_service.reset()
        container.history_service.reset()

    # If LLM provider changed, recreate llm and dependent history service
    if llm_config:
        container.llm_service.reset()
        container.history_service.reset()
    return {"message": "Configuration updated successfully"}
