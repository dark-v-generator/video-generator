import pytest
from jinja2 import TemplateSyntaxError

from src.prompts import loader


class TestRender:
    def test_story(self):
        prompt = loader.render(
            "story.jinja2",
            target_language="Portuguese (Brazil)",
            examples=[],
            reddit_title="O vizinho",
            reddit_text="Ele bateu na porta.",
        )

        assert "O vizinho" in prompt
        assert "Ele bateu na porta." in prompt
        assert "Portuguese (Brazil)" in prompt

    def test_evaluate_story(self):
        prompt = loader.render(
            "evaluate_story.jinja2",
            target_language="Portuguese (Brazil)",
            reddit_title="O vizinho",
            reddit_text="Ele bateu na porta.",
        )

        assert "O vizinho" in prompt

    def test_generate_hashtags(self):
        prompt = loader.render(
            "generate_hashtags.jinja2",
            target_language="Portuguese (Brazil)",
            title="O vizinho",
            summary="Um resumo.",
        )

        assert "Um resumo." in prompt

    def test_enhance_transcription_with_the_shipped_examples(self):
        examples = loader.load_examples("transcription_enhancement")

        prompt = loader.render(
            "enhance_transcription.jinja2",
            base_text="Texto base.",
            raw_transcription="[]",
            examples=examples,
        )

        assert examples
        assert "--- Example 1 ---" in prompt
        assert "Texto base." in prompt


class TestExamples:
    def test_missing_file_means_no_examples(self):
        assert loader.load_examples("nope") == []


class TestValidateAll:
    def test_the_shipped_templates_compile(self):
        loader.validate_all()

    def test_a_broken_template_is_named(self, tmp_path, monkeypatch):
        (tmp_path / "fine.jinja2").write_text("{{ ok }}")
        (tmp_path / "story.jinja2").write_text("Hello {% if %}")
        monkeypatch.setattr(loader, "PROMPTS_DIR", str(tmp_path))

        with pytest.raises(TemplateSyntaxError, match="story.jinja2"):
            loader.validate_all()
