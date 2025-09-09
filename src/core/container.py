from dependency_injector import containers, providers

from ..repositories.local_file_storage import LocalFileStorage
from .config import settings

from ..repositories.config_repository import FileConfigRepository
from ..repositories.history_repository import FileHistoryRepository
from ..repositories.local_file_repository import LocalFileRepository
from ..services.config_service import ConfigService

# Import concrete service implementations (we'll update these)
from ..services.history_service import HistoryService
from ..services.speech_service import (
    CoquiSpeechService,
    SpeechServiceFactory,
    FishSpeechService,
)
from ..services.captions_service import CaptionsService
from ..services.cover_service import CoverService
from ..services.video_service import VideoService
from ..services.llm import LLMServiceFactory
from ..proxies.reddit_oauth_proxy import RedditOAuthProxy


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the application"""

    # Configuration
    config = providers.Configuration()

    # Repositories (Singletons)
    file_repository = providers.Singleton(LocalFileRepository)
    file_storage = providers.Singleton(LocalFileStorage)

    config_repository = providers.Singleton(
        FileConfigRepository, file_repository=file_repository
    )

    config_service = providers.Singleton(
        ConfigService,
        config_repository=config_repository,
        file_storage=file_storage,
    )

    history_repository = providers.Singleton(
        FileHistoryRepository,
        file_repository=file_repository,
        file_storage=file_storage,
    )

    # Speech services - provide both providers
    coqui_speech_service = providers.Singleton(CoquiSpeechService)
    fish_speech_service = providers.Singleton(FishSpeechService)

    # Default speech service (can be overridden by configuration)
    speech_service = providers.Singleton(
        SpeechServiceFactory.create_speech_service,
        config_repository=config_repository,
    )

    # LLM service with factory pattern
    llm_service = providers.Singleton(
        LLMServiceFactory.create_llm_service, config_repository=config_repository
    )

    captions_service = providers.Singleton(
        CaptionsService,
        file_storage=file_storage,
        llm_service=llm_service,
    )

    cover_service = providers.Singleton(
        CoverService,
        config_repository=config_repository,
    )

    video_service = providers.Singleton(
        VideoService,
        config_repository=config_repository,
        file_storage=file_storage,
    )

    # Reddit proxy
    reddit_proxy = providers.Singleton(RedditOAuthProxy)

    history_service = providers.Singleton(
        HistoryService,
        history_repository=history_repository,
        config_repository=config_repository,
        reddit_proxy=reddit_proxy,
        speech_service=speech_service,
        captions_service=captions_service,
        cover_service=cover_service,
        video_service=video_service,
        llm_service=llm_service,
        file_storage=file_storage,
    )


# Create and configure container instance
container = ApplicationContainer()
container.config.from_dict(
    {
        "default_config_path": settings.default_config_path,
        "assets_path": settings.assets_path,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "environment": settings.environment,
        "debug": settings.debug,
        "ollama_base_url": settings.ollama_base_url,
        "ffmpeg_path": settings.ffmpeg_path,
        "file_storage_base_path": settings.file_storage_base_path,
        "openai_api_key": settings.openai_api_key,
        "youtube_api_key": settings.youtube_api_key,
        "google_cloud_credentials_path": settings.google_cloud_credentials_path,
    }
)
