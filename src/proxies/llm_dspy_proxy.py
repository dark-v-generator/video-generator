import os
import yaml
import dspy
from typing import AsyncIterable
from src.proxies.interfaces import ILLMProxy
from src.entities.configs.proxies.llm import DSPyLLMConfig
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger


class TranslateAndAdaptSignature(dspy.Signature):
    """
    You are an expert translator and text adapter.
    Your task is to take the user's raw input text and translate/adapt it into naturally flowing text, mantaining the same meaning and context.
    Make the tone suitable and conversational, ensuring the core message translates accurately and adaptively.
    """

    target_language = dspy.InputField(
        desc="The language to translate and adapt the text into."
    )
    raw_text = dspy.InputField(desc="Raw text content to be translated and adapted.")
    adapted_script = dspy.OutputField(
        desc="The final translated text as a single fluid paragraph without outside commentary."
    )


class TwoPartTikTokStorySignature(dspy.Signature):
    """
    You are an expert TikTok scriptwriter.
    Take the provided original Reddit post (title and text) and transform it into a 2-part engaging TikTok story script.

    Requirements:
    1. Translate the story into the requested target_language, keeping a natural, conversational tone.
    2. Add an engaging, short, viral-style translated title.
    3. Part 1 must end on a major suspense cliffhanger and include a call to action (e.g., "Like and follow for part 2").
    4. Part 2 must resolve the story naturally and end with a final call to action asking for the viewer's opinion.
    5. ONLY provide the text for each section, do NOT include outside commentary, camera directions, or extra formatting.
    """

    target_language = dspy.InputField(
        desc="The language the final scripts should be translated to."
    )
    reddit_post_title = dspy.InputField(desc="The original title of the story.")
    reddit_post_text = dspy.InputField(desc="The original content of the story.")

    viral_title = dspy.OutputField(desc="A catchy translated title for the story.")
    part1_script = dspy.OutputField(
        desc="Part 1 of the story ending with suspense and 'Like for part 2'."
    )
    part2_script = dspy.OutputField(
        desc="Part 2 consisting of the resolution and ending question."
    )


class EnhanceTranscriptionSignature(dspy.Signature):
    """
    You are an AI specialized in correcting timestamped text transcriptions.
    You will be provided with a base text (the ground truth text) and a raw transcription (a JSON array of objects representing words spoken by a TTS engine, each with 'word', 'start', and 'end').

    Your task is to merge, split, or alter the words in the raw transcription so their sequences perfectly match the base text.

    Rules:
    1. ONLY modify the transcription so it perfectly matches the base text.
    2. Maintain the timestamp information as accurately as possible.
    3. If merging words, combine their text and use the earliest 'start' and latest 'end'.
    4. If modifying a word, keep its original 'start' and 'end'.
    5. Return the modified JSON array of objects.
    """

    base_text = dspy.InputField(desc="The correct, ground truth text.")
    raw_transcription = dspy.InputField(
        desc="A JSON string of the raw transcription word segments from the speech-to-text model."
    )

    enhanced_transcription = dspy.OutputField(
        desc="The corrected JSON list containing 'word', 'start', and 'end'."
    )


class DSPyLLMProxy(ILLMProxy):
    def __init__(self, config: DSPyLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config
        self._configure_dspy()

        # dspy.Predict allows us to generate based on the Signature
        self.translator = dspy.Predict(TranslateAndAdaptSignature)

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
                            examples.append(
                                dspy.Example(
                                    target_language="Portuguese",
                                    reddit_post_title=post.get("title", ""),
                                    reddit_post_text=post.get("text", ""),
                                    viral_title=post.get(
                                        "title", ""
                                    ),  # We don't have separate titles in our examples so we map it as expected output style
                                    part1_script=entry.get("part1", ""),
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

        # Initialize dynamically based on selected provider config
        if provider == "openai":
            lm = dspy.OpenAI(model=model_name, max_tokens=self.config.max_tokens)
        elif provider == "ollama":
            lm = dspy.LM(
                model=f"ollama_chat/{model_name}",
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
        elif provider == "google":
            lm = dspy.Google(model=model_name, max_output_tokens=self.config.max_tokens)
        else:
            raise ValueError(f"Unknown DSPy language model provider: {provider}")

        dspy.secrets.configure(lm=lm)

    async def translate_and_adapt(
        self, text: str, target_language: Language
    ) -> AsyncIterable[str]:

        self._logger.info(
            f"Using DSPy to translate and adapt via {self.config.provider}/{self.config.model}"
        )

        # DSPy doesn't natively expose an abstract Async Streaming API universally
        # across all of its module types out of the box without complex custom LM extensions.
        # So we process it entirely and yield the block.

        result = self.translator(
            target_language=get_language_name(target_language), raw_text=text
        )

        # Fake streaming behavior to maintain interface consistency
        content = result.adapted_script
        chunk_size = 20
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

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

        return {
            "title": result.viral_title,
            "part1": result.part1_script,
            "part2": result.part2_script,
        }

    async def enhance_transcription(
        self, base_text: str, raw_transcription: list[dict]
    ) -> list[dict]:
        self._logger.info(
            f"Enhancing transcription via DSPy {self.config.provider}/{self.config.model}"
        )

        enhancer = self._get_transcription_enhancer()
        import json

        result = enhancer(
            base_text=base_text,
            raw_transcription=json.dumps(raw_transcription, ensure_ascii=False),
        )

        response_text = result.enhanced_transcription
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json").strip("```").strip()
        if response_text.startswith("```"):
            response_text = response_text.strip("```").strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self._logger.error(
                f"Failed to parse enhanced transcription JSON: {response_text}"
            )
            raise RuntimeError(f"Could not parse valid JSON from DSPy enhancer: {e}")
