import os
import json
import yaml
import dspy
from src.proxies.interfaces import ILLMProxy
from src.entities.configs.proxies.llm import DSPyLLMConfig
from src.entities.image_story import ImageStory
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger


class TwoPartTikTokStorySignature(dspy.Signature):
    """
    You are an expert TikTok scriptwriter.
    Take the provided original Reddit post (title and text) and transform it into a 2-part engaging TikTok story script.

    Requirements:
    1. Translate the story into the requested target_language, keeping a natural, conversational tone as if someone is telling the story out loud to a friend.
    2. Add a short, clickbaity title that hooks the viewer in the first 3 seconds. The title must create curiosity and make the audience want to stay for the full story. Use open loops, tease unexpected outcomes, or hint at drama without spoiling. It should still sound natural and spoken, but it MUST grab attention.
    3. Use natural, colloquial language. Prefer everyday words people actually use in casual speech. For example, prefer "print" over "captura de tela", "deletei" over "excluí permanentemente", etc.
    4. Each part must start with the title followed by "Parte 1." or "Parte 2." before the story text. Example: "Meu vizinho me perseguiu por meses. Parte 1. Tudo começou quando...".
    5. Part 1 must end before the climax. The climax belongs in Part 2. Part 1 is setup, Part 2 is payoff. Revenge, confrontations, and resolutions go in Part 2.
    6. Part 1 must end on suspense, with a call to action (e.g., "Curta e me siga para a parte 2.").
    7. Part 2 must contain the climax, resolve the story, and end with a story-specific engagement question that invites the viewer to share their opinion, followed by "Curta, me siga e deixe nos comentários". Example: "E você, acha que eu fui babaca? Curta, me siga e deixe nos comentários".
    8. ONLY provide the text for each section, do NOT include outside commentary, camera directions, or extra formatting.
    8. Identify the narrator's gender from contextual clues in the post (e.g., "I (25F)", gender-specific terms).
    10. Keep all language appropriate and family-friendly for a general social media audience. Soften any
       strong or sensitive moments with milder, everyday words. If the original post contains strong
       language or insults, rephrase the situation without repeating those words.
    9. Reddit posts use specific conventions you MUST handle:
       - Letter abbreviations for names (e.g., "B", "M", "J") must be replaced with realistic fake names.
       - Age/gender notation like "(28M)" means a 28-year-old male, "(22F)" means a 22-year-old female.
       - Acronyms like "SO" (significant other), "MIL" (mother-in-law), "FIL" (father-in-law), "BIL" (brother-in-law), "SIL" (sister-in-law) should be replaced with natural language.
       - "AITA" means "Am I the asshole?" and "NTA" means "Not the asshole".
       - "TL;DR" sections should be omitted from the script.
       - "Edit:" sections should be omitted from the script.
    """

    target_language = dspy.InputField(
        desc="The language the final scripts should be translated to."
    )
    reddit_post_title = dspy.InputField(desc="The original title of the story.")
    reddit_post_text = dspy.InputField(desc="The original content of the story.")

    viral_title = dspy.OutputField(
        desc="A short, clickbaity translated title that hooks the viewer in the first 3 seconds. Must create curiosity and make the audience want to hear the story. Use open loops or tease unexpected outcomes. Sound natural and spoken, not robotic."
    )
    narrator_gender = dspy.OutputField(
        desc="The narrator's gender inferred from the post. Must be exactly one of: 'male', 'female', or 'unknown'."
    )
    part1_script = dspy.OutputField(
        desc="Part 1: starts with '{title}. Parte 1.' then the setup and context, ending before the climax with suspense and a call to action."
    )
    part2_script = dspy.OutputField(
        desc="Part 2: starts with '{title}. Parte 2.' then the climax and resolution, ending with a story-specific engagement question followed by 'Curta, me siga e deixe nos comentários'."
    )


class TikTokStorySignature(dspy.Signature):
    """
    You are an expert TikTok scriptwriter.
    Take the provided original Reddit post (title and text) and transform it into an engaging TikTok story script.

    Requirements:
    1. Translate the story into the requested target_language, keeping a natural, conversational tone as if someone is telling the story out loud to a friend.
    2. Add a short, clickbaity title that hooks the viewer in the first 3 seconds. The title must create curiosity and make the audience want to hear the story. Use open loops, tease unexpected outcomes, or hint at drama without spoiling. It should still sound natural and spoken, not robotic.
    3. Use natural, colloquial language. Prefer everyday words people actually use in casual speech. For example, prefer "print" over "captura de tela", "deletei" over "excluí permanentemente", etc.
    4. The script must start with the title before the story text. Example: "Meu vizinho me perseguiu por meses. Tudo começou quando...".
    5. Tell the COMPLETE story in a single script — setup, climax, and resolution. Do NOT split it into parts.
    6. The script MUST end with a story-specific engagement question that invites the viewer to share their opinion, followed by "Curta, me siga e deixe nos comentários". Example: "E você, acha que eu fui babaca? Curta, me siga e deixe nos comentários".
    7. TikTok allows videos from 15 seconds up to 10 minutes. Use as much time as the story needs — do NOT rush or cut content to fit a short time limit.
    8. ONLY provide the text for the script, do NOT include outside commentary, camera directions, or extra formatting.
    9. Identify the narrator's gender from contextual clues in the post (e.g., "I (25F)", gender-specific terms).
    10. Keep all language appropriate and family-friendly for a general social media audience. Soften any
        strong or sensitive moments with milder, everyday words. If the original post contains strong
        language or insults, rephrase the situation without repeating those words.
    11. Reddit posts use specific conventions you MUST handle:
        - Letter abbreviations for names (e.g., "B", "M", "J") must be replaced with realistic fake names.
        - Age/gender notation like "(28M)" means a 28-year-old male, "(22F)" means a 22-year-old female.
        - Acronyms like "SO" (significant other), "MIL" (mother-in-law), "FIL" (father-in-law), "BIL" (brother-in-law), "SIL" (sister-in-law) should be replaced with natural language.
        - "AITA" means "Am I the asshole?" and "NTA" means "Not the asshole".
        - "TL;DR" sections should be omitted from the script.
        - "Edit:" sections should be omitted from the script.
    """

    target_language = dspy.InputField(
        desc="The language the final script should be translated to."
    )
    reddit_post_title = dspy.InputField(desc="The original title of the story.")
    reddit_post_text = dspy.InputField(desc="The original content of the story.")

    viral_title = dspy.OutputField(
        desc="A short, clickbaity translated title that hooks the viewer in the first 3 seconds. Must create curiosity and make the audience want to hear the story. Use open loops or tease unexpected outcomes. Sound natural and spoken, not robotic."
    )
    narrator_gender = dspy.OutputField(
        desc="The narrator's gender inferred from the post. Must be exactly one of: 'male', 'female', or 'unknown'."
    )
    script = dspy.OutputField(
        desc="The complete story script: starts with '{title}.' then the full story (setup, climax, resolution), ending with a story-specific engagement question followed by 'Curta, me siga e deixe nos comentários'."
    )


class StoryEvaluationSignature(dspy.Signature):
    """
    You are an expert content evaluator for TikTok storytelling channels.
    Evaluate a Reddit post's potential as a narrated TikTok video with satisfying background footage.

    Grade each criterion from 0 to 100:
    1. Potencial de Retenção (retencao) — hooks early, good pacing, tension/curiosity from the start.
    2. Qualidade da História (qualidade) — well-structured setup/conflict/payoff, memorable, unique, emotionally engaging.
    3. Potencial de Viralização (viralizacao) — share factor, universal emotions (revenge, justice, shock, wholesome).
    4. Adequação pra TikTok (adequacao_tiktok) — appropriate length, works as narrated story, family-friendly.
    5. Força do Gancho (gancho) — strong opening hook, clickbaity title potential.

    Grading: 90-100 exceptional, 70-89 strong, 50-69 decent, 30-49 weak, 0-29 poor.
    Verdict: nota_geral >= 80 "Excelente", >= 60 "Boa", >= 40 "Mediana", < 40 "Fraca".

    Return a JSON object with: resumo (Portuguese summary), notas (per-criterion grades with justificativa),
    nota_geral (average), veredito.
    """

    target_language = dspy.InputField(
        desc="The language for the evaluation output."
    )
    reddit_post_title = dspy.InputField(desc="The original title of the Reddit post.")
    reddit_post_text = dspy.InputField(desc="The original content of the Reddit post.")

    evaluation_json = dspy.OutputField(
        desc='A JSON object: {"resumo": "...", "notas": {"retencao": {"nota": N, "justificativa": "..."}, '
        '"qualidade": {...}, "viralizacao": {...}, "adequacao_tiktok": {...}, "gancho": {...}}, '
        '"nota_geral": N.N, "veredito": "Excelente|Boa|Mediana|Fraca"}'
    )


class EnhanceTranscriptionSignature(dspy.Signature):
    """
    You are an AI specialized in correcting timestamped text transcriptions.
    You will be provided with a base text (the ground truth text) and a raw transcription (a JSON array of objects representing words spoken by a TTS engine, each with 'word', 'start', and 'end').

    Your task is to merge, split, or alter the words in the raw transcription so their sequences perfectly match the base text.

    Rules:
    1. Only modify the transcription so it perfectly matches the base text.
    2. Maintain the timestamp information as accurately as possible.
    3. If merging words, combine their text and use the earliest 'start' and latest 'end'.
    4. If modifying a word, keep its original 'start' and 'end'.
    5. Remove the introduction (title and "Parte N." marker) from the output. Start from the first word after "Parte N." since the title is shown as a cover image.
    6. Return only a JSON array of objects with 'word', 'start', and 'end' keys.
    """

    base_text = dspy.InputField(desc="The correct, ground truth text.")
    raw_transcription = dspy.InputField(
        desc="A JSON string of the raw transcription word segments from the speech-to-text model."
    )

    enhanced_transcription = dspy.OutputField(
        desc='A JSON array string of corrected word segments: [{"word": ..., "start": ..., "end": ...}, ...]'
    )


class GenerateImageStorySignature(dspy.Signature):
    """
    You are an expert at creating visual storyboards for narrated video content.

    Given a narrated story text and its word-level transcription with timestamps,
    produce a visual timeline for the video as a JSON object.

    Rules:
    1. introduction_end_time: the `end` timestamp of the last word before the story begins (e.g. end of "Parte 1.").
    2. call_to_action_start_time: the `start` timestamp of the first CTA word (e.g. "Curta").
    3. 10-15 images illustrating scenes. First at 0.0 (blurred during intro, mood background).
       Second image a few sentences after introduction_end_time so the viewer sees image 1 unblurred.
       Strictly increasing start_times, last before call_to_action_start_time.
    4. Each image start_time should be the `end` timestamp of the last word of the sentence the
       previous image illustrates. Use exact transcription values (e.g. 10.94), not rounded numbers.
    5. Each image lasts roughly 4-8 seconds. Split longer scenes into multiple images with different
       angles or moments.
    6. Visual consistency: describe every character identically across prompts (age, hair, build,
       clothing). Pick one art style and append it to every prompt.
    7. All image prompts must be appropriate for a general audience. Use creative, indirect visuals:
       romantic moments → dimly lit room, silhouettes, hands holding.
       conflict → aftermath (broken object, shocked expression) or tension before.
       emotional moments → facial expressions, body language, environment.
       Suggest what happened through context and setting, not directly.
    8. Return only a JSON object, no commentary.
    """

    story_text = dspy.InputField(desc="The full narrated story text.")
    transcription = dspy.InputField(
        desc="JSON string of word-level transcription: [{word, start, end}, ...]"
    )
    style_context = dspy.InputField(
        desc="Optional style guide from a previous part describing characters and art style. "
        "If provided, follow it strictly for visual consistency. Empty string if not available.",
        default="",
    )

    image_story_json = dspy.OutputField(
        desc='A JSON object string: {"introduction_end_time": <float>, "call_to_action_start_time": <float>, "images": [{"start_time": <float>, "description": "...", "prompt": "..."}, ...]}'
    )


class DSPyLLMProxy(ILLMProxy):
    def __init__(self, config: DSPyLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config
        self._configure_dspy()

        # We use dspy.ChainOfThought or just Predict for the 2-part story.
        self._story_generator = None

        # Transcription enhancer
        self._enhancer = None

    def _get_transcription_enhancer(self):
        if self._enhancer is not None:
            return self._enhancer

        enhancer = dspy.Predict(EnhanceTranscriptionSignature)
        examples = []
        try:
            yaml_path = os.path.join(
                os.path.dirname(__file__),
                "prompts",
                "examples",
                "transcription_enhancement.yaml",
            )

            if os.path.exists(yaml_path):
                import yaml

                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                    if data:
                        for entry in data:
                            examples.append(
                                dspy.Example(
                                    base_text=entry.get("base_text", ""),
                                    raw_transcription=entry.get(
                                        "raw_transcription", ""
                                    ),
                                    enhanced_transcription=entry.get(
                                        "enhanced_transcription", ""
                                    ),
                                ).with_inputs("base_text", "raw_transcription")
                            )

                if examples:
                    self._logger.info(
                        f"Loaded {len(examples)} example(s) for transcription enhancement."
                    )
                    teleprompter = dspy.teleprompt.LabeledFewShot(k=len(examples))
                    enhancer = teleprompter.compile(student=enhancer, trainset=examples)
        except Exception as e:
            self._logger.error(
                f"Failed to load dspy transcription enhance examples: {e}"
            )

        self._enhancer = enhancer
        return self._enhancer

    def _get_story_generator(self):
        if self._story_generator is not None:
            return self._story_generator

        generator = dspy.Predict(TwoPartTikTokStorySignature)

        # Load few-shot examples from YAML
        examples = []
        try:
            yaml_path = os.path.join(
                os.path.dirname(__file__), "examples", "two_part_story.yaml"
            )
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        for entry in data:
                            post = entry.get("original_post", {})
                            # Extract viral title from part1 (first sentence)
                            part1_text = entry.get("part1", "")
                            viral_title = (
                                part1_text.split(". Parte 1.")[0].strip()
                                if ". Parte 1." in part1_text
                                else post.get("title", "")
                            )
                            examples.append(
                                dspy.Example(
                                    target_language="Portuguese",
                                    reddit_post_title=post.get("title", ""),
                                    reddit_post_text=post.get("text", ""),
                                    viral_title=viral_title,
                                    narrator_gender=entry.get(
                                        "narrator_gender", "unknown"
                                    ),
                                    part1_script=part1_text,
                                    part2_script=entry.get("part2", ""),
                                ).with_inputs(
                                    "target_language",
                                    "reddit_post_title",
                                    "reddit_post_text",
                                )
                            )

                if examples:
                    # Optimize or just attach as few-shot demos for Predict/ChainOfThought
                    # The easiest way to inject examples in a raw dspy.Predict is to assign them directly.
                    # For production we would use BootstrapFewShot
                    self._logger.info(
                        f"Loaded {len(examples)} examples from YAML for TikTok generation."
                    )
                    teleprompter = dspy.teleprompt.LabeledFewShot(k=len(examples))
                    # LabeledFewShot doesn't require compiling with a metric if we just want to inject exact examples
                    # We wrap the module to include them.
                    generator = teleprompter.compile(
                        student=generator, trainset=examples
                    )
        except Exception as e:
            self._logger.error(f"Failed to load dspy_examples.yaml: {e}")

        self._story_generator = generator
        return self._story_generator

    def _configure_dspy(self):
        provider = self.config.provider
        model_name = self.config.model

        # Build optional kwargs only when explicitly set
        extra_kwargs = {}
        if self.config.max_tokens is not None:
            extra_kwargs["max_tokens"] = self.config.max_tokens
        if self.config.temperature is not None:
            extra_kwargs["temperature"] = self.config.temperature

        # Initialize dynamically based on selected provider config
        if provider == "openai":
            lm = dspy.OpenAI(model=model_name, **extra_kwargs)
        elif provider == "ollama":
            lm = dspy.LM(
                model=f"ollama_chat/{model_name}",
                **extra_kwargs,
            )
        elif provider == "google":
            lm = dspy.LM(
                model=f"gemini/{model_name}",
                api_key=self.config.api_key,
                **extra_kwargs,
            )
        elif provider == "openrouter":
            lm = dspy.LM(
                model=f"openrouter/{model_name}",
                api_key=self.config.api_key,
                **extra_kwargs,
            )
        else:
            raise ValueError(f"Unknown DSPy language model provider: {provider}")

        dspy.settings.configure(lm=lm)

    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        self._logger.info(
            f"Generating 2-part TikTok story via DSPy {self.config.provider}/{self.config.model}"
        )

        generator = self._get_story_generator()

        result = generator(
            target_language=get_language_name(target_language),
            reddit_post_title=title,
            reddit_post_text=content,
        )

        raw_gender = result.narrator_gender.strip().lower()
        if raw_gender not in ("male", "female"):
            raw_gender = "unknown"

        return {
            "title": result.viral_title,
            "narrator_gender": raw_gender,
            "part1": result.part1_script,
            "part2": result.part2_script,
        }

    async def generate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        self._logger.info(
            f"Generating single TikTok story via DSPy {self.config.provider}/{self.config.model}"
        )

        generator = dspy.Predict(TikTokStorySignature)

        result = generator(
            target_language=get_language_name(target_language),
            reddit_post_title=title,
            reddit_post_text=content,
        )

        raw_gender = result.narrator_gender.strip().lower()
        if raw_gender not in ("male", "female"):
            raw_gender = "unknown"

        return {
            "title": result.viral_title,
            "narrator_gender": raw_gender,
            "script": result.script,
        }

    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        self._logger.info(
            f"Evaluating story via DSPy {self.config.provider}/{self.config.model}"
        )

        generator = dspy.Predict(StoryEvaluationSignature)

        result = generator(
            target_language=get_language_name(target_language),
            reddit_post_title=title,
            reddit_post_text=content,
        )

        data = self._parse_json_text(result.evaluation_json)
        return self._normalize_evaluation(data)

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
        self._logger.info(
            f"Revising story via DSPy {self.config.provider}/{self.config.model} "
            "(falling back to generate_two_part_story with feedback in content)"
        )
        combined_content = (
            f"ORIGINAL SCRIPT:\n{json.dumps(current_script, ensure_ascii=False, indent=2)}\n\n"
            f"USER FEEDBACK:\n{feedback}\n\n"
            "Rewrite the script incorporating the feedback above."
        )
        return await self.generate_two_part_story(
            title=current_script.get("title", ""),
            content=combined_content,
            target_language=target_language,
        )

    async def enhance_transcription(
        self, base_text: str, raw_transcription: list[dict]
    ) -> list[dict]:
        self._logger.info(
            f"Enhancing transcription via DSPy {self.config.provider}/{self.config.model}"
        )

        enhancer = self._get_transcription_enhancer()

        result = enhancer(
            base_text=base_text,
            raw_transcription=json.dumps(raw_transcription, ensure_ascii=False),
            config={"max_tokens": 16000},
        )

        response_text = result.enhanced_transcription
        return self._parse_json_text(response_text)

    async def generate_characters(
        self, title: str, part1: str, part2: str, target_language: Language
    ) -> list[dict]:
        self._logger.info(
            f"Generating characters via DSPy {self.config.provider}/{self.config.model}"
        )
        combined = f"Title: {title}\n\nPart 1:\n{part1}\n\nPart 2:\n{part2}"
        result = await self.generate_two_part_story(
            title=title,
            content=f"Extract characters from this story:\n{combined}",
            target_language=target_language,
        )
        return [{"name": "Narrator", "description": "Main character", "visual_prompt": "A person"}]

    async def generate_image_story(
        self,
        story_text: str,
        transcription: list[dict],
        style_context: str | None = None,
        characters: list[dict] | None = None,
        introduction_end_time: float = 0.0,
        call_to_action_start_time: float = 0.0,
    ) -> ImageStory:
        self._logger.info(
            f"Generating image story via DSPy {self.config.provider}/{self.config.model}"
        )

        generator = dspy.Predict(GenerateImageStorySignature)
        result = generator(
            story_text=story_text,
            transcription=json.dumps(transcription, ensure_ascii=False),
            style_context=style_context or "",
        )

        data = self._parse_json_text(result.image_story_json)
        if isinstance(data, list):
            data = {"images": data}
        data["introduction_end_time"] = introduction_end_time
        data["call_to_action_start_time"] = call_to_action_start_time
        return ImageStory(**data)

    @staticmethod
    def _parse_json_text(text: str):
        if text.startswith("```json"):
            text = text.strip("```json").strip("```").strip()
        if text.startswith("```"):
            text = text.strip("```").strip()
        return json.loads(text)
