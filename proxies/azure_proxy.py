from enum import Enum
import os
import tempfile
import azure.cognitiveservices.speech as speechsdk
from entities.editor.audio_clip import AudioClip


class VoiceVariation(Enum):
    MALE = "pt-BR-AntonioNeural"
    FEMALE = "pt-BR-ThalitaMultilingualNeural"
    MALE_2 = "pt-BR-MacerioMultilingualNeural"
    MALE_3 = "pt-BR-MacerioMultilingualNeural"
    FEMALE_2 = "pt-BR-BrendaNeural"
    FEMALE_3 = "pt-BR-ThalitaNeural"
    FEMALE_4 = "pt-BR-FranciscaNeural"


def __get_speech_config():
    speech_key = os.environ.get("AZURE_TTS_SUBSCRIPTION_KEY")
    service_region = os.environ.get("AZURE_TTS_SERVICE_REGION")
    if speech_key is None:
        raise "AZURE_TTS_SUBSCRIPTION_KEY is not set"
    if service_region is None:
        raise "AZURE_TTS_SERVICE_REGION is not set"
    return speechsdk.SpeechConfig(subscription=speech_key, region=service_region)


def synthesize_speech(text: str, voice_variation: VoiceVariation = VoiceVariation.MALE):
    speech_config = __get_speech_config()
    speech_config.speech_synthesis_voice_name = voice_variation.value

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        filename = temp_file.name
        audio_config = speechsdk.AudioConfig(filename=filename)
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    result = speech_synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return AudioClip(filename)
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
        raise "Unable to convert azure speech"
