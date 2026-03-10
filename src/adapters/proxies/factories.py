from src.entities.configs.image_generation import (
    ImageGenerationConfigType,
    LeonardoImageGenerationConfig,
    LocalImageGenerationConfig,
)
from src.adapters.proxies.interfaces import IImageGeneratorProxy, ITranscriptionProxy
from src.adapters.proxies.leonardo_proxy import LeonardoImageProxy
from src.adapters.proxies.local_sdxl_proxy import LocalSDXLImageProxy

from src.entities.configs.transcription import (
    TranscriptionConfigType,
    LocalTranscriptionConfig,
    OpenAITranscriptionConfig,
)
from src.adapters.proxies.local_whisper_proxy import LocalWhisperProxy
from src.adapters.proxies.openai_whisper_proxy import OpenAIWhisperProxy
from src.entities.configs.speech import (
    SpeechConfigType,
    EdgeTTSSpeechConfig,
    ElevenLabsSpeechConfig,
)
from src.adapters.proxies.edge_tts_proxy import EdgeTTSSpeechProxy
from src.adapters.proxies.elevenlabs_proxy import ElevenLabsSpeechProxy
from src.adapters.proxies.interfaces import (
    IImageGeneratorProxy,
    ITranscriptionProxy,
    ISpeechProxy,
    IRedditProxy,
)
from src.entities.configs.reddit import RedditConfigType, BS4RedditConfig
from src.adapters.proxies.reddit_proxy import BS4RedditProxy
from src.entities.configs.llm import LLMConfigType, PromptLLMConfig, DSPyLLMConfig
from src.adapters.proxies.llm_prompt_proxy import PromptLLMProxy
from src.adapters.proxies.llm_dspy_proxy import DSPyLLMProxy
from src.adapters.proxies.interfaces import ILLMProxy, IYouTubeProxy
from src.entities.configs.youtube import YouTubeConfigType, PyTubeYouTubeConfig
from src.adapters.proxies.pytube_proxy import PyTubeProxy


class ImageGeneratorFactory:
    @staticmethod
    def create(config: ImageGenerationConfigType) -> IImageGeneratorProxy:
        if isinstance(config, LeonardoImageGenerationConfig):
            return LeonardoImageProxy(config=config)
        elif isinstance(config, LocalImageGenerationConfig):
            return LocalSDXLImageProxy(config=config)
        else:
            raise ValueError(f"Unknown Image Generation Configuration: {type(config)}")


class TranscriptionProxyFactory:
    @staticmethod
    def create(config: TranscriptionConfigType) -> ITranscriptionProxy:
        if isinstance(config, LocalTranscriptionConfig):
            return LocalWhisperProxy(config=config)
        elif isinstance(config, OpenAITranscriptionConfig):
            return OpenAIWhisperProxy(config=config)


class SpeechProxyFactory:
    @staticmethod
    def create(config: SpeechConfigType) -> ISpeechProxy:
        if isinstance(config, EdgeTTSSpeechConfig):
            return EdgeTTSSpeechProxy(config=config)
        elif isinstance(config, ElevenLabsSpeechConfig):
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
    def create(config: LLMConfigType) -> ILLMProxy:
        if isinstance(config, DSPyLLMConfig):
            return DSPyLLMProxy(config=config)
        elif isinstance(config, PromptLLMConfig):
            return PromptLLMProxy(config=config)
        else:
            raise ValueError(f"Unknown LLM Configuration: {type(config)}")

class YouTubeProxyFactory:
    @staticmethod
    def create(config: YouTubeConfigType) -> IYouTubeProxy:
        if isinstance(config, PyTubeYouTubeConfig):
            return PyTubeProxy(config=config)
        else:
            raise ValueError(f"Unknown YouTube Configuration: {type(config)}")
