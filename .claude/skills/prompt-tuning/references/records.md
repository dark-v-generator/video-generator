# Os registros de `tuning/`

O que cada arquivo guarda, com um exemplo, e as categorias dos rótulos. As
regras de validação moram em `src/entities/tuning.py`; `just tuning-check` as
aplica. Chaves em inglês, texto livre em português: o operador lê estes
arquivos sem o assistente (FR-045).

Os registros são memória de longo prazo do canal. Quem os escreve é esta
skill, editando os arquivos; o código só os lê, com exceção do `README.md`
gerado. Uma coisa escrita aqui e commitada vira fato consultado por relatórios
futuros, então cada campo diz só o que a evidência sustenta.

## Quem pode mudar o quê

| Arquivo | Muda quando | Nunca |
|---|---|---|
| `exploration.yaml` | em qualquer relatório, com a aprovação do operador | editar um experimento aberto no lugar |
| `beliefs.yaml` | no fechamento, ou quando um veredito sai | apagar entrada de `history` |
| `cycles/NNN.yaml` do ciclo aberto | a cada relatório (lista `reports`, `experiment_changes`, `outside_changes`) e no fechamento | mudar `prompts` sem fechar o ciclo |
| `cycles/NNN.yaml` fechado | nunca | — |
| `reports/AAAA-MM-DD.yaml` | só na sessão em que foi escrito, antes do commit | reescrever depois do commit; correção é relatório novo com `corrects` |
| `story_labels.csv` | acrescentar linhas | apagar ou editar linha; reclassificar é linha nova |
| `README.md` | só por `just tuning-summary` | editar à mão |

A verificação 9 do check compara `reports/` e os ciclos fechados com o `HEAD`
do git: um relatório já commitado que mude faz o check falhar.

## Ids

- Experimento: `E` + 3 dígitos (`E001`), o próximo depois do maior que já
  existiu no arquivo, contando fechados e fila. Nunca reutilizado.
- Crença: `B` + 3 dígitos, mesma regra.
- Relatório: `R-AAAA-MM-DD`, com a data do dia em que foi escrito; o arquivo é
  `reports/AAAA-MM-DD.yaml`. Um segundo relatório no mesmo dia é
  `R-AAAA-MM-DD-2` em `reports/AAAA-MM-DD-2.yaml`.
- Ciclo: `number` sequencial, arquivo `cycles/NNN.yaml` com três dígitos.
- Achado não tem id próprio: é citado pelo id do relatório em que está (em
  `justification.ref` de uma mudança de prompt, por exemplo).

## `exploration.yaml`

O único arquivo que a rodada diária lê. A ordem da lista é a prioridade: a vaga
de exploração do dia vai para o primeiro aberto que tiver uma história
adequada.

```yaml
cycle: 1
share: 0.25
share_since: 2026-10-02      # muda sempre que share muda
min_fit: 70
experiments:
  - id: E001
    status: open             # open | closed | backlog
    kind: challenge          # unexplored | variation | challenge
    question: "Histórias com desconhecidos ou empresas funcionam quando o narrador reage?"
    motivation: "0 de 10 acima de 1,5×, mas nenhuma das 10 tinha reação do narrador."
    belief: B006             # obrigatório em challenge
    looks_like: "Conflito com um desconhecido, loja ou empresa em que o narrador faz algo a respeito."
    sample_target: 10
    decision_rule: "Confirma a crença se o relativo mediano ficar abaixo de 0,8; refuta se ficar acima de 1,2."
    opened: {cycle: 1, date: 2026-10-02}
    replaces: null
    outcome: null
  - id: E002
    status: backlog          # só question e motivation são obrigatórios
    question: "Títulos em forma de pergunta trazem mais comentários?"
    motivation: "Histórias em que o narrador é culpado têm mais comentários."
```

`looks_like` vai, como dado, para o prompt que dá a nota de exploração a cada
história: escreva-o como a descrição que permite reconhecer uma história que
testa a pergunta, não como uma lista de palavras-chave.

Fechar um experimento: `status: closed` e `outcome`:

```yaml
    outcome:
      verdict: refuted       # confirmed | refuted | inconclusive | closed_without_verdict | not_testable
      date: 2026-11-04
      cycle: 2
      videos: [341, 344, 350, 356, 360, 371, 377, 380, 388, 391]
      settled_count: 10
      median_relative: 1.3
      note: "Com reação do narrador, desconhecidos foram tão bem quanto o resto."
```

Mudar a redação de um experimento aberto é fechar o antigo com
`closed_without_verdict` e abrir um novo com `replaces: <id antigo>`: os
vídeos feitos para uma pergunta nunca são contados para outra.

## `beliefs.yaml`

```yaml
beliefs:
  - id: B001
    statement: "Histórias de trabalho em que o narrador dá o troco vão muito melhor que as vizinhas."
    area: story_kind         # story_kind | title_opening | posting | other
    status: lead             # base | does_not_work | lead | contested | retired
    evidence:
      videos: 7
      median_relative: 5.6
      period: {since: 2026-08-29, until: 2026-09-28}
    confidence: low          # low | medium | high
    entered: {cycle: 1, date: 2026-09-29}
    last_tested: 2026-09-29
    history:
      - date: 2026-09-29
        cycle: 1
        event: entered       # entered | confirmed | weakened | overturned | retired | kept_against_evidence
        source: video-performance-report-2026-09
        note: "3 dos 4 maiores vídeos do mês."
```

Toda mudança de `status`, de `evidence` ou de `confidence` acrescenta uma
entrada em `history` com o relatório ou experimento que a causou (`source`).
`base` e `does_not_work` exigem `evidence.videos ≥ 10`.

## `cycles/NNN.yaml`

```yaml
number: 2
opened: 2026-11-04
deployed: null               # preenchido depois do just deploy
closed: null
prompts:                     # fingerprints de prompts.fingerprint no dia
  story: 42072ca8893c
  evaluate_story: 1d2e3f4a5b6c
  generate_hashtags: 620d6983865b
  evaluate_exploration: null
settings: {writer_model: openrouter/moonshotai/kimi-k2.6, grader_model: openrouter/deepseek/deepseek-v4-flash, rendering_strategy: narration-over-footage}
changes:                     # as mudanças que abriram este ciclo
  - prompt: evaluate_story
    before: "trecho exato como estava"
    after: "trecho exato como ficou"
    justification: {kind: finding, ref: R-2026-11-04, summary: "Títulos que prometem reação: 2,4× em 14 vídeos."}
    decision: approved       # approved | modified | rejected
    reason: ""               # obrigatório em rejected
    reverts: null            # número do ciclo cuja mudança esta desfaz
experiment_changes:
  - {date: 2026-11-04, report: R-2026-11-04, action: opened, experiment: E003, note: ""}
outside_changes:
  - {detected: 2026-11-10, prompt: story, from: 42072ca8893c, to: 9a8b7c6d5e4f, reason: "Correção de ortografia pedida pelo operador."}
evaluation: null
reports: [R-2026-11-10]
closing: null
```

Ao fechar, o ciclo recebe:

```yaml
closed: 2026-11-04
evaluation:
  result: helped             # helped | hurt | unclear | not_evaluated
  base_videos: 24
  median_relative: 1.2
  previous_median_relative: 1.0
  note: "Mudança de modelo no meio: efeito não atribuível só ao prompt."
closing: {recommendation: close, decision: close, note: ""}
```

`experiment_changes.action` usa os verbos `opened`, `closed`, `reordered`,
`share_changed`, `min_fit_changed`, `moved_to_backlog`, `discarded`.

Os fingerprints saem de:

```bash
uv run python -c "from src.entities.tuning import PROMPT_FILES; from src.prompts.loader import PROMPTS_DIR, fingerprints; print(fingerprints(PROMPT_FILES, PROMPTS_DIR))"
```

e os `settings`, na forma que a receita de cada vídeo grava (é contra ela que
`also_changed` compara), de:

```bash
uv run python -c "from src.entities.config import MainConfig; from src.core.recipe import build_production_recipe; r = build_production_recipe(MainConfig.from_yaml('config.prod.yaml')); print(r.writer_model, r.grader_model, r.rendering_strategy)"
```

## `reports/AAAA-MM-DD.yaml`

```yaml
id: R-2026-10-06
cycle: 1
period: {since: 2026-09-06, until: 2026-10-06}
data_as_of: 2026-10-05T23:10:00
videos:
  considered: 71
  excluded: {unsettled: 9, no_snapshot: 3, ambiguous: 0}   # ambiguous = ambiguous_goal do pacote
weekly_reach:                # channel.weekly do pacote, copiado como está
  - {week: 2026-09-07, videos: 19, median_views: 930}
  - {week: 2026-09-14, videos: 22, median_views: 602}
distortions:
  - kind: reach_falling      # reach_falling | failed_uploads | unsettled | several_changes | outside_change
    note: "Mediana semanal caiu de 1 065 para 430."
    affects: "comparações entre semanas; os achados usam o relativo, que desconta a queda"
findings:
  - statement: "Histórias de trabalho em que o narrador dá o troco vão melhor que as vizinhas."
    area: story_kind
    direction: works         # works | does_not | inconclusive
    videos: [322, 330, 341, 347, 352, 359, 364, 371, 380, 388, 395]
    median_relative: 3.9
    confidence: medium
    is_lead: false           # true com menos de 10 vídeos
    belief: B001
    unchanged_since: null    # id do relatório anterior quando os vídeos são os mesmos
cycle_state:
  share_intended: 0.25
  share_achieved: 0.0
  unfilled_slots: null       # null até as vagas existirem na rodada
  base_median_relative: 1.07
  experiments:
    - {id: E001, settled: 2, target: 10, median_relative: 0.7, days_to_target: 19}
since_previous: {previous: R-2026-09-30, new_videos: 12, changed_findings: ["Sogros passou de 7 para 9 vídeos, ainda pista."]}
suggestions:
  - {question: "…", kind: challenge, motivation: "…", decision: backlog}   # opened | backlog | discarded
recommendation:
  action: keep               # keep | close
  reasons: ["O ciclo 1 tem 0 vídeos de base assentados; não há o que comparar ainda."]
decision: {action: keep, note: ""}
corrects: null
view_url: https://claude.ai/code/artifact/…
```

Tudo o que a visão de leitura mostra precisa estar aqui ou em outro arquivo de
`tuning/`: a página é descartável.

## `story_labels.csv`

```csv
record_id,kind,narrator_acts,title_promise,labelled_at,note
335,strangers,fought_back,reaction,2026-10-06,
364,work,fought_back,reaction,2026-10-06,
405,grief,no_reaction,situation,2026-10-06,"sem vilão"
```

Uma linha por vídeo; reclassificar é acrescentar uma linha com `labelled_at`
mais recente, e a mais recente vale. O rótulo é gravado para que dois
relatórios agrupem o mesmo vídeo do mesmo jeito: um achado só muda quando um
dado muda, nunca porque a classificação oscilou (FR-015).

### Categorias

Vêm do relatório de setembro (Video Performance Report, 84 vídeos). Classifique
pelo título e pelo resumo do pacote; quando o resumo vier vazio (vídeos
importados), o título basta, porque é o que a audiência viu.

**`kind`** — com quem é o conflito, o que decide o tipo de relação em jogo:

| Valor | Quando |
|---|---|
| `work` | chefe, colega, empresa em que o narrador trabalha, cliente do narrador |
| `in_laws` | sogro, sogra, cunhados, família do cônjuge ou da noiva |
| `own_family` | pais, irmãos, filhos, parentes do próprio narrador |
| `partner` | namorado, namorada, marido, esposa, ex |
| `friends` | amigos, colegas de quarto |
| `strangers` | desconhecidos, vizinhos, lojas, empresas de que o narrador é cliente, instituições |
| `grief` | luto, trauma, ansiedade, doença: sem vilão nem virada |

Quando a história tem mais de um antagonista, vale o que o título põe no
centro, porque é ele que decide se alguém para para assistir.

**`narrator_acts`** — o que o narrador faz na história:

| Valor | Quando |
|---|---|
| `fought_back` | reage, dá o troco, vence, expõe |
| `blamed` | acaba culpado ou tratado como vilão por outros |
| `no_reaction` | sofre ou relata, sem virada da parte dele |

**`title_promise`** — o que o título promete a quem ainda não assistiu:

| Valor | Quando |
|---|---|
| `reaction` | promete a reação ou a virada do narrador ("Só esqueceram que…", "e eu finalmente revidei") |
| `blame` | promete que o narrador vai ser culpado, ou pergunta quem está errado |
| `situation` | só descreve o que aconteceu |

Comprimento do título, dia de postagem e tempo assistido não são rótulos: vêm
das próprias linhas do pacote e são agrupados por `scripts/group.py`.

### Categoria nova

Quando um vídeo não cabe em nenhuma categoria sem forçar, crie uma (nome curto
em inglês, `snake_case`), use-a e registre no relatório em que ela aparece,
em `distortions` com `kind: new_label` e a definição em `note`. Depois
acrescente-a a esta tabela. Reclassificar vídeos antigos com a categoria nova é
acrescentar linhas novas, e o relatório diz quantos mudaram, porque os
achados que dependem deles mudam sem vídeo novo.
