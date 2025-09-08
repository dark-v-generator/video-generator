import os
import re
import azure.cognitiveservices.speech as speechsdk
from enum import Enum


class VoiceVariation(Enum):
    ANTONIO_NEUTRAL = "pt-BR-AntonioNeural"
    THALITA_NEUTRAL = "pt-BR-ThalitaNeural"
    AVA_NEUTRAL = "en-US-AvaMultilingualNeural"
    ANDREW_NEUTRAL = "en-US-AndrewMultilingualNeural"


def __get_speech_config():
    speech_key = os.environ.get("AZURE_TTS_SUBSCRIPTION_KEY")
    service_region = os.environ.get("AZURE_TTS_SERVICE_REGION")
    if speech_key is None:
        raise "AZURE_TTS_SUBSCRIPTION_KEY is not set"
    if service_region is None:
        raise "AZURE_TTS_SERVICE_REGION is not set"
    return speechsdk.SpeechConfig(subscription=speech_key, region=service_region)


def __text_to_ssml(text: str, voice: str, rate: float = 1.0, break_time="1s"):
    text = re.sub(r"\n\s*\n+", f'\n<break time="{break_time}" />\n', text)
    text = re.sub(
        r"[A-ZÀ-Ý][A-ZÀ-Ý]+(?:\s*[A-ZÀ-Ý]+)*",
        r'<emphasis level="strong">\g<0></emphasis>',
        text,
    )
    ssml_text = """
    <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="pt-BR">
        <voice name="{voice_name}">
        <prosody rate="{rate}">
        {text}
        </prosody>
        </voice>
    </speak>
    """.format(
        text=text, voice_name=voice, rate=str(round(rate, 2))
    )
    return ssml_text


def synthesize_speech(
    text: str,
    voice_variation: VoiceVariation = VoiceVariation.ANTONIO_NEUTRAL,
    rate: float = 1.0,
    output_path: str = "output.mp3",
) -> str:
    speech_config = __get_speech_config()
    speech_config.speech_synthesis_voice_name = voice_variation.value
    
    # Set output format to MP3
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )
    
    audio_config = speechsdk.AudioConfig(filename=output_path)
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, 
        audio_config=audio_config
    )
    ssml_text = __text_to_ssml(
        text, voice=voice_variation.value, rate=rate, break_time="300ms"
    )
    result = speech_synthesizer.speak_ssml(ssml_text)
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
        raise "Unable to convert azure speech"

