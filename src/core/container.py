from dependency_injector import containers, providers
from .secrets import secrets

from ..entities.config import MainConfig
from ..services.reddit_video_service import RedditVideoService
from ..services.video_service import VideoService
from ..services.captions_service import CaptionsService
from ..services.cover_service import CoverService
from ..services.speech_service import SpeechService
from ..proxies import factories as proxies_factories


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the application"""

    # Configuration
    config = providers.Configuration()

    main_config = providers.Singleton(
        MainConfig.from_yaml, file_path="config.yaml"
    )

    # Proxies configs
    transcription_proxy = providers.Singleton(
        proxies_factories.TranscriptionProxyFactory.create,
        config=main_config.provided.proxies.transcription_config,
        openai_api_key=secrets.openai_api_key,
    )
    image_generation_proxy = providers.Singleton(
        proxies_factories.ImageGeneratorFactory.create,
        config=main_config.provided.proxies.image_generation_config,
        leonardo_api_key=secrets.leonardo_api_key,
    )
    speech_proxy = providers.Singleton(
        proxies_factories.SpeechProxyFactory.create,
        config=main_config.provided.proxies.speech_config,
        elevenlabs_api_key=secrets.elevenlabs_api_key,
    )
    reddit_proxy = providers.Singleton(
        proxies_factories.RedditProxyFactory.create,
        config=main_config.provided.proxies.reddit_config,
    )
    llm_proxy = providers.Singleton(
        proxies_factories.LLMProxyFactory.create,
        config=main_config.provided.proxies.llm_config,
    )
    youtube_proxy = providers.Singleton(
        proxies_factories.YouTubeProxyFactory.create,
        config=main_config.provided.proxies.youtube_config,
    )
    cover_proxy = providers.Singleton(
        proxies_factories.CoverProxyFactory.create,
        config=main_config.provided.proxies.cover_config,
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
        captions_config=main_config.provided.services.captions_config,
    )

    cover_service = providers.Singleton(
        CoverService,
        cover_proxy=cover_proxy,
    )

    video_service = providers.Singleton(
        VideoService,
        youtube_proxy=youtube_proxy,
        video_config=main_config.provided.services.video_config,
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
