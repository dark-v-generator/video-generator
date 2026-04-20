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
    GEMINI_SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    def __init__(self, config: PromptLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config

    def _get_model_string(self) -> str:
        provider = self.config.provider
        model = self.config.model
        if provider == "openai":
            return f"openai/{model}"
        elif provider == "ollama":
            return f"ollama/{model}"
        elif provider == "google":
            return f"gemini/{model}"
        return model

    def _get_extra_kwargs(self, model_str: str, json_mode: bool = True) -> dict:
        kwargs = {}
        if (
            json_mode
            and ("gpt" in model_str or "gemini" in model_str or "openai/" in model_str)
            and "gemma" not in model_str
        ):
            kwargs["response_format"] = {"type": "json_object"}
        if self.config.provider == "google":
            kwargs["safety_settings"] = self.GEMINI_SAFETY_SETTINGS
        return kwargs

    def _get_completion_kwargs(
        self,
        model_str: str,
        json_mode: bool = True,
        default_max_tokens: int | None = None,
    ) -> dict:
        """Build kwargs for litellm.acompletion, using the correct token-limit
        parameter for the model (max_completion_tokens for newer OpenAI models,
        max_tokens for everything else)."""
        kwargs = self._get_extra_kwargs(model_str, json_mode=json_mode)
        max_tok = self.config.max_tokens or default_max_tokens
        if max_tok is not None:
            model = self.config.model
            uses_completion_tokens = self.config.provider == "openai" and (
                model.startswith("gpt-5")
                or model.startswith("o3")
                or model.startswith("o4")
            )
            if uses_completion_tokens:
                kwargs["max_completion_tokens"] = max_tok
            else:
                kwargs["max_tokens"] = max_tok
        return kwargs

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

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str),
        )

        response_text = response.choices[0].message.content

        if not response_text:
            self._logger.error(
                f"LLM returned empty response. "
                f"Finish reason: {response.choices[0].finish_reason}"
            )
            raise RuntimeError(
                "LLM returned empty content for story generation. "
                "This may be caused by a safety filter. Check the post content."
            )

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

    async def generate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        model_str = self._get_model_string()
        self._logger.info(f"Generating single story via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("story.jinja2")

        prompt = template.render(
            target_language=get_language_name(target_language),
            examples=[],
            reddit_title=title,
            reddit_text=content,
        )

        messages = [
            {"role": "user", "content": prompt},
        ]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str),
        )

        response_text = response.choices[0].message.content

        if not response_text:
            self._logger.error(
                f"LLM returned empty response. "
                f"Finish reason: {response.choices[0].finish_reason}"
            )
            raise RuntimeError(
                "LLM returned empty content for story generation. "
                "This may be caused by a safety filter. Check the post content."
            )

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            result = json.loads(response_text)
            return {
                "title": result.get("title", ""),
                "narrator_gender": result.get("narrator_gender", "unknown"),
                "script": result.get("script", ""),
            }
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM JSON response: {response_text}")
            raise RuntimeError(f"Could not parse valid JSON from LLM: {e}")

    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        model_str = self._get_model_string()
        self._logger.info(f"Evaluating story via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("evaluate_story.jinja2")

        prompt = template.render(
            target_language=get_language_name(target_language),
            reddit_title=title,
            reddit_text=content,
        )

        messages = [{"role": "user", "content": prompt}]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str),
        )

        response_text = response.choices[0].message.content

        if not response_text:
            self._logger.error(
                "LLM returned empty response. Finish reason: %s",
                response.choices[0].finish_reason,
            )
            raise RuntimeError(
                "LLM returned empty content for story evaluation. "
                "This may be caused by a safety filter."
            )

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            data = json.loads(response_text)
            return self._normalize_evaluation(data)
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse evaluation JSON: {response_text}")
            raise RuntimeError(f"Could not parse valid JSON from LLM: {e}")

    @staticmethod
    def _normalize_evaluation(data: dict) -> dict:
        notas = data.get("notas", {})
        grades = [
            notas.get(k, {}).get("nota", 0)
            for k in ("retencao", "qualidade", "viralizacao", "adequacao_tiktok", "gancho")
        ]
        nota_geral = round(sum(grades) / len(grades), 1) if grades else 0.0

        if nota_geral >= 80:
            veredito = "Excelente"
        elif nota_geral >= 60:
            veredito = "Boa"
        elif nota_geral >= 40:
            veredito = "Mediana"
        else:
            veredito = "Fraca"

        return {
            "resumo": data.get("resumo", ""),
            "notas": notas,
            "nota_geral": nota_geral,
            "veredito": veredito,
        }

    async def revise_story(
        self, current_script: dict, feedback: str, target_language: Language
    ) -> dict:
        model_str = self._get_model_string()
        self._logger.info(f"Revising story via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("revise_story.jinja2")

        prompt = template.render(
            current_script=json.dumps(current_script, ensure_ascii=False, indent=2),
            feedback=feedback,
            target_language=get_language_name(target_language),
        )

        messages = [{"role": "user", "content": prompt}]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str),
        )

        response_text = response.choices[0].message.content

        if not response_text:
            raise RuntimeError(
                "LLM returned empty content for story revision. "
                "This may be caused by a safety filter."
            )

        try:
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
            self._logger.error(f"Failed to parse revised story JSON: {response_text}")
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
            **self._get_completion_kwargs(model_str, json_mode=False),
        )

        response_text = response.choices[0].message.content

        if not response_text:
            self._logger.error(
                f"LLM returned empty response. "
                f"Finish reason: {response.choices[0].finish_reason}"
            )
            raise RuntimeError(
                "LLM returned empty content for transcription enhancement. "
                "This may be caused by a safety filter."
            )

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            decoder = json.JSONDecoder()
            stripped = response_text.strip()
            result, end = decoder.raw_decode(stripped)
            tail = stripped[end:].strip()
            if tail:
                self._logger.warning(
                    "enhance_transcription: ignored %d trailing chars after first JSON value",
                    len(tail),
                )
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for v in result.values():
                    if isinstance(v, list):
                        return v
            return result
        except json.JSONDecodeError as e:
            self._logger.error(
                f"Failed to parse enhanced transcription JSON: {response_text}"
            )
            raise RuntimeError(f"Could not parse valid JSON from LLM enhancer: {e}")

    async def generate_characters(
        self, title: str, part1: str, part2: str, target_language: Language
    ) -> list[dict]:
        model_str = self._get_model_string()
        self._logger.info(f"Generating characters via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("generate_characters.jinja2")

        prompt = template.render(
            title=title,
            part1=part1,
            part2=part2,
            target_language=target_language.value,
        )

        messages = [{"role": "user", "content": prompt}]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str),
        )

        response_text = response.choices[0].message.content
        if not response_text:
            raise RuntimeError("LLM returned empty content for character generation.")

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            data = json.loads(response_text)
            if isinstance(data, dict) and "characters" in data:
                data = data["characters"]
            elif isinstance(data, dict) and all(
                k in data for k in ("name", "visual_prompt")
            ):
                data = [data]
            if not isinstance(data, list):
                raise ValueError(f"Expected list of characters, got {type(data)}")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            self._logger.error(f"Failed to parse characters JSON: {response_text}")
            raise RuntimeError(f"Could not parse characters from LLM: {e}")

    async def generate_image_story(
        self,
        story_text: str,
        transcription: list[dict],
        style_context: str | None = None,
        characters: list[dict] | None = None,
        introduction_end_time: float = 0.0,
        call_to_action_start_time: float = 0.0,
    ) -> ImageStory:
        model_str = self._get_model_string()
        self._logger.info(f"Generating image story via LiteLLM {model_str}")

        template_dir = os.path.join(os.path.dirname(__file__), "prompts")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("generate_image_story.jinja2")

        prompt = template.render(
            story_text=story_text,
            transcription=json.dumps(transcription, ensure_ascii=False),
            style_context=style_context,
            characters=characters,
        )

        messages = [{"role": "user", "content": prompt}]

        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            api_key=self.config.api_key,
            temperature=self.config.temperature,
            **self._get_completion_kwargs(model_str, default_max_tokens=8192),
        )

        response_text = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "length":
            self._logger.warning("Image story response was truncated (hit token limit)")

        if not response_text:
            self._logger.error(
                "LLM returned empty response. Finish reason: %s", finish_reason
            )
            raise RuntimeError(
                "LLM returned empty content for image story generation. "
                "This may be caused by a safety filter. Check the story text."
            )

        try:
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```").strip()
            if response_text.startswith("```"):
                response_text = response_text.strip("```").strip()

            decoder = json.JSONDecoder()
            stripped = response_text.strip()
            data, end = decoder.raw_decode(stripped)
            tail = stripped[end:].strip()
            if tail:
                self._logger.warning(
                    "generate_image_story: ignored %d trailing chars",
                    len(tail),
                )

            if isinstance(data, list):
                data = {"images": data}
            elif isinstance(data, dict) and "images" not in data:
                if all(k in data for k in ("start_time", "description", "prompt")):
                    data = {"images": [data]}

            if not isinstance(data, dict):
                raise ValueError(f"Expected object or array, got {type(data)}")

            data["introduction_end_time"] = introduction_end_time
            data["call_to_action_start_time"] = call_to_action_start_time
            return ImageStory(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self._logger.error(f"Failed to parse image story JSON: {response_text}")
            raise RuntimeError(f"Could not parse valid ImageStory from LLM: {e}")
