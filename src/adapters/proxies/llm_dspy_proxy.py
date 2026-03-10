import os
import yaml
import dspy
from typing import AsyncIterable
from src.adapters.proxies.interfaces import ILLMProxy
from src.entities.configs.llm import DSPyLLMConfig
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


class DSPyLLMProxy(ILLMProxy):
    def __init__(self, config: DSPyLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config
        self._configure_dspy()

        # dspy.Predict allows us to generate based on the Signature
        self.translator = dspy.Predict(TranslateAndAdaptSignature)

        # We use dspy.ChainOfThought or just Predict for the 2-part story.
        self._story_generator = None

    def _get_story_generator(self):
        if self._story_generator is not None:
            return self._story_generator

        generator = dspy.Predict(TwoPartTikTokStorySignature)

        # Load few-shot examples from YAML
        examples = []
        try:
            yaml_path = os.path.join(os.path.dirname(__file__), "dspy_examples.yaml")
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

        dspy.settings.configure(lm=lm)

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
