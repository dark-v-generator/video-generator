# The speech proxy's interface names the voice a rendered video narrates with.
from ...proxies.interfaces import ISpeechProxy
from .contract import Renderer
from .narration_over_footage import NarrationOverFootageRenderer
from .registry import select_renderer

__all__ = [
    "ISpeechProxy",
    "NarrationOverFootageRenderer",
    "Renderer",
    "select_renderer",
]
