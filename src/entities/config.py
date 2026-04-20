import random
from typing import List, Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel

from src.entities.configs.proxies.image_generation import (
    ImageGenerationConfigType,
    LocalImageGenerationConfig,
)
from src.entities.configs.proxies.transcription import (
    TranscriptionConfigType,
    LocalTranscriptionConfig,
)
from src.entities.configs.proxies.speech import (
    SpeechConfigType,
    EdgeTTSSpeechConfig,
)
from src.entities.configs.proxies.reddit import RedditConfigType, BS4RedditConfig
from src.entities.configs.proxies.llm import LLMConfigType, DSPyLLMConfig, PromptLLMConfig, LLMProviderConfig
from src.entities.configs.proxies.youtube import YouTubeConfigType, PyTubeYouTubeConfig
from src.entities.configs.proxies.cover import CoverConfigType, PlaywrightCoverConfig
from src.entities.configs.proxies.tiktok import TikTokConfigType, TikTokUploaderConfig

from src.entities.configs.services.captions import CaptionsConfig
from src.entities.configs.services.video import VideoConfig
from src.entities.configs.bots import BotsConfig


class ProxiesConfig(BaseYAMLModel):
    transcription_config: TranscriptionConfigType = Field(
        LocalTranscriptionConfig(), title="Transcription configuration"
    )
    image_generation_config: ImageGenerationConfigType = Field(
        LocalImageGenerationConfig(), title="Image Generation configuration (scenes)"
    )
    portrait_generation_config: Optional[ImageGenerationConfigType] = Field(
        None, title="Image Generation configuration for character portraits (falls back to image_generation_config)",
    )
    speech_config: SpeechConfigType = Field(
        EdgeTTSSpeechConfig(), title="Speech configuration"
    )
    reddit_config: RedditConfigType = Field(
        BS4RedditConfig(), title="Reddit configuration"
    )
    llm_config: LLMConfigType = Field(DSPyLLMConfig(), title="LLM configuration")
    evaluation_llm_config: Optional[LLMConfigType] = Field(
        None,
        title="LLM configuration for story evaluation (falls back to llm_config)",
    )
    youtube_config: YouTubeConfigType = Field(
        PyTubeYouTubeConfig(), title="YouTube configuration"
    )
    cover_config: CoverConfigType = Field(
        PlaywrightCoverConfig(), title="Cover configuration"
    )
    tiktok_config: TikTokConfigType = Field(
        TikTokUploaderConfig(), title="TikTok upload configuration"
    )


class ServicesConfig(BaseYAMLModel):
    video_config: VideoConfig = Field(VideoConfig(), title="Video configuration")
    captions_config: CaptionsConfig = Field(CaptionsConfig())


DEFAULT_EVALUATION_SUBREDDITS = [
    "pettyrevenge",
    "AmItheAsshole",
    "RelationshipAdvice",
    "TrueOffMyChest",
    "AskReddit",
    "ExplainLikeImFive",
    "MaliciousCompliance",
    "Antiwork",
]


class EvaluationConfig(BaseYAMLModel):
    subreddits: List[str] = Field(
        default_factory=lambda: list(DEFAULT_EVALUATION_SUBREDDITS),
        title="Subreddits to evaluate daily",
    )
    min_chars: int = Field(500, title="Minimum post content length in characters")
    max_chars: int = Field(15000, title="Maximum post content length in characters")


class MainConfig(BaseYAMLModel):
    @staticmethod
    def __generate_random_seed() -> str:
        return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=10))

    proxies: ProxiesConfig = Field(default_factory=ProxiesConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    bots: BotsConfig = Field(default_factory=BotsConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    seed: Optional[str] = Field(None, title="Seed")

    def int_seed(self) -> int:
        seed = self.seed or self.__generate_random_seed()
        return int.from_bytes(seed.encode(), "little")
