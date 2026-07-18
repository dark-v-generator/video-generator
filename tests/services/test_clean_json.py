"""Regression tests for PromptLLMProxy._clean_json.

Covers the case where a model pretty-prints a multi-line string value with
literal newlines inside the JSON string (invalid JSON), which previously raised
``json.JSONDecodeError: Unterminated string`` and failed the whole generation.
"""

import json

from src.proxies.llm_prompt_proxy import PromptLLMProxy


def _parse(raw):
    return json.loads(PromptLLMProxy._clean_json(raw))


def test_plain_valid_json_passes_through():
    data = _parse('{"title": "oi", "part1": "abc"}')
    assert data["title"] == "oi"


def test_markdown_fenced_json():
    data = _parse('```json\n{"title": "oi", "part1": "abc"}\n```')
    assert data["part1"] == "abc"


def test_literal_newlines_inside_string_value():
    # The exact failure mode observed with kimi-k2.6: a string value that spans
    # multiple physical lines with literal newlines + indentation.
    raw = (
        '```json\n'
        '{\n'
        '  "title": "Minha irmã proibiu meus filhos no casamento",\n'
        '  "narrator_gender": "unknown",\n'
        '  "part1": "Minha irmã decidiu que meus filhos não podiam ir.\n'
        '             Aquilo doeu, mas eu disse que tudo bem.",\n'
        '  "part2": "No fim, eu não paguei nada. E você? Curta e comente."\n'
        '}\n'
        '```'
    )
    data = _parse(raw)
    assert data["narrator_gender"] == "unknown"
    assert data["title"].startswith("Minha irmã")
    # the newline inside the value is preserved (escaped), content intact
    assert "Aquilo doeu" in data["part1"]
    assert data["part2"].endswith("Curta e comente.")


def test_tabs_inside_string_value():
    raw = '{"script": "linha um\tcom tab", "title": "t"}'
    data = _parse(raw)
    assert "com tab" in data["script"]
