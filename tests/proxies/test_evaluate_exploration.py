"""The exploration grade: which open experiment a story is a fair test of.

Every proxy checks the answer the same way, so a model that names an
experiment it was not given, or a grade off the scale, stops the search
instead of reaching the history.
"""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from src.entities.configs.proxies.llm import LLMProviderConfig, PromptLLMConfig
from src.entities.language import Language
from src.entities.tuning import Experiment, Stamp
from src.proxies import llm_prompt_proxy
from src.proxies.exploration import normalize_exploration
from src.proxies.llm_prompt_proxy import PromptLLMProxy
from src.proxies.mock_llm_proxy import MockLLMProxy
from tests.fakes.proxies import FakeLLMProxy


def experiment(id: str, question: str = "Histórias de luto com virada seguram?"):
    return Experiment(
        id=id,
        status="open",
        kind="unexplored",
        question=question,
        motivation="O canal nunca testou.",
        looks_like="Luto em que alguém revela um segredo no velório.",
        sample_target=12,
        decision_rule="Confirma se o relativo mediano passar de 1,0.",
        opened=Stamp(cycle=1, date=date(2026, 9, 29)),
    )


EXPERIMENTS = [experiment("E001"), experiment("E002", "Sogros ainda rendem?")]


def test_an_answer_naming_a_given_experiment_is_kept():
    answer = normalize_exploration(
        {"experiment": "E002", "fit": 84, "reason": "Sogra no centro."}, EXPERIMENTS
    )

    assert answer == {"experiment": "E002", "fit": 84.0, "reason": "Sogra no centro."}


@pytest.mark.parametrize("none", [None, "", "null"])
def test_no_experiment_is_a_fit_of_zero(none):
    answer = normalize_exploration(
        {"experiment": none, "fit": 55, "reason": "Nenhuma serve."}, EXPERIMENTS
    )

    assert answer == {"experiment": None, "fit": 0.0, "reason": "Nenhuma serve."}


def test_an_experiment_that_was_not_given_raises_naming_it():
    with pytest.raises(ValueError, match="E009"):
        normalize_exploration({"experiment": "E009", "fit": 90}, EXPERIMENTS)


@pytest.mark.parametrize("fit", [-1, 100.5, None, "alto"])
def test_a_fit_off_the_scale_raises(fit):
    with pytest.raises(ValueError, match="fit"):
        normalize_exploration({"experiment": "E001", "fit": fit}, EXPERIMENTS)


class TestPromptProxy:
    @staticmethod
    def proxy_answering(monkeypatch, text: str) -> tuple[PromptLLMProxy, list]:
        sent = []

        async def completion(**kwargs):
            sent.append(kwargs["messages"][0]["content"])
            choice = SimpleNamespace(
                message=SimpleNamespace(content=text), finish_reason="stop"
            )
            return SimpleNamespace(choices=[choice])

        monkeypatch.setattr(llm_prompt_proxy.litellm, "acompletion", completion)
        proxy = PromptLLMProxy(
            PromptLLMConfig(
                provider_config=LLMProviderConfig(
                    provider="openrouter", model="deepseek/deepseek-v4-flash"
                )
            )
        )
        return proxy, sent

    @pytest.mark.asyncio
    async def test_sends_the_story_and_the_experiments_and_checks_the_answer(
        self, monkeypatch
    ):
        answer = {"experiment": "E001", "fit": 77, "reason": "Velório com segredo."}
        proxy, sent = self.proxy_answering(
            monkeypatch, f"```json\n{json.dumps(answer)}\n```"
        )

        result = await proxy.evaluate_exploration(
            "A tia no velório", "Ela contou tudo.", EXPERIMENTS, Language.PORTUGUESE
        )

        assert result == {**answer, "fit": 77.0}
        (prompt,) = sent
        assert "A tia no velório" in prompt and "Ela contou tudo." in prompt
        assert "E001" in prompt and "Sogros ainda rendem?" in prompt
        assert "Luto em que alguém revela um segredo no velório." in prompt

    @pytest.mark.asyncio
    async def test_an_answer_naming_an_unknown_experiment_raises(self, monkeypatch):
        proxy, _ = self.proxy_answering(
            monkeypatch, '{"experiment": "E404", "fit": 90, "reason": "?"}'
        )

        with pytest.raises(ValueError, match="E404"):
            await proxy.evaluate_exploration("T", "C", EXPERIMENTS, Language.PORTUGUESE)


@pytest.mark.asyncio
async def test_the_mock_grades_for_the_first_experiment():
    result = await MockLLMProxy().evaluate_exploration(
        "T", "C", EXPERIMENTS, Language.PORTUGUESE
    )

    assert result["experiment"] == "E001"
    assert 0 <= result["fit"] <= 100


@pytest.mark.asyncio
async def test_the_fake_answers_by_title_and_nothing_otherwise():
    llm = FakeLLMProxy(
        exploration={
            "Luto": {"experiment": "E001", "fit": 91, "reason": "serve"},
            "Quebrado": RuntimeError("model down"),
        }
    )

    served = await llm.evaluate_exploration(
        "Luto", "", EXPERIMENTS, Language.PORTUGUESE
    )
    unserved = await llm.evaluate_exploration(
        "Outra", "", EXPERIMENTS, Language.PORTUGUESE
    )

    assert (served["experiment"], served["fit"]) == ("E001", 91.0)
    assert (unserved["experiment"], unserved["fit"]) == (None, 0.0)
    with pytest.raises(RuntimeError):
        await llm.evaluate_exploration("Quebrado", "", EXPERIMENTS, Language.PORTUGUESE)
    assert ("evaluate_exploration", "Luto") in llm.calls
