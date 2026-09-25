"""Pick the configured rendering strategy by name."""

from .contract import Renderer


def select_renderer(name: str, renderers: dict[str, Renderer]) -> Renderer:
    if name not in renderers:
        raise KeyError(
            f"Unknown rendering strategy {name!r}; "
            f"available: {', '.join(sorted(renderers))}"
        )
    return renderers[name]
