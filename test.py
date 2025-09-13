#!/usr/bin/env python3
"""
Example usage of speech synthesis providers with async progress events.

This demonstrates how to use the new async interface with progress tracking and bytes return.
"""

import asyncio

from src.entities.language import Language
from src.services.speech_service import (
    SpeechServiceFactory,
)
from src.entities.progress import ProgressEvent

async def test_speech_service():
    provider_name = "coqui"
    try:
        service = SpeechServiceFactory.create_speech_service(provider_name)
        text = f"Test of {provider_name} with progress events."

        async for event in service.generate_speech(
            text=text, gender="male", rate=1.0, language=Language.ENGLISH
        ):
            if isinstance(event, ProgressEvent):
                if event.progress is not None:
                    print(f"{event.stage} - {event.message} - {event.progress:.0f}%")
                else:
                    print(f"{event.stage} - {event.message}")
            elif isinstance(event, bytes):
                print(f"      ✅ {provider_name.upper()} generation completed!")
                print(f"      Audio data size: {len(event)} bytes")
                with open("test.wav", "wb") as f:
                    f.write(event)

    except Exception as e:
        print(f"      ❌ Error with {provider_name}: {e}")


if __name__ == "__main__":
    asyncio.run(test_speech_service())