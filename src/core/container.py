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

from ..services.captions_service import CaptionsService
from ..services.cover_service import CoverService
from ..services.video_service import VideoService

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
    speech_proxy = providers.Singleton(
        proxies_factories.SpeechProxyFactory.create,
        config=main_config.provided.speech_config,
    )
    reddit_proxy = providers.Singleton(
        proxies_factories.RedditProxyFactory.create,
        config=main_config.provided.reddit_config,
    )
    llm_proxy = providers.Singleton(
        proxies_factories.LLMProxyFactory.create,
        config=main_config.provided.llm_config,
    )
    youtube_proxy = providers.Singleton(
        proxies_factories.YouTubeProxyFactory.create,
        config=main_config.provided.youtube_config,
    )
    cover_proxy = providers.Singleton(
        proxies_factories.CoverProxyFactory.create,
        config=main_config.provided.cover_config,
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



    captions_service = providers.Singleton(
        CaptionsService,
        file_storage=file_storage,
        llm_proxy=llm_proxy,
        transcription_proxy=transcription_proxy,
    )

    cover_service = providers.Singleton(
        CoverService,
        config_repository=config_repository,
        cover_proxy=cover_proxy,
    )

    video_service = providers.Singleton(
        VideoService,
        file_storage=file_storage,
        youtube_proxy=youtube_proxy,
    )

    history_service = providers.Singleton(
        HistoryService,
        history_repository=history_repository,
        config_repository=config_repository,
        speech_proxy=speech_proxy,
        captions_service=captions_service,
        cover_service=cover_service,
        video_service=video_service,
        file_storage=file_storage,
        reddit_proxy=reddit_proxy,
    )


# Create and configure container instance
container = ApplicationContainer()
