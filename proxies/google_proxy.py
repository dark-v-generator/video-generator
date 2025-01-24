from enum import Enum
import tempfile
from google.cloud import texttospeech
from entities.editor.audio_clip import AudioClip

def __create_tts_client():
    return texttospeech.TextToSpeechClient()

class VoiceVariation(Enum):
    MALE = 'pt-BR-Standard-E'
    YOUNG_MALE = 'pt-BR-Standard-B'
    FEMALE = 'pt-BR-Standard-D'
    YOUNG_FEMALE = 'pt-BR-Standard-C'

def synthesize_speech(
        text: str, 
        voice_variation: VoiceVariation = VoiceVariation.MALE) -> AudioClip:
    tts = __create_tts_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="pt-BR", 
        name=voice_variation.value,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0
    )
    response = tts.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_file.write(response.audio_content)
        return AudioClip(temp_file.name)