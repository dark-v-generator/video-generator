from src.entities.configs.proxies.image_generation import (
    ImageGenerationConfigType,
    LeonardoImageGenerationConfig,
    LocalImageGenerationConfig,
)
from src.proxies.interfaces import IImageGeneratorProxy, ITranscriptionProxy
from src.proxies.leonardo_proxy import LeonardoImageProxy
from src.proxies.local_sdxl_proxy import LocalSDXLImageProxy

from src.entities.configs.proxies.transcription import (
    TranscriptionConfigType,
    LocalTranscriptionConfig,
    OpenAITranscriptionConfig,
)
from src.proxies.local_whisper_proxy import LocalWhisperProxy
from src.proxies.openai_whisper_proxy import OpenAIWhisperProxy
from src.entities.configs.proxies.speech import (
    SpeechConfigType,
    EdgeTTSSpeechConfig,
    ElevenLabsSpeechConfig,
)
from src.proxies.edge_tts_proxy import EdgeTTSSpeechProxy
from src.proxies.elevenlabs_proxy import ElevenLabsSpeechProxy
from src.proxies.interfaces import (
    IImageGeneratorProxy,
    ITranscriptionProxy,
    ISpeechProxy,
    IRedditProxy,
)
from src.entities.configs.proxies.reddit import RedditConfigType, BS4RedditConfig
from src.proxies.reddit_proxy import BS4RedditProxy
from src.entities.configs.proxies.llm import (
    LLMConfigType,
    PromptLLMConfig,
    DSPyLLMConfig,
)
from src.proxies.llm_prompt_proxy import PromptLLMProxy
from src.proxies.llm_dspy_proxy import DSPyLLMProxy
from src.proxies.interfaces import ILLMProxy, IYouTubeProxy
from src.entities.configs.proxies.youtube import YouTubeConfigType, PyTubeYouTubeConfig
from src.proxies.pytube_proxy import PyTubeProxy

from src.proxies.interfaces import ICoverProxy
from src.proxies.playwright_cover_proxy import PlaywrightCoverProxy
from src.entities.configs.proxies.cover import CoverConfigType, PlaywrightCoverConfig


class ImageGeneratorFactory:
    @staticmethod
    def create(
        config: ImageGenerationConfigType, leonardo_api_key: str = None
    ) -> IImageGeneratorProxy:
        if isinstance(config, LeonardoImageGenerationConfig):
            config.api_key = leonardo_api_key
            return LeonardoImageProxy(config=config)
        elif isinstance(config, LocalImageGenerationConfig):
            return LocalSDXLImageProxy(config=config)
        else:
            raise ValueError(f"Unknown Image Generation Configuration: {type(config)}")


class TranscriptionProxyFactory:
    @staticmethod
    def create(
        config: TranscriptionConfigType, openai_api_key: str = None
    ) -> ITranscriptionProxy:
        if isinstance(config, LocalTranscriptionConfig):
            return LocalWhisperProxy(config=config)
        elif isinstance(config, OpenAITranscriptionConfig):
            config.api_key = openai_api_key
            return OpenAIWhisperProxy(config=config)


class SpeechProxyFactory:
    @staticmethod
    def create(
        config: SpeechConfigType, elevenlabs_api_key: str = None
    ) -> ISpeechProxy:
        if isinstance(config, EdgeTTSSpeechConfig):
            return EdgeTTSSpeechProxy(config=config)
        elif isinstance(config, ElevenLabsSpeechConfig):
            config.api_key = elevenlabs_api_key
            return ElevenLabsSpeechProxy(config=config)
        else:
            raise ValueError(f"Unknown Speech Configuration: {type(config)}")


class RedditProxyFactory:
    @staticmethod
    def create(config: RedditConfigType) -> IRedditProxy:
        if isinstance(config, BS4RedditConfig):
            return BS4RedditProxy(config=config)
        else:
            raise ValueError(f"Unknown Reddit Configuration: {type(config)}")


class LLMProxyFactory:
    @staticmethod
    def create(
        config: LLMConfigType,
        openai_api_key: str = None,
        ollama_base_url: str = None,
        google_api_key: str = None,
    ) -> ILLMProxy:
        if config.provider_config.provider == "openai":
            config.provider_config.api_key = openai_api_key
        elif config.provider_config.provider == "ollama":
            config.provider_config.base_url = ollama_base_url
        elif config.provider_config.provider == "google":
            config.provider_config.api_key = google_api_key

        if isinstance(config, DSPyLLMConfig):
            return DSPyLLMProxy(config=config)
        elif isinstance(config, PromptLLMConfig):
            return PromptLLMProxy(config=config)
        else:
            raise ValueError(f"Unknown LLM Configuration: {type(config)}")


class YouTubeProxyFactory:
    @staticmethod
    def create(config: YouTubeConfigType, youtube_api_key: str = None) -> IYouTubeProxy:
        if isinstance(config, PyTubeYouTubeConfig):
            return PyTubeProxy(config=config)
        else:
            raise ValueError(f"Unknown YouTube Configuration: {type(config)}")


class CoverProxyFactory:
    @staticmethod
    def create(config: CoverConfigType) -> ICoverProxy:
        if isinstance(config, PlaywrightCoverConfig):
            return PlaywrightCoverProxy(title_font_size=config.title_font_size)
        else:
            raise ValueError(f"Unknown Cover Configuration: {type(config)}")
