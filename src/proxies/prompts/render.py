"""Rendering of the editorial prompts, shared by the proxy and the local CLI."""

import os

import yaml
from jinja2 import Environment, FileSystemLoader

from src.entities.language import Language, get_language_name

_TEMPLATE_DIR = os.path.dirname(__file__)
_EXAMPLES_DIR = os.path.join(os.path.dirname(_TEMPLATE_DIR), "examples")


def _load_examples(name: str) -> list:
    """The worked examples a prompt template embeds, if the file is there."""
    path = os.path.join(_EXAMPLES_DIR, name)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _render(template_name: str, examples: list, title: str, content: str, language):
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
    template = env.get_template(template_name)

    return template.render(
        target_language=get_language_name(language),
        examples=examples,
        reddit_title=title,
        reddit_text=content,
    )


def render_story_prompt(title: str, content: str, language: Language) -> str:
    """The exact prompt the server sends to the scriptwriting model.

    The CLI renders the same text so the assistant working on the laptop
    follows the rules the server would apply. One template is what keeps the
    two from drifting apart.
    """
    return _render("story.jinja2", [], title, content, language)


def render_two_part_story_prompt(title: str, content: str, language: Language) -> str:
    """The same guarantee, for a story told in two videos.

    This one carries the worked examples, exactly as the proxy loads them, so
    the assistant sees the reference scripts the paid model would see.
    """
    examples = _load_examples("two_part_story.yaml")
    return _render("two_part_story.jinja2", examples, title, content, language)
