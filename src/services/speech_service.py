from enum import Enum
from src.entities.language import Language
from src.proxies import azure_proxy


class VoiceGender(Enum):
    MALE = "male"
    FEMALE = "female"


def synthesize_speech(
    text: str,
    gender: VoiceGender = VoiceGender.MALE,
    rate: float = 1.0,
    output_path: str = "output.mp3",
    language: Language = Language.PORTUGUESE
) -> None:
    voice_variation = __get_azure_voice_variation(gender, language)
    return azure_proxy.synthesize_speech(
        text=text, 
        voice_variation=voice_variation, 
        rate=rate, 
        output_path=output_path
    )


def __get_azure_voice_variation(gender: VoiceGender,language: Language) -> azure_proxy.VoiceVariation:
    match language:
        case Language.PORTUGUESE:
            match gender:
                case VoiceGender.MALE:
                    return azure_proxy.VoiceVariation.ANTONIO_NEUTRAL
                case VoiceGender.FEMALE:
                    return azure_proxy.VoiceVariation.THALITA_NEUTRAL
        case Language.ENGLISH:
            match gender:
                case VoiceGender.MALE:
                    return azure_proxy.VoiceVariation.ANDREW_NEUTRAL
                case VoiceGender.FEMALE:
                    return azure_proxy.VoiceVariation.AVA_NEUTRAL
    raise "No voice variation found" 