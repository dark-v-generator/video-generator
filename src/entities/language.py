from enum import Enum


class Language(Enum):
    PORTUGUESE = "pt"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    JAPANESE = "ja"
    KOREAN = "ko"
    CHINESE = "zh"


def get_language_name(language: Language) -> str:
    match language:
        case Language.PORTUGUESE:
            return "Portuguese (Brazil)"
        case Language.ENGLISH:
            return "English"
        case Language.SPANISH:
            return "Spanish"
        case Language.FRENCH:
            return "French"
        case Language.GERMAN:
            return "German"
        case Language.ITALIAN:
            return "Italian"
        case Language.JAPANESE:
            return "Japanese"
        case Language.KOREAN:
            return "Korean"
        case Language.CHINESE:
            return "Chinese"
