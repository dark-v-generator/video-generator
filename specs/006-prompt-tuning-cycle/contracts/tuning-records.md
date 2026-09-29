# Registros de ajuste (M1)

Formato dos arquivos de `tuning/`, o contrato de leitura e as invariantes que
`just tuning-check` verifica. Campos e regras: [data-model.md](../data-model.md).

## Arquivos

```yaml
# tuning/exploration.yaml
cycle: 1
share: 0.25
share_since: 2026-10-02
min_fit: 70
experiments:            # a ordem é a prioridade
  - id: E001
    status: open
    kind: challenge
    question: "Histórias com desconhecidos ou empresas funcionam quando o narrador reage?"
    motivation: "0 de 10 acima de 1,5×, mas nenhuma das 10 tinha reação do narrador."
    belief: B004
    looks_like: "Conflito com um desconhecido, loja ou empresa em que o narrador faz algo a respeito."
    sample_target: 10
    decision_rule: "Confirma a crença se o relativo mediano ficar abaixo de 0,8; refuta se ficar acima de 1,2."
    opened: {cycle: 1, date: 2026-10-02}
    replaces: null
    outcome: null
```

```yaml
# tuning/cycles/001.yaml
number: 1
opened: 2026-10-02
deployed: 2026-10-02
closed: null
prompts:
  story: 42072ca8893c
  evaluate_story: 9f3a1c0d2b7e
  generate_hashtags: 1b2c3d4e5f60
  evaluate_exploration: null      # até o M4
settings: {writer_model: moonshotai/kimi-k2.6, grader_model: deepseek/deepseek-v4-flash, rendering_strategy: narration_over_footage}
changes: []                       # o primeiro ciclo é a linha de base
experiment_changes: []
outside_changes: []
evaluation: null
reports: []
closing: null
```

Os valores de fingerprint e de `rendering_strategy` acima são ilustrativos; a
semente usa os que `prompts.fingerprint` e o config devolvem no dia.

`beliefs.yaml` é `beliefs: [Belief, ...]`. Cada relatório é um documento YAML
com os campos de `Report`.

## `TuningRecords` — `src/storage/tuning_contract.py`

```python
class TuningRecords(Protocol):
    def exploration_plan(self) -> ExplorationPlan: ...
    def beliefs(self) -> list[Belief]: ...
    def cycles(self) -> list[Cycle]: ...          # ordenados por number
    def open_cycle(self) -> Cycle: ...            # TuningError se não houver exatamente um
    def reports(self) -> list[Report]: ...        # ordenados por id
    def story_labels(self) -> dict[int, StoryLabel]: ...   # a mais recente por record_id
    def write_summary(self, markdown: str) -> None: ...    # tuning/README.md
```

`FileTuningRecords(root: Path)` lê do disco a cada chamada. Arquivo malformado
ou campo inválido levanta `TuningError` com o caminho e o campo. `exploration.yaml`
ausente devolve o plano vazio; os outros arquivos ausentes devolvem lista vazia.

O código **não escreve** os registros: quem escreve é a skill, editando os
arquivos. A única escrita pelo código é o resumo gerado.

## `just tuning-check` — `scripts/tuning_check.py`

Sai com código 0 e uma linha por verificação, ou com código 1 e a lista do que
falhou. Verifica:

1. Todo arquivo carrega nas entidades.
2. Existe exatamente um ciclo com `closed: null`, e é o de maior `number`;
   `exploration.yaml.cycle` é esse número.
3. Ids de experimento, crença e relatório são únicos.
4. Experimento `open` ou `closed` tem todos os campos de texto; `closed` tem
   `outcome`; `challenge` tem `belief` existente; `replaces` aponta para um
   experimento fechado.
5. Crença `base` ou `does_not_work` tem `evidence.videos ≥ 10`; toda crença tem
   ao menos a entrada `entered` em `history`.
6. Todo relatório pertence a um ciclo existente e está na lista `reports` dele;
   `corrects` aponta para um relatório anterior.
7. `PromptChange` rejeitada tem `reason`; `justification.ref` existe.
8. **Fingerprints**: os de `prompts` do ciclo aberto são os dos arquivos em
   `src/prompts/`. Diferença é reportada como "prompt X mudou fora da rotina:
   `<registrado>` → `<em disco>`", a menos que já conste em `outside_changes`.
9. Relatórios e ciclos fechados não mudaram em relação ao `HEAD` do git
   (FR-041). Correção é relatório novo com `corrects`.

A verificação 9 usa `git diff --name-only HEAD -- tuning/reports tuning/cycles`
e ignora arquivos novos e o ciclo aberto.

## `just tuning-summary` — `scripts/tuning_summary.py`

Gera `tuning/README.md` com, nesta ordem: ciclo aberto (número, desde quando,
versões dos prompts, fatia); **base**; **o que não funciona**; pistas e
contestadas; experimentos abertos com progresso do último relatório; fila de
ideias; ciclos (datas, mudanças de prompt, avaliação); relatórios (data,
recomendação, decisão). Cada crença mostra evidência, confiança, data do último
teste e histórico.

Para FR-044, cada mudança de prompt aparece com o trecho `after`, o ciclo e a
justificativa: procurar uma frase do prompt no README leva ao ciclo e ao
achado.

A saída é determinística: mesmos arquivos, mesmo README.
