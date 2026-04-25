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

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, str):
            return None

        normalized = value.lower().replace("_", "-")
        aliases = {
            "pt-br": cls.PORTUGUESE,
            "pt_br": cls.PORTUGUESE,
            "en-us": cls.ENGLISH,
            "en-gb": cls.ENGLISH,
            "es-es": cls.SPANISH,
            "es-mx": cls.SPANISH,
            "fr-fr": cls.FRENCH,
            "de-de": cls.GERMAN,
            "it-it": cls.ITALIAN,
            "ja-jp": cls.JAPANESE,
            "ko-kr": cls.KOREAN,
            "zh-cn": cls.CHINESE,
            "zh-tw": cls.CHINESE,
        }
        return aliases.get(normalized)


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
