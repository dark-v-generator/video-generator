import os

from dependency_injector import containers, providers
from .secrets import secrets

from ..capabilities.discovery import RedditStoryDiscovery
from ..capabilities.footage import LocalFolderFootageSource, YouTubeFootageSource
from ..capabilities.rendering import NarrationOverFootageRenderer, select_renderer
from ..capabilities.rendering.captions import CaptionsService
from ..capabilities.rendering.censor import TextCensor
from ..capabilities.rendering.compose import VideoComposer
from ..capabilities.rendering.cover import CoverService
from ..capabilities.rendering.speech import SpeechService
from ..capabilities.writing import ModelStoryWriter
from ..entities.config import MainConfig
from ..prompts import loader as prompts
from ..proxies import factories as proxies_factories

_CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.yaml")


def _create_llm_proxy(**kwargs):
    # A broken prompt template must stop the process here, not halfway
    # through a run when the first story is written.
    prompts.validate_all()
    return proxies_factories.LLMProxyFactory.create(**kwargs)


def _first_configured(*proxies):
    return next(proxy for proxy in proxies if proxy is not None)


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
    speech_proxy = providers.Singleton(
        proxies_factories.SpeechProxyFactory.create,
        config=main_config.provided.proxies.speech_config,
        elevenlabs_api_key=secrets.elevenlabs_api_key,
    )
    reddit_proxy = providers.Singleton(
        proxies_factories.RedditProxyFactory.create,
        config=main_config.provided.proxies.reddit_config,
        reddit_client_id=secrets.reddit_client_id,
        reddit_client_secret=secrets.reddit_client_secret,
        reddit_user_agent=secrets.reddit_user_agent,
    )
    llm_proxy = providers.Singleton(
        _create_llm_proxy,
        config=main_config.provided.proxies.llm_config,
        openai_api_key=secrets.openai_api_key,
        ollama_base_url=secrets.ollama_base_url,
        google_api_key=secrets.google_api_key,
        openrouter_api_key=secrets.openrouter_api_key,
    )
    history_adaptation_llm_proxy = providers.Singleton(
        proxies_factories.LLMProxyFactory.create_optional,
        config=main_config.provided.proxies.history_adaptation_llm_config,
        openai_api_key=secrets.openai_api_key,
        ollama_base_url=secrets.ollama_base_url,
        google_api_key=secrets.google_api_key,
        openrouter_api_key=secrets.openrouter_api_key,
    )
    youtube_proxy = providers.Singleton(
        proxies_factories.YouTubeProxyFactory.create,
        config=main_config.provided.proxies.youtube_config,
        youtube_po_token=secrets.youtube_po_token,
        youtube_visitor_data=secrets.youtube_visitor_data,
    )
    cover_proxy = providers.Singleton(
        proxies_factories.CoverProxyFactory.create,
        config=main_config.provided.proxies.cover_config,
    )
    # Capabilities
    story_discovery = providers.Singleton(
        RedditStoryDiscovery,
        reddit=reddit_proxy,
        llm=llm_proxy,
        evaluation=main_config.provided.evaluation,
    )
    # Only the selected source is built: a local run never constructs the
    # YouTube proxy. VideoConfig already refuses "local" without a directory.
    footage_source = providers.Selector(
        main_config.provided.services.video_config.footage_source,
        youtube=providers.Singleton(
            YouTubeFootageSource,
            youtube=youtube_proxy,
            video_config=main_config.provided.services.video_config,
        ),
        local=providers.Singleton(
            LocalFolderFootageSource,
            directory=main_config.provided.services.video_config.local_footage_dir,
            video_config=main_config.provided.services.video_config,
        ),
    )
    story_writer = providers.Singleton(
        ModelStoryWriter,
        llm=providers.Callable(
            _first_configured, history_adaptation_llm_proxy, llm_proxy
        ),
    )

    # Rendering
    text_censor = providers.Singleton(
        TextCensor,
        extra_mappings=main_config.provided.services.censorship_config.extra_word_replacements,
    )

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

    video_composer = providers.Singleton(
        VideoComposer,
        video_config=main_config.provided.services.video_config,
    )

    renderers = providers.Dict(
        {
            NarrationOverFootageRenderer.name: providers.Singleton(
                NarrationOverFootageRenderer,
                speech=speech_service,
                captions=captions_service,
                cover=cover_service,
                footage=footage_source,
                composer=video_composer,
                censor=text_censor,
                video_config=main_config.provided.services.video_config,
            ),
        }
    )
    renderer = providers.Singleton(
        select_renderer,
        name=main_config.provided.services.video_config.rendering_strategy,
        renderers=renderers,
    )


# Create and configure container instance
container = ApplicationContainer()
