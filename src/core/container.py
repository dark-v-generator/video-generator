import os

from dependency_injector import containers, providers
from .secrets import secrets

from ..entities.config import MainConfig
from ..services.reddit_video_service import RedditVideoService
from ..services.video_service import VideoService
from ..services.captions_service import CaptionsService
from ..services.cover_service import CoverService
from ..services.speech_service import SpeechService
from ..services.story_finder_service import StoryFinderService
from ..proxies import factories as proxies_factories

_CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.yaml")


class ApplicationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the application"""

    # Configuration
    config = providers.Configuration()

    main_config = providers.Singleton(MainConfig.from_yaml, file_path=_CONFIG_PATH)

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
        runpod_api_key=secrets.runpod_api_key,
        legnext_api_key=secrets.legnext_api_key,
    )
    portrait_generation_proxy = providers.Singleton(
        proxies_factories.ImageGeneratorFactory.create_optional,
        config=main_config.provided.proxies.portrait_generation_config,
        leonardo_api_key=secrets.leonardo_api_key,
        runpod_api_key=secrets.runpod_api_key,
        legnext_api_key=secrets.legnext_api_key,
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
        openai_api_key=secrets.openai_api_key,
        ollama_base_url=secrets.ollama_base_url,
        google_api_key=secrets.google_api_key,
    )
    evaluation_llm_proxy = providers.Singleton(
        proxies_factories.LLMProxyFactory.create_optional,
        config=main_config.provided.proxies.evaluation_llm_config,
        openai_api_key=secrets.openai_api_key,
        ollama_base_url=secrets.ollama_base_url,
        google_api_key=secrets.google_api_key,
    )
    youtube_proxy = providers.Singleton(
        proxies_factories.YouTubeProxyFactory.create,
        config=main_config.provided.proxies.youtube_config,
    )
    cover_proxy = providers.Singleton(
        proxies_factories.CoverProxyFactory.create,
        config=main_config.provided.proxies.cover_config,
    )
    tiktok_proxy = providers.Singleton(
        proxies_factories.TikTokProxyFactory.create,
        config=main_config.provided.proxies.tiktok_config,
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
        image_generation_proxy=image_generation_proxy,
        portrait_generation_proxy=portrait_generation_proxy,
        speech_service=speech_service,
        captions_service=captions_service,
        cover_service=cover_service,
        video_service=video_service,
    )

    story_finder_service = providers.Singleton(
        StoryFinderService,
        reddit_proxy=reddit_proxy,
        evaluation_llm_proxy=evaluation_llm_proxy,
        llm_proxy=llm_proxy,
        evaluation_config=main_config.provided.evaluation,
    )


# Create and configure container instance
container = ApplicationContainer()
