import litellm

from src.proxies.interfaces import ILLMProxy
from src.entities.configs.proxies.llm import PromptLLMConfig
from src.entities.image_story import ImageStory
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger
import os
import json
import yaml
from jinja2 import Environment, FileSystemLoader

# Set up litellm configuration if necessary
# Disable litellm telemetry
litellm.telemetry = False


class PromptLLMProxy(ILLMProxy):
    def __init__(self, config: PromptLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config

    def _get_model_string(self) -> str:
        provider = self.config.provider
        model = self.config.model
        if provider == "openai":
            return model
        elif provider == "ollama":
            return f"ollama/{model}"
        elif provider == "google":
            return f"gemini/{model}"
        return model

    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        model_str = self._get_model_string()
        self._logger.info(f"Generating 2-part story via LiteLLM {model_str}")

        # 1. Load Examples
        examples = []
        yaml_path = os.path.join(
            os.path.dirname(__file__), "examples", "two_part_story.yaml"
        )
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    examples = data

        # 2. Render Template
        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("two_part_story.jinja2")

        prompt = template.render(
            target_language=get_language_name(target_language),
            examples=examples,
            reddit_title=title,
            reddit_text=content,
        )

        messages = [
            {"role": "user", "content": prompt},
        ]

        # 3. Call LiteLLM
        kwargs = {}
        # Simple JSON mode enforcer for models that support it
        # Gemma 3 on Google/Vertex AI might NOT support JSON mode yet (INVALID_ARGUMENT)
        if ("gpt" in model_str or "gemini" in model_str) and "gemma" not in model_str:
            kwargs["response_format"] = {"type": "json_object"}

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs,
        )

        response_text = response.choices[0].message.content

        # 4. Parse the JSON response
        try:
            # Strip markdown json blocks if returned
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            result = json.loads(response_text)
            return {
                "title": result.get("title", ""),
                "narrator_gender": result.get("narrator_gender", "unknown"),
                "part1": result.get("part1", ""),
                "part2": result.get("part2", ""),
            }
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM JSON response: {response_text}")
            raise RuntimeError(f"Could not parse valid JSON from LLM: {e}")

    async def enhance_transcription(
        self, base_text: str, raw_transcription: list[dict]
    ) -> list[dict]:
        model_str = self._get_model_string()
        self._logger.info(f"Enhancing transcription via LiteLLM {model_str}")

        examples = []
        yaml_path = os.path.join(
            os.path.dirname(__file__), "examples", "transcription_enhancement.yaml"
        )
        if os.path.exists(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    examples = data

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("enhance_transcription.jinja2")

        prompt = template.render(
            base_text=base_text,
            raw_transcription=json.dumps(raw_transcription, ensure_ascii=False),
            examples=examples,
        )

        messages = [
            {"role": "user", "content": prompt},
        ]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        response_text = response.choices[0].message.content

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            self._logger.error(
                f"Failed to parse enhanced transcription JSON: {response_text}"
            )
            raise RuntimeError(f"Could not parse valid JSON from LLM enhancer: {e}")

    async def generate_image_story(
        self, story_text: str, transcription: list[dict]
    ) -> ImageStory:
        model_str = self._get_model_string()
        self._logger.info(f"Generating image story via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("generate_image_story.jinja2")

        prompt = template.render(
            story_text=story_text,
            transcription=json.dumps(transcription, ensure_ascii=False),
        )

        messages = [{"role": "user", "content": prompt}]

        kwargs = {}
        if ("gpt" in model_str or "gemini" in model_str) and "gemma" not in model_str:
            kwargs["response_format"] = {"type": "json_object"}

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs,
        )

        response_text = response.choices[0].message.content

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            data = json.loads(response_text)
            return ImageStory(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self._logger.error(f"Failed to parse image story JSON: {response_text}")
            raise RuntimeError(f"Could not parse valid ImageStory from LLM: {e}")
