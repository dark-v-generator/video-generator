from typing import Literal, Union, Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LLMProviderConfig(BaseYAMLModel):
    provider: Literal["openai", "google", "ollama"] = "ollama"
    model: str = "gemma3:12b"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = Field(None, exclude=True)
    api_key: Optional[str] = Field(None, exclude=True)


class DSPyLLMConfig(BaseYAMLModel):
    type: Literal["dspy"] = "dspy"
    provider_config: LLMProviderConfig = Field(default_factory=LLMProviderConfig)


class PromptLLMConfig(BaseYAMLModel):
    type: Literal["prompt"] = "prompt"
    provider_config: LLMProviderConfig = Field(default_factory=LLMProviderConfig)


LLMConfigType = Union[DSPyLLMConfig, PromptLLMConfig]
