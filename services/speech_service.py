from enum import Enum
from proxies import google_proxy, polly_proxy, azure_proxy
from entities.editor import audio_clip


class VoiceGender(Enum):
    MALE = "male"
    FEMALE = "female"


def synthesize_speech(
    text: str, 
    gender: VoiceGender = VoiceGender.MALE,
    rate: float = 1.0,
) -> audio_clip.AudioClip:
    if True:
        if gender == VoiceGender.MALE:
            gender = azure_proxy.VoiceVariation.MALE
        else:
            gender = azure_proxy.VoiceVariation.FEMALE
        return azure_proxy.synthesize_speech(text, gender, rate)
    elif False:
        if gender == VoiceGender.MALE:
            google_tts_gender = google_proxy.VoiceVariation.MALE
        else:
            google_tts_gender = google_proxy.VoiceVariation.FEMALE
        return google_proxy.synthesize_speech(text, google_tts_gender)
    elif False:
        return polly_proxy.synthesize_speech(text)
