import json
import dspy
from src.prompts import loader as prompts
from src.proxies.interfaces import ILLMProxy
from src.entities.configs.proxies.llm import DSPyLLMConfig
from src.entities.language import Language, get_language_name
from src.core.logging_config import get_logger
from src.capabilities.publishing.hashtags import normalize_hashtags


class TikTokStorySignature(dspy.Signature):
    """
    You are an expert TikTok scriptwriter.
    Take the provided original Reddit post (title and text) and transform it into an engaging TikTok story script.

    Requirements:
    1. Translate or adapt the story into the requested target_language, keeping a natural, conversational tone as if someone is telling the story out loud to a friend.
    2. Write a title in the requested target_language that is the strongest hook of the whole video. It is shown on the cover image and read by the viewer — it is NOT narrated. Lead by concrete harm or injustice done to someone worth rooting for, with a clear antagonist or unfairness, imply a turn is coming without revealing the outcome, and keep a natural spoken voice.
    3. Use natural, colloquial target_language. Prefer everyday words people actually use in casual speech.
    4. Do NOT narrate the title — it is shown on the cover image. The script begins directly in the story, opening on the conflict or the stakes. Example cover title "Meu vizinho me perseguiu por meses" → script begins "Ele começou batendo na minha porta às três da manhã...".
    5. Tell the COMPLETE story in a single script — setup, climax, and resolution. Do NOT split it into parts.
    6. The script MUST end with a story-specific engagement question that invites the viewer to share their opinion, followed by a localized equivalent of "like, follow me, and leave it in the comments". For Portuguese (Brazil), use "Curta, me siga e deixe nos comentários".
    7. TikTok allows videos from 15 seconds up to 10 minutes. Use as much time as the story needs — do NOT rush or cut content to fit a short time limit.
    8. ONLY provide the text for the script, do NOT include outside commentary, camera directions, or extra formatting.
    9. Identify the narrator's gender from contextual clues in the post (e.g., "I (25F)", gender-specific terms).
    10. STRONG WORDS POLICY — applies to ALL narrated text including the title. This script is spoken by
        a TTS engine on TikTok where every word is audio-moderated. NEVER use: matar, morrer, morto,
        morte, assassinar, suicídio, suicidou, atirar, esfaquear, sangue, sangrento, droga, drogas,
        cocaína, maconha, viciado, transar, transou, sexo explícito, estuprar, estupro, abuso sexual,
        arma de fogo, pistola / kill, murder, die, dead, suicide, shoot, stab, blood, drugs, cocaine,
        weed, rape, sex (explicit), gun.
        Use euphemisms: "dar um fim"/"fazer desaparecer"/"ir de arrasta" for killing; "descansou"/
        "partiu dessa pra melhor"/"não está mais entre nós" for death; "tomou uma decisão definitiva"
        for suicide; "ficou com"/"dormiu com"/"tiveram uma noite juntos" for sex; "forçou a situação"/
        "fez algo horrível" for assault; "substâncias"/"coisas erradas" for drugs; "aquele objeto"/
        "aconteceu o pior" for weapons. Keep intensity through tone, context, and metaphor — not
        graphic words.
    11. Reddit posts use specific conventions you MUST handle:
        - Letter abbreviations for names (e.g., "B", "M", "J") must be replaced with realistic fake names.
        - Interpret age/gender notation according to the source language. In English, "(28M)" means a 28-year-old male and "(22F)" means a 22-year-old female. In Portuguese, "H" means homem and "M" means mulher.
        - Acronyms like "SO" (significant other), "MIL" (mother-in-law), "FIL" (father-in-law), "BIL" (brother-in-law), "SIL" (sister-in-law) should be replaced with natural language.
        - Understand AITA-style judgments and translate/adapt them naturally: "AITA" means "Am I the asshole?", "NTA" means "Not the asshole", "YTA" means "You're the asshole", "ESH" means "Everyone sucks here", and "NAH" means "No assholes here". In Portuguese communities, handle terms like "EOB", "NEOB", "TEOB", "NGM", "sou o babaca" and "não é o babaca".
        - "TL;DR" sections should be omitted from the script.
        - "Edit:" sections should be omitted from the script.
        - Recognize source-language acronyms and shorthand in English, Portuguese, Spanish, or any other language present in the post, then replace them with clear, natural target_language wording.
    """

    target_language = dspy.InputField(
        desc="The language the final script should be translated to."
    )
    reddit_post_title = dspy.InputField(desc="The original title of the story.")
    reddit_post_text = dspy.InputField(desc="The original content of the story.")

    viral_title = dspy.OutputField(
        desc="The strong hook shown on the COVER image (read by the viewer, NOT narrated). Leads by concrete harm/injustice with a clear victim and antagonist, without revealing the outcome. Natural and spoken in tone."
    )
    narrator_gender = dspy.OutputField(
        desc="The narrator's gender inferred from the post. Must be exactly one of: 'male', 'female', or 'unknown'."
    )
    script = dspy.OutputField(
        desc="The complete story script: begins directly in the story (NO title narrated), the full story (setup, climax, resolution), ending with a story-specific engagement question followed by a localized like/follow/comment call to action."
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

    Return a JSON object with: resumo (target_language summary), notas (per-criterion grades with target_language justificativa),
    nota_geral (average), veredito.
    Keep the JSON keys and veredito values exactly as specified. Understand source-language acronyms and shorthand before evaluating, including AITA/NTA/YTA/ESH/NAH, SO, MIL, FIL, BIL, SIL, TL;DR, ETA, OP, and Portuguese terms such as EOB, NEOB, TEOB, NGM, "sou o babaca" and "não é o babaca".
    """

    target_language = dspy.InputField(desc="The language for the evaluation output.")
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
    5. Remove the introduction (title and localized "Part N." marker, such as "Parte N.") from the output. Start from the first word after that marker since the title is shown as a cover image.
    6. Return only a JSON array of objects with 'word', 'start', and 'end' keys.
    """

    base_text = dspy.InputField(desc="The correct, ground truth text.")
    raw_transcription = dspy.InputField(
        desc="A JSON string of the raw transcription word segments from the speech-to-text model."
    )

    enhanced_transcription = dspy.OutputField(
        desc='A JSON array string of corrected word segments: [{"word": ..., "start": ..., "end": ...}, ...]'
    )


class DSPyLLMProxy(ILLMProxy):
    def __init__(self, config: DSPyLLMConfig):
        self._logger = get_logger(__name__)
        self.config = config.provider_config
        self._configure_dspy()

        # Transcription enhancer
        self._enhancer = None

    def _get_transcription_enhancer(self):
        if self._enhancer is not None:
            return self._enhancer

        enhancer = dspy.Predict(EnhanceTranscriptionSignature)
        examples = []
        try:
            for entry in prompts.load_examples("transcription_enhancement"):
                examples.append(
                    dspy.Example(
                        base_text=entry.get("base_text", ""),
                        raw_transcription=entry.get("raw_transcription", ""),
                        enhanced_transcription=entry.get("enhanced_transcription", ""),
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
            for k in (
                "retencao",
                "qualidade",
                "viralizacao",
                "adequacao_tiktok",
                "gancho",
            )
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

    async def generate_hashtags(
        self, title: str, summary: str, target_language: Language
    ) -> list[str]:
        self._logger.info(
            f"Generating hashtags via DSPy {self.config.provider}/{self.config.model}"
        )

        class HashtagSignature(dspy.Signature):
            """Generate TikTok hashtags for a story."""

            title: str = dspy.InputField()
            summary: str = dspy.InputField()
            target_language: str = dspy.InputField()
            hashtags_json: str = dspy.OutputField(
                desc='JSON: {"hashtags": ["fyp", "storytime", ...]}'
            )

        generator = dspy.Predict(HashtagSignature)
        result = generator(
            title=title,
            summary=summary,
            target_language=get_language_name(target_language),
        )

        try:
            data = self._parse_json_text(result.hashtags_json)
            tags = data.get("hashtags", [])
            return normalize_hashtags(tags)
        except (json.JSONDecodeError, AttributeError):
            self._logger.warning("Failed to parse hashtag JSON from DSPy")
            return normalize_hashtags([])

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

    @staticmethod
    def _parse_json_text(text: str):
        if text.startswith("```json"):
            text = text.strip("```json").strip("```").strip()
        if text.startswith("```"):
            text = text.strip("```").strip()
        return json.loads(text)
