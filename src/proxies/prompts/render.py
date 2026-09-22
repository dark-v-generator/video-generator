"""Rendering of the editorial prompts, shared by the proxy and the local CLI."""

import os

from jinja2 import Environment, FileSystemLoader

from src.entities.language import Language, get_language_name

_TEMPLATE_DIR = os.path.dirname(__file__)


def render_story_prompt(title: str, content: str, language: Language) -> str:
    """The exact prompt the server sends to the scriptwriting model.

    The CLI renders the same text so the assistant working on the laptop
    follows the rules the server would apply. One template is what keeps the
    two from drifting apart.
    """
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
    template = env.get_template("story.jinja2")

    return template.render(
        target_language=get_language_name(language),
        examples=[],
        reddit_title=title,
        reddit_text=content,
    )
