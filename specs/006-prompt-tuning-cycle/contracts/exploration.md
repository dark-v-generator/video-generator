# Exploração na rodada diária (M4, M5)

## Prompt — `src/prompts/evaluate_exploration.jinja2` (M4)

Variáveis: `target_language`, `reddit_title`, `reddit_text`, `experiments`
(lista de `{id, question, looks_like}`).

O que o prompt explica, como racional (Princípio III):

- o canal reserva parte da produção para aprender, e cada experimento é uma
  pergunta feita à audiência;
- a nota mede se esta história é um **teste justo** de uma das perguntas: do
  tipo que a pergunta descreve e contável como um bom vídeo, porque uma história
  fraca que fracassa não responde nada;
- a nota não mede se a história vai bem: isso é outra avaliação, feita à parte;
- ser diferente do que o canal publica não vale por si; sem pergunta que a
  história sirva, a resposta é nenhuma.

Saída:

```json
{"experiment": "E001", "fit": 84, "reason": "…"}
```

`experiment` é um dos ids recebidos ou `null`; com `null`, `fit` é 0.

## Proxy (M4)

```python
class ILLMProxy(Protocol):
    async def evaluate_exploration(
        self, title: str, content: str,
        experiments: Sequence[Experiment], target_language: Language,
    ) -> dict: ...   # {"experiment": str | None, "fit": float, "reason": str}
```

Normalização: id que não está entre os recebidos levanta `ValueError` nomeando
o id; `fit` fora de 0–100 levanta. Implementado em `llm_prompt_proxy`,
`llm_dspy_proxy`, `mock_llm_proxy` e `tests/fakes/proxies.py`. No fake, o
resultado é programável por título.

## Descoberta (M4)

```python
async def find_best_stories(
    self, *, language, sort="top", time_filter="day", posts_per_sub=25,
    top_per_sub=5, subreddits=None, exclude_urls=None,
    experiments: Sequence[Experiment] = (), min_fit: int = 70,
) -> list[EvaluatedStory]: ...
```

- `experiments` vazio: comportamento atual, nenhuma chamada a mais.
- Com experimentos: depois de `grade`, chama `evaluate_exploration` para cada
  avaliada cujo veredito não é `Erro` e preenche `story.exploration`. Devolve as
  histórias de base de hoje (mesma regra Excelente/Boa, até 10) seguidas das que
  têm `fit ≥ min_fit` e ainda não estão na lista, em ordem de `fit`.
- Falha em `evaluate_exploration` propaga: a busca falha, como qualquer falha
  de descoberta (`record.stop("discovery_failed")`).

## Vagas — `src/capabilities/exploration/` (M5)

```python
class ExplorationSource(Protocol):
    def plan(self) -> ExplorationPlan: ...

@dataclass(frozen=True)
class GoalCounts:
    total: int        # vídeos produzidos desde share_since
    exploration: int  # deles, com objetivo de experimento

def slots_due(share: float, counts: GoalCounts, target: int) -> int: ...

def arrange(
    candidates: Sequence[EvaluatedStory], plan: ExplorationPlan,
    counts: GoalCounts, target: int,
) -> tuple[list[EvaluatedStory], int]: ...   # (ordenadas, vagas reservadas)
```

`slots_due`: [research.md §6](../research.md). Devolve 0 com `share = 0` ou sem
experimento aberto.

`arrange`:

1. `slots = slots_due(...)`.
2. Para cada vaga, percorre `plan.open()` em ordem; o primeiro experimento com
   candidata não escolhida, `exploration.experiment == id` e `fit ≥ min_fit`
   leva a vaga, com a de maior `fit`. A escolhida recebe `goal = id`
   (`dataclasses.replace`).
3. Devolve as escolhidas, depois as demais candidatas **elegíveis para base**
   (veredito Excelente ou Boa) na ordem recebida, com `goal = "base"`.
   Candidatas que só entraram pela nota de exploração e não foram escolhidas
   ficam de fora.
4. O segundo valor é `slots`, mesmo que menos histórias tenham sido escolhidas.

Casos cobertos por teste: fatia 0,25 e alvo 3 ao longo de 12 dias; dia sem
história adequada; dois experimentos com história, o de maior prioridade leva;
experimento prioritário sem história, o seguinte leva; história que é boa de
base e serve a um experimento ocupa uma vaga só, a de exploração.

## Histórico (M4)

```python
class HistoryStore(Protocol):
    ...
    def goal_counts(self, since: date) -> GoalCounts: ...
```

Conta `video_records` com `created_at ≥ since` e `imported = 0`. Colunas e
migração: [data-model.md §2](../data-model.md). `InMemoryHistoryStore` acompanha.

## `DailyRun` — mudanças (M5)

```python
@dataclass(kw_only=True)
class DailyRun:
    ...                               # campos atuais inalterados
    exploration: ExplorationSource    # M5
```

Em `_find`, e só ali:

```python
plan = self.exploration.plan()
candidates = await self.discovery.find_best_stories(
    ..., experiments=plan.open(), min_fit=plan.min_fit,
)
...
target = min(requested, len(candidates))
candidates, slots = arrange(candidates, plan, self.history.goal_counts(plan.share_since), target)
self.record.found(len(candidates), target, exploration_slots=slots)
```

- Mensagens de progresso: as mesmas. Com `slots > 0`, a mensagem de fim de
  busca ganha " (N de exploração)"; com `slots = 0` o texto é idêntico ao de
  hoje, e o golden não muda.
- O laço de produção não muda: percorre a lista até o alvo. Uma história de
  exploração pulada é substituída pela próxima da lista.
- `publish` (publish-only) não lê o plano: o objetivo já está no registro.
- `daily_run.py` fica em até 320 linhas; se as linhas acima não couberem, a
  montagem da mensagem de fim de busca vai para `run_record.py`.

## `RunRecord` (M4, M5)

- `video(...)`: preenche `goal`, `exploration_experiment`, `exploration_fit` a
  partir da candidata, e `cycle` a partir de `recipe` estendida com o número do
  ciclo do plano.
- `found(candidates, target, exploration_slots=0)`.
- `finish()`: `exploration_filled` = vídeos gravados com `goal != "base"`.

## Container (M5)

`exploration_source = providers.Factory(FileTuningRecords, root=tuning_dir())`,
exposto como `ExplorationSource` (o método `plan()` é
`exploration_plan()` com outro nome no contrato da capacidade). Factory, não
Singleton: o plano é relido a cada rodada, porque o bot fica no ar entre
deploys.
