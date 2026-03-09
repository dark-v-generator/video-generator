from typing import Literal, Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LLMProviderConfig(BaseYAMLModel):
    provider: Literal["openai", "google", "ollama"] = "ollama"
    model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: int = 2000


class DSPyLLMConfig(BaseYAMLModel):
    type: Literal["dspy"] = "dspy"
    provider_config: LLMProviderConfig = Field(default_factory=LLMProviderConfig)


class PromptLLMConfig(BaseYAMLModel):
    type: Literal["prompt"] = "prompt"
    provider_config: LLMProviderConfig = Field(default_factory=LLMProviderConfig)


LLMConfigType = Union[DSPyLLMConfig, PromptLLMConfig]
