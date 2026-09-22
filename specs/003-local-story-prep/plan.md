# Implementation Plan: Preparação local de histórias e hand-off para o servidor

**Branch**: `main` (sem branch dedicada criada; diretório da feature: `003-local-story-prep`) | **Date**: 2026-09-21 (M4 acrescentado em 2026-09-22) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-local-story-prep/spec.md`

## Summary

Permitir que o operador faça a parte criativa do pipeline diário na própria máquina,
com o assistente interativo da sua assinatura (Claude Code), e entregue ao servidor
um **pacote de história preparada** que o job diário consome sem chamar os modelos
de avaliação e de roteiro. Com a fila vazia, o servidor se comporta exatamente como
hoje.

A costura já existe: `PreparedStory` em `src/services/reddit_video_service.py` é o
ponto do pipeline a partir do qual não há mais chamadas de LLM. A feature serializa
esse ponto num arquivo (`PreparedStoryPackage`), cria um CLI local
(`scripts/prepare_story.py`) para descobrir candidatas, renderizar o prompt editorial
do servidor, validar o pacote, gerar a prévia de áudio e enviar para a fila, um skill
do Claude Code (`.claude/skills/prepare-story/`) que conduz o operador por esse fluxo,
e, no servidor, uma `PreparedStoryQueue` que o job diário consulta antes da descoberta.

Entrega em três milestones, na ordem pedida pelo usuário: local primeiro (descoberta,
roteiro, validação, skill), depois prévia de áudio e envio, e por último o consumo no
servidor, que só será verificável em três dias.

Um quarto milestone, acrescentado depois que os três primeiros fecharam, dá ao operador
a escolha de preparar uma história em **duas partes** (US6): posts longos viravam
narrações de oito minutos, e o pipeline de duas partes que já existe no serviço não
era usado por nenhum bot. O pacote ganha uma segunda forma (`version: 2`, com
`part1_text` e `part2_text`), o CLI renderiza o prompt de duas partes do servidor e
gera uma prévia por parte, e o job diário produz os dois vídeos com o mesmo método do
vídeo único e agenda a parte 2 no slot seguinte ao da parte 1. A descoberta
automática continua produzindo só vídeos únicos.

## Technical Context

**Language/Version**: Python 3.11+ (venv atual: 3.12)

**Primary Dependencies**: pydantic (entidade do pacote e validação),
dependency-injector (`src/core/container.py`, reuso de `reddit_proxy`,
`speech_service`, `text_censor`, `story_finder_service`), jinja2 (render do prompt
editorial já existente em `src/proxies/prompts/story.jinja2`), edge-tts (prévia de
áudio, já usado em produção), `ssh`/`scp` do sistema (transporte, via `subprocess`),
python-telegram-bot (job diário existente em `bots/satisfying_bot.py`)

**Storage**: sistema de arquivos. Local: `output/prepared/` (já ignorado pelo git via
`output/*`), com `candidates.json`, um `<post_id>.json` por pacote e
`<post_id>.preview.mp3` ao lado. Servidor: `.storage/prepared/{inbox,done,failed}/`
(já ignorado via `.storage/*` e excluído do rsync do `just deploy`, FR-015).

**Testing**: pytest (`tests/`, `asyncio_mode = auto`), no padrão de
`tests/services/test_story_finder_service.py` e `tests/test_publish_slots.py`
(bot testado com `SimpleNamespace`/monkeypatch, sem rede)

**Target Platform**: macOS (laptop do operador, fluxo local) e Linux (servidor,
consumo da fila). Ambos compartilham o mesmo repositório e o mesmo `config.yaml`.

**Project Type**: projeto único, Clean Architecture em módulos (`src/entities`,
`src/services`, `src/proxies`, `src/core`, `scripts`, `bots`)

**Performance Goals**: fluxo local do `find` ao pacote validado com áudio em menos de
15 min de relógio (SC-001); zero chamadas a modelo pago no fluxo local (SC-002); zero
chamadas de avaliação/roteiro no servidor quando a fila cobre a meta diária (SC-004)

**Constraints**: fila vazia = comportamento e logs idênticos aos atuais (FR-011,
SC-003); título e roteiro do pacote usados verbatim (SC-005, SC-008); a mesma história nunca é
publicada duas vezes pelos dois caminhos (FR-014, SC-006); as regras editoriais vêm de
uma única fonte, para um vídeo e para duas partes (FR-003, FR-017); a metade local funciona sem deploy no servidor (SC-007);
um pacote de duas partes nunca publica uma parte só (FR-023) e é recusado inteiro por um
servidor sem suporte (FR-024, SC-009)

**Scale/Scope**: 1 operador, 3 vídeos/dia, fila de poucos pacotes por vez; pacotes de
até ~15 mil caracteres de post e ~10 mil de roteiro

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Resultado |
|-----------|-----------|-----------|
| I. Fail Fast e Simplicidade | O fluxo local falha cedo em tudo: credenciais do Reddit ausentes estouram na primeira chamada; pacote inválido é recusado por `validate` e por `ship` (FR-005, FR-007); servidor inacessível aborta o envio deixando o pacote local intacto. No servidor, um pacote inválido (idioma diferente, campo faltando) é movido para `failed/` e a run segue, em vez de abortar o dia inteiro. Esse é o único desvio do default e cobre exatamente o caso "execução diária não assistida, falha custa o vídeo do dia" que a constituição admite; justificado em Complexity Tracking. | PASS |
| II. Arquitetura Limpa em Módulos | O pacote é uma entidade pydantic em `src/entities` que sabe converter-se em `PreparedStory` (regra de negócio, sem I/O). A fila é um serviço em `src/services` cuja única dependência é um diretório (detalhe na borda, injetável nos testes). O render do prompt editorial vira uma função pura reutilizada pelo `PromptLLMProxy` e pelo CLI, sem duplicar o template. Transporte (`ssh`/`scp`) e I/O de terminal ficam em `scripts/`. `RedditVideoService`, `ILLMProxy` e `IRedditProxy` não mudam de contrato. | PASS |
| III. Prompts Baseados em Racional | O skill do Claude Code explica o objetivo de cada etapa (por que ranquear assim, por que o gancho vem primeiro, por que validar antes de enviar) e delega ao assistente como aplicar; as regras editoriais em si não são reescritas, apenas apontadas para `story.jinja2` (que já segue o princípio). Sem CAPS. | PASS |
| Idioma | Plano, research, data-model, quickstart e skill em português; código, comentários, commits e nomes de arquivos em inglês. `spec.md` em inglês acompanhando o pedido do usuário, mesmo desvio documentado na feature 002. | PASS (com desvio documentado) |

**Re-check pós-design (Phase 1)**: o desenho final adiciona uma entidade, um serviço
de fila, uma função pura de render de prompt, um CLI e um skill. Nenhuma camada
interna passa a conhecer camada externa; nenhum novo desvio. PASS.

## Delivery Plan

4 milestones, ~1 PR cada (≤ 8). A ordem espelha o pedido do usuário: as duas primeiras
são inteiramente locais e verificáveis sem o servidor; a terceira só é verificável
quando o operador voltar a ter acesso. A quarta veio depois e depende das três: a
metade local (prompt, validação, prévia) é verificável no laptop, e a produção dos
dois vídeos exige o servidor, como no M3.

### M1 — Descobrir, roteirizar e validar localmente (US1 + US2 / P1) — PR 1

- `src/entities/prepared_story.py`: `PreparedStoryPackage` (pydantic) com
  `to_prepared_story()`, `post_id` derivado da URL e validação de campos
  obrigatórios e idioma.
- `src/proxies/prompts/render.py`: `render_story_prompt(title, content, language)`
  extraído de `PromptLLMProxy.generate_story` (que passa a chamá-lo). Mesma
  template, mesmo `examples=[]`.
- `src/services/story_finder_service.py`: `find_candidates(...)` (ranking
  determinístico, sem LLM, com `exclude_urls`); `find_best_stories` passa a ser
  composição `find_candidates` + avaliação, sem mudança de comportamento.
- `src/services/prepared_story_validation.py`: `validate_package(pkg, censor,
  expected_language)` retornando lista de problemas (campo faltando, roteiro vazio,
  idioma diferente, palavra proibida com o trecho ofensivo). Usa `TextCensor` como
  detector (`censor(text) != text` por token).
- `scripts/prepare_story.py` com subcomandos `find`, `show`, `prompt`, `validate`,
  `list` (ver `contracts/cli.md`). `find` grava `output/prepared/candidates.json`.
- `.claude/skills/prepare-story/SKILL.md`: conduz `find` → leitura das candidatas
  com os critérios de `evaluate_story.jinja2` → escolha → `prompt N` → JSON →
  `validate` → revisão. Termina apontando para `preview`/`ship` (M2).
- Receitas `just`: `story-find`, `story-validate file`.

**Gate de verificação M1**:
- Testes: `PreparedStoryPackage` round-trip JSON e `to_prepared_story()`; `post_id`
  estável a partir da URL; `validate_package` acusa cada classe de erro com o
  trecho; `render_story_prompt` produz byte a byte o mesmo texto que
  `PromptLLMProxy.generate_story` enviava (teste de regressão com template real);
  `find_candidates` ranqueia sem chamar `evaluate_story` e respeita
  `exclude_urls`; `find_best_stories` continua com o mesmo resultado dos testes
  existentes em `tests/services/test_story_finder_service.py`.
- Manual (quickstart §1 e §2): `just story-find` imprime a shortlist com título,
  comunidade, score, comentários, tamanho e link, sem nenhuma chamada a modelo
  (log não mostra LiteLLM); `/prepare-story` no Claude Code chega a um pacote
  validado.

### M2 — Ouvir e enviar (US3 + US4 / P2) — PR 2

- `scripts/prepare_story.py`: subcomandos `preview` (usa `container.speech_service()`
  com `rate=1.0`, gênero resolvido do pacote e idioma do pacote; grava
  `<post_id>.preview.mp3` ao lado e imprime a duração), `ship` (valida, verifica
  duplicata remota por `post_id`, pede confirmação, `ssh mkdir -p` + `scp`), `queue`
  (`ssh ls` da inbox remota com título e hora, lendo os JSONs via `ssh cat`).
- Config `bots.satisfying_bot.prepared_stories` (`remote`, `inbox_dir`,
  `fill_with_discovery`) em `src/entities/configs/bots.py` e nos `config*.yaml`.
- Receitas `just`: `story-preview file`, `story-ship file`, `story-queue`.
- Skill atualizado para fechar o loop: ouvir, revisar, enviar.

**Gate de verificação M2**:
- Testes: `preview` grava o mp3 e retorna duração (proxy de fala falso); `ship`
  recusa pacote inválido sem tocar na rede; `ship` com duplicata remota exige
  confirmação (subprocess mockado); `ship` com host inacessível deixa o arquivo
  local intacto e sai com erro; `queue` parseia a listagem.
- Manual (quickstart §3 e §4): ouvir a prévia com a voz/velocidade de produção;
  `just story-ship` contra qualquer host SSH alcançável (o servidor ou o próprio
  laptop via `localhost`) coloca o arquivo em `.storage/prepared/inbox/` (SC-007).

### M3 — O servidor consome a fila (US5 / P3) — PR 3

- `src/services/prepared_story_queue.py`: `PreparedStoryQueue(root)` com
  `list_inbox()` (FIFO por mtime, depois nome), `mark_done(pkg, outcome)`,
  `mark_failed(pkg, error)`, `known_post_urls()` (inbox + done). Cria os diretórios
  sob demanda.
- `bots/satisfying_bot.py`: `_collect_candidates()` monta a lista de trabalho:
  pacotes da fila primeiro (já como `PreparedStory`, sem `_prepare_story_with_retries`),
  depois descoberta (se faltar para a meta e `fill_with_discovery`), com
  `exclude_urls` = fila + done + `post_url` do `tiktok_publish_log.csv`. Pacote com
  `hashtags` pula `generate_hashtags`. Manifesto ganha `source: prepared|auto`.
  `run_daily_generate` e `run_daily_auto_publish` compartilham essa montagem.
  Após publicar/gerar: `mark_done`; após falha em qualquer etapa: `mark_failed`.
- Comando Telegram `/prepared` listando a fila (leve, reaproveita `list_inbox`).
- `docs/prepared-stories.md` (português): fluxo completo, `just` receitas, formato
  do pacote, o que acontece na fila.

**Gate de verificação M3**:
- Testes (padrão `tests/test_publish_slots.py`, sem rede): fila vazia → a lista de
  trabalho é exatamente a da descoberta e nenhuma função da fila é chamada além de
  `list_inbox` (SC-003); N pacotes e meta N → zero chamadas a `find_best_stories`,
  `prepare_satisfying_story` e, com hashtags, `generate_hashtags` (SC-004); N-1
  pacotes → descoberta completa 1 com `exclude_urls` contendo os N-1;
  `fill_with_discovery: false` → só os N-1; sucesso move para `done/`, falha move
  para `failed/` com erro; idioma diferente → `failed/` sem gerar vídeo; manifesto
  traz `source`.
- Manual (quickstart §5, no servidor): `just prod-daily-generate 1` com um pacote na
  inbox produz `story_01.mp4` cujo `story_01.json` tem o título do pacote e
  `source: prepared`, e o log não mostra chamadas de avaliação nem de roteiro.

### M4 — Histórias em duas partes pelo fluxo preparado (US6 / P3) — PR 4

- `src/entities/prepared_story.py`: base comum `_PackageBase`; `TwoPartStoryPackage`
  (`version: Literal[2]`, `part1_text`, `part2_text`, `to_story_script()`,
  `to_prepared_stories()`); `load_package(text)` despachando por `version` e
  falhando com `unsupported package version` fora de `{1, 2}`.
- `src/proxies/prompts/render.py`: `render_two_part_story_prompt(title, content,
  language)` extraído de `PromptLLMProxy.generate_two_part_story` (que passa a
  chamá-lo), carregando os mesmos exemplos de `examples/two_part_story.yaml`.
- `src/services/prepared_story_validation.py`: `validate_package` aceita as duas
  formas; na versão 2 checa `story_title`, `part1_text`, `part2_text` (cada problema
  nomeia o campo) e o CTA final da parte 1 por idioma (`pt-br`: `Curta e me siga para
  a parte 2.`).
- `src/services/prepared_story_queue.py`: `QueuedPackage.package` passa a ser a união
  das duas formas, lida com `load_package`; `known_post_urls` inalterado.
- `scripts/prepare_story.py`: `prompt N --two-part`; `validate`, `list`, `preview` e
  `queue` usando `load_package`; `preview` de versão 2 gera
  `<post_id>.part1.preview.mp3` e `<post_id>.part2.preview.mp3` e imprime cada duração
  e o total. Receita `story-prompt n *args`.
- `bots/satisfying_bot.py`: `_WorkItem.part2`; `_collect_candidates` monta a parte 1 e
  a parte 2 de um pacote de versão 2 (uma história na meta); `_generate_video_for_story`
  produz as duas partes com `generate_satisfying_video_from_story`, arquivos
  `story_NN.mp4` e `story_NN_p2.mp4`, manifestos com `part`, e falha o item inteiro se
  qualquer parte falhar; `_publish_one_video` é chamado para a parte 1 e depois para a
  parte 2 com `last_slot` = slot da parte 1 e as mesmas hashtags; `mark_done` só
  depois das duas, com `outcome.json` listando os dois vídeos; parte 2 falhando ao
  publicar → `mark_failed` nomeando o slot da parte 1. `GeneratedVideo.part` opcional;
  `run_daily_publish` respeita a ordem de nome dos manifestos. Mensagens do Telegram
  em `contracts/queue.md`.
- `.claude/skills/prepare-story/SKILL.md`: passo 3 apresenta a escolha do formato
  (sugerindo duas partes quando a prévia única passa de uns seis minutos ou a história
  tem um gancho natural antes do desfecho) e passo 6 ouve as duas prévias.
- `docs/prepared-stories.md`: seção sobre pacotes de duas partes.

**Gate de verificação M4**:
- Testes: `TwoPartStoryPackage` round-trip, `to_story_script()`, `to_prepared_stories()`
  com os sufixos, `load_package` despachando e recusando `version: 3`; o modelo de
  versão 1 rejeita `version: 2` (é o que garante SC-009 num servidor antigo);
  `render_two_part_story_prompt` byte a byte igual ao que `generate_two_part_story`
  envia (regressão com `litellm.acompletion` falso), exemplos inclusos;
  `validate_package` versão 2 acusa parte vazia, palavra proibida em cada parte
  nomeando o campo, idioma e CTA ausente na parte 1; CLI `prompt --two-part`,
  `validate`, `list` (`2 partes`) e `preview` (dois mp3, duas durações e total); bot:
  pacote versão 2 conta uma história na meta, gera dois vídeos e dois manifestos com
  `part`, publica em dois slots consecutivos com as mesmas hashtags e duas linhas no
  publish log, `done/` com os dois vídeos; falha na parte 2 (produção) → nenhum
  publicado e `failed/`; falha na parte 2 (publicação) → `failed/` com o slot da
  parte 1; fila vazia → nada de duas partes na descoberta (SC-003 continua).
- Manual (quickstart §6): `just story-prompt N --two-part` começa com o mesmo texto
  do template de duas partes e traz os três exemplos; pacote versão 2 validado; duas
  prévias com durações; no servidor, `just prod-daily-generate 1` com o pacote na
  inbox produz `story_01.mp4` e `story_01_p2.mp4`, covers `... - Parte 1` e `... -
  Parte 2`, sem chamada de roteiro.

**Projeção**: 4 PRs.

## Project Structure

### Documentation (this feature)

```text
specs/003-local-story-prep/
├── plan.md              # Este arquivo
├── research.md          # Phase 0 (decisões: formato, transporte, ranking sem LLM, skill)
├── data-model.md        # Phase 1 (PreparedStoryPackage, fila, config, manifesto)
├── quickstart.md        # Phase 1 (guia de validação por milestone)
├── contracts/
│   ├── prepared_story_package.md   # Esquema do pacote (JSON) e regras de validação
│   ├── cli.md                      # Subcomandos de scripts/prepare_story.py e receitas just
│   └── queue.md                    # Contrato da fila no servidor e do job diário
└── tasks.md             # Phase 2 (/speckit-tasks — não criado por /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── entities/
│   ├── prepared_story.py           # M1: NOVO — PreparedStoryPackage (+ to_prepared_story); M4: TwoPartStoryPackage, load_package
│   └── configs/bots.py             # M2: PreparedStoriesConfig em TelegramBotConfig
├── proxies/
│   ├── prompts/render.py           # M1: NOVO — render_story_prompt (função pura); M4: render_two_part_story_prompt
│   ├── prompts/story.jinja2        # INALTERADO (fonte única das regras editoriais)
│   ├── prompts/two_part_story.jinja2 # INALTERADO (fonte única das regras de duas partes)
│   ├── llm_prompt_proxy.py         # M1: generate_story usa render_story_prompt; M4: generate_two_part_story usa render_two_part_story_prompt
│   └── interfaces.py               # INALTERADO
├── services/
│   ├── story_finder_service.py     # M1: find_candidates(exclude_urls) sem LLM
│   ├── prepared_story_validation.py# M1: NOVO — validate_package; M4: versão 2 (partes + CTA)
│   ├── prepared_story_queue.py     # M3: NOVO — PreparedStoryQueue (inbox/done/failed); M4: load_package
│   ├── reddit_video_service.py     # INALTERADO (PreparedStory é o contrato)
│   └── text_censor.py              # INALTERADO (usado como detector)
└── core/container.py               # M3: provider prepared_story_queue

scripts/
└── prepare_story.py                # M1: find/show/prompt/validate/list; M2: preview/ship/queue; M4: --two-part, prévia por parte

bots/
└── satisfying_bot.py               # M3: _collect_candidates, /prepared, manifesto com source; M4: duas partes (part2, slots consecutivos)

.claude/skills/prepare-story/
└── SKILL.md                        # M1: NOVO — fluxo guiado no Claude Code; M2: fecha o loop; M4: escolha do formato

docs/
└── prepared-stories.md             # M3: NOVO — doc do operador (português); M4: seção de duas partes

tests/
├── test_prepared_story_package.py  # M1: NOVO
├── test_prepare_story_cli.py       # M1/M2: NOVO
├── test_prepared_story_queue.py    # M3: NOVO
├── test_daily_prepared_flow.py     # M3: NOVO (padrão de test_publish_slots.py); M4: casos de duas partes
├── test_render_two_part_prompt.py  # M4: NOVO (regressão contra generate_two_part_story)
└── services/test_story_finder_service.py  # M1: casos de find_candidates; existentes intactos

Justfile                            # M1/M2: story-find, story-validate, story-preview, story-ship, story-queue; M4: story-prompt aceita args
config.yaml / config.prod.yaml      # M2: bloco prepared_stories comentado com defaults
```

**Structure Decision**: projeto único existente. A regra de negócio nova (pacote,
validação, fila) entra em `src/entities` e `src/services`; o que toca sistema
externo (terminal, `ssh`/`scp`, Telegram) fica em `scripts/` e `bots/`.
`RedditVideoService` e as interfaces de proxy são invariantes da feature.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No servidor, pacote inválido vai para `failed/` e a run continua, em vez de abortar | FR-013 e edge case de idioma: a run diária é não assistida e um pacote ruim não deve custar os outros vídeos do dia; o operador vê o erro no arquivo em `failed/` e no Telegram | Abortar a run por um pacote inválido derrubaria também a descoberta automática, que é o comportamento que a feature promete preservar |
| `find_best_stories` decomposto em `find_candidates` + avaliação | FR-001/SC-002 exigem a shortlist local sem LLM; sem a decomposição o CLI duplicaria o ranking | Uma flag `skip_llm` no método existente mistura dois modos no mesmo fluxo e deixa o tipo de retorno ambíguo (`EvaluatedStory` sem avaliação) |
| `render_story_prompt` extraído do proxy | FR-003: o prompt que o assistente segue tem que ser o mesmo que o servidor envia; a extração é o que permite testar isso byte a byte | Mandar o skill "ler o `.jinja2`" deixaria o assistente interpretar a sintaxe do template e as variáveis, abrindo espaço para drift |
| `spec.md` em inglês | Pedido do usuário em inglês; rastreabilidade termo a termo | Traduzir agora só re-escreveria um artefato já validado |
| Segundo modelo de pacote (`version: 2`) em vez de campos opcionais no primeiro | FR-018/FR-024: o formato tem que ser distinguível pela versão e um servidor antigo tem que recusar o pacote inteiro antes de produzir; `Literal[1]` no modelo antigo faz isso sem código | Campos opcionais num só modelo fariam o servidor antigo aceitar o arquivo e falhar só na geração, depois de gastar tempo e com um erro pior |
| Duas partes produzidas com dois `PreparedStory` e o método de vídeo único, não com `compose_two_part_video` | FR-021 exige paridade com o vídeo único (censura de legendas, `cta_start`, fundo); o método existente de duas partes não faz nada disso e não tem consumidor | Um método novo de duas partes no serviço duplicaria a etapa de produção e teria que ser mantido em sincronia com a de vídeo único |
