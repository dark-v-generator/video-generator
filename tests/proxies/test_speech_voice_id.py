"""Which voice each speech proxy narrates with, as the history records it."""

import pytest

from src.entities.configs.proxies.speech import (
    EdgeTTSSpeechConfig,
    ElevenLabsSpeechConfig,
    SpeechVoiceConfig,
)
from src.entities.language import Language
from src.proxies.edge_tts_proxy import EdgeTTSSpeechProxy
from src.proxies.elevenlabs_proxy import ElevenLabsSpeechProxy

_VOICES = {
    Language.PORTUGUESE: SpeechVoiceConfig(
        male_voice_id="configured-male", female_voice_id="configured-female"
    )
}


class TestEdgeTTS:
    @pytest.mark.parametrize(
        "gender, language, expected",
        [
            ("male", Language.PORTUGUESE, "pt-BR-AntonioNeural"),
            ("female", Language.PORTUGUESE, "pt-BR-FranciscaNeural"),
            ("male", Language.ENGLISH, "en-US-ChristopherNeural"),
            ("female", Language.ENGLISH, "en-US-AriaNeural"),
        ],
    )
    def test_defaults_without_config(self, gender, language, expected):
        proxy = EdgeTTSSpeechProxy(EdgeTTSSpeechConfig())

        assert proxy.voice_id(gender, language) == expected

    def test_configured_voices_win(self):
        proxy = EdgeTTSSpeechProxy(EdgeTTSSpeechConfig(voices=_VOICES))

        assert proxy.voice_id("male", Language.PORTUGUESE) == "configured-male"
        assert proxy.voice_id("female", Language.PORTUGUESE) == "configured-female"


class TestElevenLabs:
    def test_default_without_config(self):
        proxy = ElevenLabsSpeechProxy(ElevenLabsSpeechConfig(api_key="k"))

        assert proxy.voice_id("female", Language.PORTUGUESE) == "pNInz6obbf5AWCG1OKVK"

    def test_configured_voices_win(self):
        proxy = ElevenLabsSpeechProxy(
            ElevenLabsSpeechConfig(api_key="k", voices=_VOICES)
        )

        assert proxy.voice_id("male", Language.PORTUGUESE) == "configured-male"
        assert proxy.voice_id("female", Language.PORTUGUESE) == "configured-female"
