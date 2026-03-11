import argparse
import asyncio
import os
import json
from src.proxies.factories import (
    LLMProxyFactory,
    SpeechProxyFactory,
    TranscriptionProxyFactory,
)
from src.entities.configs.proxies.transcription import LocalTranscriptionConfig
from src.entities.configs.proxies.speech import EdgeTTSSpeechConfig
from src.entities.configs.proxies.llm import DSPyLLMConfig, PromptLLMConfig, LLMProviderConfig
from src.entities.language import Language


async def main():
    parser = argparse.ArgumentParser(description="Test transcription enhancement")
    parser.add_argument(
        "--type",
        type=str,
        choices=["dspy", "prompt"],
        default="dspy",
        help="Type of LLM Proxy to use",
    )
    args = parser.parse_args()

    # Provide a simple short text sequence to test
    test_text = (
        "Meu novo vizinho do andar de baixo fez o síndico me importunar. Parte 2."
    )

    print(f"Generating TTS for: {test_text}")
    speech_proxy = SpeechProxyFactory.create(EdgeTTSSpeechConfig())
    audio_bytes = await speech_proxy.generate_speech(
        test_text, gender="male", rate=1.2, language=Language.PORTUGUESE
    )

    print("Transcribing TTS audio via Whisper...")
    whisper_proxy = TranscriptionProxyFactory.create(LocalTranscriptionConfig())
    transcription = whisper_proxy.transcribe(audio_bytes, language=Language.PORTUGUESE)

    raw_words = [w.model_dump() for w in transcription.words]
    print(f"Raw words generated: {len(raw_words)}")

    print(f"Using proxy type: {args.type.upper()} with local ollama (gemma3:12b)")
    provider_config = LLMProviderConfig(
        provider="ollama", model="gemma3:12b", temperature=0.1, max_tokens=3000
    )

    if args.type == "dspy":
        config = DSPyLLMConfig(provider_config=provider_config)
    else:
        config = PromptLLMConfig(provider_config=provider_config)

    llm_proxy = LLMProxyFactory.create(config)

    print("Enhancing transcription...")
    enhanced_words = await llm_proxy.enhance_transcription(
        base_text=test_text, raw_transcription=raw_words
    )

    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)

    audio_file = os.path.join(output_dir, "test_enhance_audio.wav")
    with open(audio_file, "wb") as f:
        f.write(audio_bytes)

    raw_file = os.path.join(output_dir, f"test_raw_{args.type}.json")
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_words, f, ensure_ascii=False, indent=2)

    enhanced_file = os.path.join(output_dir, f"test_enhanced_{args.type}.json")
    with open(enhanced_file, "w", encoding="utf-8") as f:
        json.dump(enhanced_words, f, ensure_ascii=False, indent=2)

    print(f"Done! Check tests/data for output.")
    print(f"Outputs:\n- {audio_file}\n- {raw_file}\n- {enhanced_file}")


if __name__ == "__main__":
    asyncio.run(main())
