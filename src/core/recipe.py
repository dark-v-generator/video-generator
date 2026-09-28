"""The part of a video's recipe that is fixed for the whole process.

Prompt versions, models, rendering strategy and speech settings come from the
config and the prompt files; the narrator's gender and voice depend on each
story, so the run fills those in.
"""

from ..entities.config import MainConfig
from ..entities.configs.proxies.llm import LLMConfigType, MockLLMConfig
from ..entities.configs.proxies.speech import EdgeTTSSpeechConfig
from ..entities.history import ProductionRecipe
from ..prompts import loader as prompts


def _model_name(config: LLMConfigType) -> str:
    if isinstance(config, MockLLMConfig):
        return "mock"
    provider = config.provider_config
    return f"{provider.provider}/{provider.model}"


def build_production_recipe(config: MainConfig) -> ProductionRecipe:
    proxies = config.proxies
    speech = proxies.speech_config
    return ProductionRecipe(
        story_prompt_version=prompts.fingerprint("story.jinja2"),
        grading_prompt_version=prompts.fingerprint("evaluate_story.jinja2"),
        # The writer falls back to the main model, as the container wires it.
        writer_model=_model_name(
            proxies.history_adaptation_llm_config or proxies.llm_config
        ),
        grader_model=_model_name(proxies.llm_config),
        rendering_strategy=config.services.video_config.rendering_strategy,
        speech_provider=speech.type,
        speech_rate=(
            speech.default_rate if isinstance(speech, EdgeTTSSpeechConfig) else None
        ),
        narrator_gender="",
        voice_id="",
    )
