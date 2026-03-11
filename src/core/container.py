import os
from dependency_injector import containers, providers

from ..entities.config import MainConfig
from ..services.reddit_video_service import RedditVideoService
from ..services.video_service import VideoService
from ..services.captions_service import CaptionsService
from ..services.cover_service import CoverService
from ..services.speech_service import SpeechService
from ..adapters.proxies import factories as proxies_factories


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the application"""

    # Configuration
    config = providers.Configuration()

    main_config = providers.Singleton(
        MainConfig.from_yaml, file_path=os.getenv("CONFIG_PATH", "config.yaml")
    )

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

    # Services
    speech_service = providers.Singleton(
        SpeechService,
        speech_proxy=speech_proxy,
    )

    captions_service = providers.Singleton(
        CaptionsService,
        llm_proxy=llm_proxy,
        transcription_proxy=transcription_proxy,
        captions_config=main_config.provided.captions_config,
    )

    cover_service = providers.Singleton(
        CoverService,
        cover_proxy=cover_proxy,
    )

    video_service = providers.Singleton(
        VideoService,
        youtube_proxy=youtube_proxy,
    )

    reddit_video_service = providers.Singleton(
        RedditVideoService,
        reddit_proxy=reddit_proxy,
        llm_proxy=llm_proxy,
        speech_service=speech_service,
        captions_service=captions_service,
        video_service=video_service,
    )


# Create and configure container instance
container = ApplicationContainer()
