from enum import Enum
from proxies import google_proxy, polly_proxy
from entities.editor import audio_clip
from google.cloud import texttospeech

class VoiceGender(Enum):
    MALE = 'male'
    FEMALE = 'female'
    
def synthesize_speech(text: str, gender: VoiceGender = VoiceGender.MALE) -> audio_clip.AudioClip:
    if gender == VoiceGender.MALE:
        google_tts_gender = google_proxy.VoiceVariation.MALE
    else:
        google_tts_gender = google_proxy.VoiceVariation.FEMALE
    
    if True:
        return google_proxy.synthesize_speech(text, google_tts_gender)
    else:
        return polly_proxy.synthesize_speech(text)
