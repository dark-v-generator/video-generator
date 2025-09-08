from fastapi import Depends
from ..core.container import container


def get_file_storage():
    """Get file storage"""
    return container.file_storage()


def get_config_service():
    """Get config service"""
    return container.config_service()


def get_history_service():
    """Get history service"""
    return container.history_service()


def get_speech_service():
    """Get speech service"""
    return container.speech_service()


def get_captions_service():
    """Get captions service"""
    return container.captions_service()


def get_cover_service():
    """Get cover service"""
    return container.cover_service()


def get_video_service():
    """Get video service"""
    return container.video_service()


def get_language_service():
    """Get language service"""
    return container.language_service()


def get_llm_service():
    """Get LLM service"""
    return container.llm_service()


# Dependency shortcuts using FastAPI Depends
FileStorageDep = Depends(get_file_storage)
HistoryServiceDep = Depends(get_history_service)
SpeechServiceDep = Depends(get_speech_service)
CaptionsServiceDep = Depends(get_captions_service)
CoverServiceDep = Depends(get_cover_service)
VideoServiceDep = Depends(get_video_service)
LanguageServiceDep = Depends(get_language_service)
LLMServiceDep = Depends(get_llm_service)
ConfigServiceDep = Depends(get_config_service)
