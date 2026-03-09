import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.container import container
from src.entities.language import Language


async def test_pipeline():
    print("--- Starting Translation Pipeline Test ---")

    # Ensure data directory exists
    os.makedirs("tests/data", exist_ok=True)

    # Get proxies from container
    speech_proxy = container.speech_proxy()
    transcription_proxy = container.transcription_proxy()
    llm_proxy = container.llm_proxy()

    original_text = "This is a simple pipeline test to check if we can successfully transform text to speech, transcribe it, translate the text with our LLM proxy, and then create speech and transcribe it again."
    print(f"\n[1] Original Text:\n{original_text}\n")

    # 1. Text to Speech
    print("[2] Generating Speech (English)...")
    speech_bytes = await speech_proxy.generate_speech(
        text=original_text, gender="male", language=Language.ENGLISH
    )
    print(f"    -> Success: Generated {len(speech_bytes)} bytes of audio")

    with open("tests/data/output_english.mp3", "wb") as f:
        f.write(speech_bytes)
    print("    -> Saved to tests/data/output_english.mp3\n")

    # 2. Transcribe
    print("[3] Transcribing Speech...")
    transcription = transcription_proxy.transcribe(
        speech_bytes, language=Language.ENGLISH
    )
    print(f"    -> Transcribed Text: {transcription.text}")

    with open("tests/data/transcription_english.json", "w") as f:
        f.write(transcription.model_dump_json(indent=2))
    print("    -> Saved transcription to tests/data/transcription_english.json\n")

    # 3. Translate via LLM Proxy
    print("[4] Translating and Adapting text (to Portuguese)...")
    translated_text = ""
    print("    -> Streaming Output: ", end="")
    async for chunk in llm_proxy.translate_and_adapt(
        transcription.text, Language.PORTUGUESE
    ):
        translated_text += chunk
        print(chunk, end="", flush=True)
    print("\n")

    # 4. Generate speech again
    print("[5] Generating Speech from Translated Text (Portuguese)...")
    translated_speech_bytes = await speech_proxy.generate_speech(
        text=translated_text, gender="male", language=Language.PORTUGUESE
    )
    print(f"    -> Success: Generated {len(translated_speech_bytes)} bytes of audio")

    with open("tests/data/output_portuguese.mp3", "wb") as f:
        f.write(translated_speech_bytes)
    print("    -> Saved to tests/data/output_portuguese.mp3\n")

    # 5. Transcribe again
    print("[6] Transcribing Translated Speech...")
    translated_transcription = transcription_proxy.transcribe(
        translated_speech_bytes, language=Language.PORTUGUESE
    )
    print(f"    -> Final Transcribed Text: {translated_transcription.text}")

    with open("tests/data/transcription_portuguese.json", "w") as f:
        f.write(translated_transcription.model_dump_json(indent=2))
    print("    -> Saved transcription to tests/data/transcription_portuguese.json\n")

    print("--- Pipeline Test Complete! ---")


if __name__ == "__main__":
    asyncio.run(test_pipeline())
