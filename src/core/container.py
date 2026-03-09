import os
from dependency_injector import containers, providers

from ..entities.config import MainConfig

from ..adapters.repositories.local_file_storage import LocalFileStorage
from ..core.config import settings
from ..adapters.repositories.config_repository import FileConfigRepository
from ..adapters.repositories.history_repository import FileHistoryRepository
from ..adapters.repositories.local_file_repository import LocalFileRepository
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
from ..adapters.proxies.reddit_proxy import BS4RedditProxy
from ..adapters.proxies import factories as proxies_factories


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the application"""

    # Configuration
    config = providers.Configuration()

    main_config = providers.Singleton(
        MainConfig.from_yaml, file_path=os.getenv("CONFIG_PATH", "config.yaml")
    )

    # Repositories (Singletons)
    file_repository = providers.Singleton(LocalFileRepository)
    file_storage = providers.Singleton(LocalFileStorage)

    # Proxies configs
    transcription_proxy = providers.Singleton(
        proxies_factories.TranscriptionProxyFactory.create,
        config=main_config.provided.transcription_config,
    )
    image_generation_proxy = providers.Singleton(
        proxies_factories.ImageGeneratorFactory.create,
        config=main_config.provided.image_generation_config,
    )

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

    # Proxies
    reddit_proxy = providers.Singleton(BS4RedditProxy)

    # Speech services - provide both providers
    coqui_speech_service = providers.Singleton(CoquiSpeechService)
    fish_speech_service = providers.Singleton(FishSpeechService)

    # Default speech service (can be overridden by configuration)
    speech_service = providers.Singleton(SpeechServiceFactory.create_speech_service)

    # LLM service with factory pattern
    llm_service = providers.Singleton(LLMServiceFactory.create_llm_service)

    captions_service = providers.Singleton(
        CaptionsService,
        file_storage=file_storage,
        llm_service=llm_service,
        transcription_proxy=transcription_proxy,
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

    history_service = providers.Singleton(
        HistoryService,
        history_repository=history_repository,
        config_repository=config_repository,
        speech_service=speech_service,
        captions_service=captions_service,
        cover_service=cover_service,
        video_service=video_service,
        llm_service=llm_service,
        file_storage=file_storage,
        reddit_proxy=reddit_proxy,
    )


# Create and configure container instance
container = ApplicationContainer()
