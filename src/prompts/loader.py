"""The prompts sent to the models live here, as editable Jinja templates.

Editing a ``*.jinja2`` file changes what the model receives with no code
change. ``validate_all`` compiles every template up front so a broken edit
stops the process at boot, naming the file, instead of halfway through a run.
"""

import os
from functools import lru_cache

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=None)
def _environment(directory: str) -> Environment:
    return Environment(loader=FileSystemLoader(directory))


def render(template_name: str, **variables) -> str:
    return _environment(PROMPTS_DIR).get_template(template_name).render(**variables)


def load_examples(name: str) -> list:
    """Few-shot examples from ``examples/<name>.yaml``; none when the file is absent."""
    path = os.path.join(PROMPTS_DIR, "examples", f"{name}.yaml")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def validate_all() -> None:
    environment = _environment(PROMPTS_DIR)
    for name in sorted(os.listdir(PROMPTS_DIR)):
        if not name.endswith(".jinja2"):
            continue
        try:
            environment.get_template(name)
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"{name}: {e.message}", e.lineno, name=name, filename=e.filename
            ) from e
