# Tasks: Preparação local de histórias e hand-off para o servidor

**Input**: Design documents from `/specs/003-local-story-prep/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Incluídos — os gates de verificação do plan.md exigem testes por milestone e
o projeto tem suíte pytest estabelecida (`asyncio_mode = auto`). Escrever os testes de
cada story primeiro e vê-los falhar antes de implementar.

**Organization**: 4 milestones = 4 PRs (ver Delivery Plan). M1 cobre US1+US2 (um PR,
porque o skill que fecha US2 depende do `find` de US1 e ambos são a metade local que o
usuário quer primeiro); M2 cobre US3+US4; M3 cobre US5 e só é verificável no servidor;
M4 cobre US6 (duas partes), acrescentado em 2026-09-22 depois de M3 fechar, e sua
metade de servidor só é verificável lá, como M3. Tarefas dentro de um milestone são
commits do mesmo PR, nunca PRs separados.

## Format: `[ID] [P?] [Story] Description`

## Delivery Plan

| PR | Milestone | Stories | Conteúdo |
|----|-----------|---------|----------|
| 1 | M1 — Descobrir, roteirizar e validar localmente | US1, US2 | `find_candidates`, `render_story_prompt`, `PreparedStoryPackage`, `validate_package`, CLI `find/show/prompt/validate/list`, receitas `just`, skill `/prepare-story`, testes |
| 2 | M2 — Ouvir e enviar | US3, US4 | `PreparedStoriesConfig`, CLI `preview/ship/queue`, receitas `just`, skill fechando o loop, testes |
| 3 | M3 — O servidor consome a fila | US5 | `PreparedStoryQueue`, `_collect_candidates` no bot, dedup com publish log, `/prepared`, manifesto com `source`, doc do operador, testes |
| 4 | M4 — Histórias em duas partes pelo fluxo preparado | US6 | `TwoPartStoryPackage` + `load_package`, `render_two_part_story_prompt`, validação por parte, CLI `prompt --two-part`/`preview` por parte, bot produzindo dois vídeos e agendando em slots consecutivos, skill com a escolha do formato, doc, testes |

Projeção: **4 PRs** (≤ 8, ok).

---

## Phase 1: Setup

**Purpose**: confirmar a linha de base antes de mexer — a feature não cria projeto novo.

- [X] T001 Rodar `uv sync --extra dev && uv run pytest -q` e registrar a linha de base (a falha pré-existente em `tests/test_translation_pipeline.py::test_pipeline` é conhecida desde a feature 002 e não bloqueia; qualquer outra falha nova, parar e reportar)

---

## Phase 2: Foundational

**Purpose**: a única peça compartilhada por todos os milestones é a entidade do pacote;
ela nasce aqui porque US2 (M1) a escreve, US3/US4 (M2) a leem e US5 (M3) a consome.

- [X] T002 [P] Testes de `PreparedStoryPackage` em tests/test_prepared_story_package.py: round-trip `model_validate_json` → `model_dump_json`; `post_id` extraído de `post.url` (`/comments/<id>/`) e erro claro para URL sem id; `language` aceita `pt-br` e serializa de volta; `to_prepared_story()` mapeia 1:1 para `PreparedStory` (inclusive `original_post_md` igual ao que `prepare_satisfying_story` monta); chaves extras ignoradas; `version` ≠ 1 rejeitada; `story_title`/`script_text` vazios rejeitados
- [X] T003 Criar `PreparedStoryPackage` em src/entities/prepared_story.py conforme data-model.md (campos, `version: Literal[1]`, `source`, `language: Language`, `created_at`, `post: RedditPost`, `story_title`, `script_text`, `narrator_gender`, `resolved_gender`, `summary`, `hashtags: list[str] | None`; `model_config = ConfigDict(extra="ignore")`; propriedades `post_id` e `original_post_md`; método `to_prepared_story()`; função `extract_post_id(url)` reutilizável)

**Checkpoint**: [X] T002 verde — M1 pode começar.

---

## Phase 3: Milestone 1 — Descobrir, roteirizar e validar localmente (US1 + US2 / P1) 🎯 MVP

**Goal**: o operador roda `just story-find`, escolhe uma história com o assistente,
recebe o prompt editorial exato do servidor, escreve o pacote e o valida, tudo sem
nenhuma chamada a modelo pago.

**Independent test criteria** (antes de implementar):

- `just story-find` imprime a shortlist (rank, score, comunidade, pontos, comentários,
  chars, título, URL), grava `output/prepared/candidates.json` e o log não contém
  `LiteLLM` nem `Evaluating`.
- `just story-show N` imprime o texto original completo do candidato N.
- `just story-prompt N` produz byte a byte o mesmo texto que
  `PromptLLMProxy.generate_story` envia para o mesmo post e idioma.
- `just story-validate` acusa campo faltando, roteiro vazio, idioma diferente e cada
  palavra proibida com contexto; exit 1; pacote bom → `✓`, exit 0.
- `/prepare-story` no Claude Code chega a um pacote validado em
  `output/prepared/<post_id>.json` sem que o assistente escolha a história, aprove o
  roteiro ou envie sozinho.
- `tests/services/test_story_finder_service.py` existente passa sem alteração.

### Testes (escrever primeiro, ver falhar)

- [X] T004 [P] [US1] Testes de `find_candidates` em tests/services/test_story_finder_service.py: retorna `list[StoryCandidate]` ordenada por `deterministic_score` desc, respeita `top_per_sub`, nunca chama `evaluate_story` no proxy fake, `exclude_urls` remove candidatos por `post.url` antes do corte por sub, subreddit com falha é pulado com log e os demais entram; `find_best_stories` continua com o mesmo resultado dos testes já existentes no arquivo
- [X] T005 [P] [US2] Teste de regressão de `render_story_prompt` em tests/test_prepared_story_package.py (seção própria) ou tests/test_render_story_prompt.py: para um post fixo e `Language.PORTUGUESE`, a string devolvida é igual à que `PromptLLMProxy.generate_story` monta (capturar via `litellm.acompletion` monkeypatched que devolve o `messages[0]["content"]`), e começa com `You are an expert TikTok scriptwriter.`
- [X] T006 [P] [US2] Testes de `validate_package` em tests/test_prepared_story_package.py: pacote válido → lista vazia; `language` ≠ esperado → `language: package=en server=pt-br`; `script_text` com `matou` → `script_text: 'matou' em "...contexto..."`; `story_title` com `sangue` → item para `story_title`; `extra_word_replacements` da config também detectados; `resolved_gender` incoerente com `narrator_gender` male/female → item
- [X] T007 [P] [US1] Testes do CLI em tests/test_prepare_story_cli.py: `find` com `StoryFinderService` fake grava `candidates.json` com `rank` 1-based, `generated_at`, `sort`, `time_filter`, `subreddits` e exclui URLs de pacotes já presentes em `--out`; `show N` imprime título e conteúdo; `prompt N` imprime o render; `validate` retorna exit 1 com a lista de problemas e exit 0 com `✓`; `list` mostra título, `post_id`, `created_at` e se existe `<post_id>.preview.mp3`

### Implementação

- [X] T008 [US1] Extrair `find_candidates(sort, time_filter, posts_per_sub, top_per_sub, subreddits, exclude_urls) -> list[StoryCandidate]` de `find_best_stories` em src/services/story_finder_service.py (laço de fetch + `score_candidates` + corte por sub + erro quando nenhum sub respondeu), e reescrever `find_best_stories` como `find_candidates` + laço de `evaluate_story` + corte por veredito, sem mudar mensagens de log nem resultado
- [X] T009 [P] [US2] Criar `render_story_prompt(title, content, language) -> str` em src/proxies/prompts/render.py (mesmo `FileSystemLoader` do diretório de prompts, `story.jinja2`, `examples=[]`, `get_language_name`) e fazer `PromptLLMProxy.generate_story` em src/proxies/llm_prompt_proxy.py chamá-la no lugar do render inline
- [X] T010 [P] [US2] Criar `validate_package(pkg, censor, expected_language) -> list[str]` em src/services/prepared_story_validation.py: tokeniza `story_title` e `script_text` por palavra (`\w+`, unicode), acusa toda palavra em que `censor.censor(word) != word` com 40 chars de contexto de cada lado, checa idioma e coerência de gênero; formato das mensagens conforme contracts/prepared_story_package.md
- [X] T011 [US1] Criar scripts/prepare_story.py com `argparse` de subcomandos e implementar `find` (usa `container.story_finder_service().find_candidates`, `config.evaluation.subreddits` por padrão, `--sort/--time/--per-sub/--top-per-sub/--sub/--out`, grava `candidates.json` conforme data-model.md, imprime a tabela do contracts/cli.md), `show N` e `list` (lê `<out>/*.json` como `PreparedStoryPackage`, ignora `candidates.json`)
- [X] T012 [US2] Implementar em scripts/prepare_story.py os subcomandos `prompt N` (lê `candidates.json`, chama `render_story_prompt` com `--language` default `config.language`, imprime em stdout) e `validate FILE...` (carrega `PreparedStoryPackage`, chama `validate_package` com `container.text_censor()` e `config.language`, saída `✓ file` / `✗ file` + itens, exit 1 se algum falhar)
- [X] T013 [P] [US1] Adicionar receitas `story-find *args`, `story-show n`, `story-prompt n`, `story-validate file` no Justfile (seção nova "Prepared stories", comentário explicando que nenhuma receita chama LLM)
- [X] T014 [US2] Criar o skill em .claude/skills/prepare-story/SKILL.md (frontmatter `name: prepare-story`, `description` em português dizendo quando usar): explicar o objetivo (usar o assistente da assinatura no lugar do modelo pago, sem que o servidor mude), os passos 1 a 5 do contracts/cli.md com os comandos `just` exatos, a lente de `src/proxies/prompts/evaluate_story.jinja2` para propor 3 a 5 candidatas com uma linha de justificativa, o formato do pacote apontando para specs/003-local-story-prep/contracts/prepared_story_package.md (incluir `summary` de 3 a 5 frases e `hashtags` sem `#`), a regra de manter o arquivo anterior até o operador aprovar a revisão, e o que o assistente nunca decide sozinho (história, aprovação, envio); aceitar uma URL do Reddit como argumento para pular a descoberta (usar `container.reddit_proxy().get_reddit_post` via um subcomando `show --url`); redigir no espírito do princípio III da constituição (racional, sem CAPS, sem regras casuísticas); terminar dizendo que `preview` e `ship` chegam no M2
- [X] T015 [US2] Adicionar `show --url URL` em scripts/prepare_story.py (busca o post pelo proxy e o anexa a `candidates.json` como rank seguinte, para que `prompt N` funcione com posts vindos de URL) e cobrir em tests/test_prepare_story_cli.py

### Live verification (milestone gate)

- [X] T016 [US1] Rodar `uv run pytest tests/test_prepared_story_package.py tests/test_prepare_story_cli.py tests/services/test_story_finder_service.py -q` (tudo verde) e o quickstart.md §1 e §2 de verdade: `just story-find` contra o Reddit com o `.env` local, `just story-show 1`, `just story-prompt 1 | head -5`, `/prepare-story` no Claude Code até `✓` no `validate`, e o teste de `matou` → `✗`; registrar a evidência aqui

  **Evidência (2026-09-22)**

  - Baseline antes de mexer: `uv run pytest -q` → `1 failed, 189 passed`; a única
    falha é a conhecida `tests/test_translation_pipeline.py::test_pipeline`
    (`PromptLLMProxy` não tem `translate_and_adapt`), herdada da feature 002.
  - `uv run pytest tests/test_prepared_story_package.py tests/test_prepare_story_cli.py
    tests/services/test_story_finder_service.py tests/test_render_story_prompt.py -q`
    → **51 passed**. Suíte inteira depois do milestone: `1 failed, 239 passed`
    (mesma falha pré-existente; 50 testes novos, nenhuma regressão).
  - `just story-find --top-per-sub 2` contra o Reddit real com o `.env` local:
    19 candidatas em 11 comunidades, tabela com rank, `det=`, comunidade, pontos,
    ratio, comentários, chars, título e URL; `output/prepared/candidates.json`
    gravado com `generated_at`, `sort`, `time_filter`, `subreddits` e `rank` 1-based.
    `grep -ciE "litellm|evaluating"` no log → **0** (SC-002 verificado no fluxo real).
  - `just story-show 1` imprimiu o texto original completo do candidato #1
    (r/AmItheAsshole, 2999 chars).
  - `just story-prompt 1 | head -5` começa com `You are an expert TikTok scriptwriter.`.
    A igualdade byte a byte com `PromptLLMProxy.generate_story` é coberta por
    `tests/test_render_story_prompt.py::test_render_matches_the_prompt_the_proxy_sends`,
    que captura o `messages[0]["content"]` com `litellm.acompletion` monkeypatched.
  - Fluxo do `/prepare-story` executado até o fim sobre o candidato #1: pacote escrito
    em `output/prepared/1wmh90e.json` e `just story-validate` → `✓ 1wmh90e.json`,
    exit 0. Com `matou` injetado no roteiro → `✗` com
    `script_text: 'matou' em "... com o clima. Quase me matou de raiva. ..."`, exit 1;
    desfeita a edição, volta a `✓`. Um pacote com `language: en` e
    `resolved_gender` incoerente lista os três problemas de uma vez, exit 1.
  - `just story-list` → `1wmh90e  2026-09-22T09:29:48  [sem mp3]  <título>`.
  - `just story-find --sub r/AmItheAsshole` depois do pacote pronto: o post `1wmh90e`
    não reaparece na shortlist (exclusão por `exclude_urls` verificada no fluxo real).
  - `just story-show --url <url do Reddit>` anexou o post como rank 4 em
    `candidates.json` e `just story-prompt 4` renderizou o prompt desse post.
  - Passo do skill que **não** foi verificado sozinho, por desenho: a escolha da
    história e a aprovação do roteiro são do operador (o skill proíbe o assistente de
    decidir isso). O que foi exercido aqui é todo o caminho mecânico em volta delas.
  - Desvio registrado: o contrato exemplifica a mensagem de idioma como
    `server=pt-br`, mas `Language.PORTUGUESE.value` é `pt`, e a string bruta do
    `config.yaml` já se perdeu quando a validação roda. A mensagem usa `.value` dos
    dois lados (`language: package=en server=pt`), que é simétrica e sempre exata.
    `pt` e `pt-br` são o mesmo idioma para o sistema, então a distinção não
    acrescentaria informação ao operador.

**Checkpoint**: [X] Milestone 1 DONE (2026-09-22) — a metade criativa roda inteira no laptop sem API paga.

---

## Phase 4: Milestone 2 — Ouvir e enviar (US3 + US4 / P2)

**Goal**: o operador ouve a narração com a voz e velocidade de produção antes de
enviar, e um comando coloca o pacote validado na fila do servidor (ou de qualquer
host SSH, para testar sem o servidor).

**Independent test criteria** (antes de implementar):

- `just story-preview FILE` grava `<post_id>.preview.mp3` ao lado, imprime a duração
  `mm:ss`, usa `resolved_gender` e `language` do pacote e `rate=1.0` (o
  `default_rate` da config faz o resto); rodar de novo após editar o roteiro substitui
  o mp3.
- `ship` recusa pacote inválido sem executar `ssh`/`scp`; com host inacessível sai
  com exit 2 e o arquivo local continua igual; duplicata remota pergunta `y/N` e
  `--force` pula.
- `queue` lista `post_id`, título, URL, `created_at` e mtime remoto.
- Quickstart §4 funciona com `--remote "$USER@localhost:$PWD/.storage/prepared"`.

### Testes (escrever primeiro, ver falhar)

- [X] T017 [P] [US3] Testes de `preview` em tests/test_prepare_story_cli.py: com `SpeechService` fake que devolve bytes de um mp3 de fixture curto, o arquivo `<post_id>.preview.mp3` é gravado ao lado do pacote, a chamada recebe `gender=resolved_gender`, `rate=1.0`, `language=pkg.language`, e a saída contém a duração; segunda chamada sobrescreve
- [X] T018 [P] [US4] Testes de `ship` e `queue` em tests/test_prepare_story_cli.py com `subprocess.run` monkeypatched: pacote inválido → exit 1 e nenhuma chamada a subprocess; sequência `ssh mkdir -p`, `ssh test -e`, `scp` com os argumentos do contracts/cli.md; `test -e` retornando 0 sem `--force` → pergunta e aborta em `N`; `--force` pula a pergunta; `scp` falhando → exit 2, mensagem com stderr, arquivo local intacto; `queue` parseia a saída concatenada dos JSONs remotos numa tabela
- [X] T019 [P] [US4] Teste de config em tests/test_prepared_story_package.py: `TelegramBotConfig` sem bloco `prepared_stories` carrega com defaults (`remote` = `gustavo@192.168.1.100:~/video-generator/.storage/prepared`, `inbox_dir` = `.storage/prepared`, `fill_with_discovery` = `True`)

### Implementação

- [X] T020 [US4] Adicionar `PreparedStoriesConfig` (`remote`, `inbox_dir`, `fill_with_discovery`) e o campo `prepared_stories` em `TelegramBotConfig`, em src/entities/configs/bots.py
- [X] T021 [P] [US4] Adicionar o bloco `prepared_stories` comentado (defaults e propósito de cada campo) sob `bots.satisfying_bot` em config.yaml e config.prod.yaml, e uma tabela dos campos em docs/configuration.md
- [X] T022 [US3] Implementar `preview FILE [--rate]` em scripts/prepare_story.py: `container.speech_service().generate_speech(text=pkg.script_text, gender=pkg.resolved_gender, rate=args.rate, language=pkg.language)`, grava `<post_id>.preview.mp3`, duração via `AudioClip(bytes=...).clip.duration` formatada `mm:ss`
- [X] T023 [US4] Implementar `ship FILE... [--remote] [--force]` em scripts/prepare_story.py: valida como `validate`; parse de `user@host:dir`; `subprocess.run(["ssh", host, f"mkdir -p {dir}/inbox"])`, `["ssh", host, f"test -e {dir}/inbox/{post_id}.json"]` (0 → duplicata → `input("já existe na fila, substituir? [y/N] ")` salvo `--force`), `["scp", file, f"{host}:{dir}/inbox/"]`; exit 2 com o comando e o stderr em qualquer falha; nunca move nem altera o arquivo local
- [X] T024 [US4] Implementar `queue [--remote]` em scripts/prepare_story.py: `ssh host 'for f in dir/inbox/*.json; do stat -c "%Y" "$f" 2>/dev/null || stat -f "%m" "$f"; cat "$f"; echo; done'` (aceitar as duas variantes de `stat`, Linux e macOS), parsear cada bloco como `PreparedStoryPackage`, imprimir tabela `post_id`, título (60 chars), URL, `created_at`, mtime; `Fila vazia.` quando não há arquivos
- [X] T025 [P] [US3] Adicionar receitas `story-preview file` (com `CONFIG_PATH=config.prod.yaml`), `story-ship file`, `story-queue` no Justfile
- [X] T026 [US4] Atualizar .claude/skills/prepare-story/SKILL.md com os passos 6 e 7 do contracts/cli.md (ouvir com `just story-preview`, voltar à revisão se o operador pedir, enviar com `just story-ship` só com confirmação explícita, mostrar `just story-queue` ao final) e remover a nota "chega no M2"

### Live verification (milestone gate)

- [X] T027 [US3] Rodar `uv run pytest tests/test_prepare_story_cli.py tests/test_prepared_story_package.py -q` (verde) e o quickstart.md §3 e §4: ouvir a prévia de um pacote real com `config.prod.yaml` (voz do gênero certo, 1.5x), editar e re-gerar; `ship` contra `localhost` cria `.storage/prepared/inbox/<post_id>.json`, reenvio pergunta, `--force` substitui, `queue` lista; `ship` de um JSON inválido é recusado sem rede; registrar a evidência aqui. Quando o servidor voltar a estar acessível, repetir `just story-ship` e `just story-queue` sem `--remote` (SC-007)

  **Evidência (2026-09-22)**

  - `uv run pytest tests/test_prepare_story_cli.py tests/test_prepared_story_package.py -q`
    → **58 passed** (18 novos). Suíte inteira: `1 failed, 257 passed` — a única falha
    continua sendo a conhecida `tests/test_translation_pipeline.py::test_pipeline`,
    herdada da feature 002.
  - §3, prévia real com `config.prod.yaml` sobre o pacote `1wmh90e` do M1:
    `just story-preview output/prepared/1wmh90e.json` →
    `Narrando 3334 chars (voz male, pt, rate=1.0)` e
    `output/prepared/1wmh90e.preview.mp3  02:33` (153,0 s medidos com `AudioClip`).
    O `rate=1.0` impresso é o do chamador; o `default_rate: 1.5` da config é que dá a
    velocidade final, como o comentário em `config.prod.yaml` avisa.
  - Override de velocidade e sobrescrita: `--rate 1.5` (efetivo 2.25x) → `01:55`, e o
    md5 do mp3 mudou (`e73b28f…` → `50c54c4…`), ou seja o arquivo é substituído e não
    acumulado. Rodado de novo sem `--rate`, volta a `02:33`.
  - Gênero e edição do roteiro: cópia do pacote com `resolved_gender: female` e o
    roteiro cortado para 314 chars → `Narrando 314 chars (voz female, pt, ...)` e
    `00:13`. O gênero e o idioma do pacote chegam ao TTS.
  - §4, recusa sem rede: `ship` de um pacote com `language: en` e `matou` no roteiro →
    lista os dois problemas, exit 1, **nenhum** processo `ssh`/`scp` disparado.
  - §4, host inacessível: `ship … --remote "$USER@localhost:$PWD/.storage/prepared"` →
    `Falhou: ssh … mkdir -p …` + `ssh: connect to host localhost port 22: Connection
    refused`, exit 2, md5 do arquivo local inalterado e `.storage/prepared` nem criado.
  - §4, caminho feliz, duplicata e `--force`: exercidos de ponta a ponta com shims de
    `ssh`/`scp` no PATH (o shim de `ssh` executa o comando remoto no shell local, o de
    `scp` copia o arquivo), porque nenhum host SSH estava acessível — ver o desvio
    abaixo. `queue` numa raiz inexistente → `Fila vazia.`, exit 0; `ship` → cria
    `inbox/` e grava `inbox/1wmh90e.json`; `queue` → `post_id`, título cortado em 60
    chars, URL, `criado` e `enfileirado` (o fallback `stat -f "%m"` do macOS foi o que
    respondeu, já que `stat -c` não existe aqui); reenvio →
    `1wmh90e.json já existe na fila, substituir? [y/N]`, `n` aborta com exit 1 e sem
    `scp`, `y` copia; `--force` com stdin fechado copia sem perguntar. Com dois pacotes
    na inbox, `queue` lista os dois.
  - Remote default vindo da config: `just story-queue` (sem `--remote`, `ssh` real) →
    `Falhou: ssh gustavo@192.168.1.100 …` + `Operation timed out`, exit 2. O host e o
    diretório saem de `bots.satisfying_bot.prepared_stories.remote`.
  - **Não verificado** (desvio registrado): o `ship`/`queue` sobre um SSH de verdade.
    O servidor de produção está fora do ar (`192.168.1.100` dá timeout) e o Remote
    Login deste Mac está desligado, então o destino `$USER@localhost` do quickstart §4
    também não responde; ligar o Remote Login é uma configuração de segurança da
    máquina do operador, não algo a mudar por conta própria. O que os shims não cobrem
    é a interoperabilidade com o `ssh`/`scp` reais: quoting dos argumentos remotos e
    autenticação. Tudo o mais — sequência de comandos, detecção de duplicata, parse da
    listagem, códigos de saída — foi exercido de verdade. Repetir `just story-ship` e
    `just story-queue` sem `--remote` quando o servidor voltar (SC-007); é também
    pré-requisito do gate do M3, que precisa de pacotes reais na inbox do servidor.
  - Desvio de contrato registrado: `preview` **não** valida o pacote antes de narrar.
    A tabela de `contracts/cli.md` só prevê validação em `validate` e `ship`, e as duas
    receitas usam configs diferentes (`story-preview` roda com `config.prod.yaml`,
    `story-validate` com `config.yaml`), então validar aqui poderia recusar por um
    critério que não é o do passo. Um JSON malformado ainda falha na hora, ao carregar.

**Checkpoint**: [X] Milestone 2 DONE (2026-09-22) — o operador consegue preparar, ouvir e enfileirar histórias sem precisar do servidor. O envio por SSH real fica pendente de um host acessível (ver evidência de T027).

---

## Phase 5: Milestone 3 — O servidor consome a fila (US5 / P3)

**Goal**: o job diário produz e agenda primeiro o que está na fila, sem chamar os
modelos de avaliação e roteiro, completa com descoberta quando faltar (configurável), e
com a fila vazia se comporta exatamente como hoje.

**Independent test criteria** (antes de implementar):

- Fila vazia: `find_best_stories` é chamado com `exclude_urls` = URLs do publish log;
  nenhuma chamada da fila além de `list_inbox`; mensagens e manifestos iguais aos
  atuais, exceto `"source": "auto"`.
- N pacotes e meta N: zero chamadas a `find_best_stories`,
  `prepare_satisfying_story`, `evaluate_story`; `generate_hashtags` só para pacotes
  sem `hashtags`; títulos e roteiros usados verbatim.
- K < N: K preparados primeiro, depois descoberta com `exclude_urls` ⊇ os K;
  `fill_with_discovery: false` → só os K.
- Pacote inválido (versão, idioma, campos) → `failed/` + `error.txt` antes de gerar;
  falha de geração/publicação → `failed/`; sucesso → `done/` + `outcome.json`.
- `--generate-only` → `done/` com `status: generated`.
- `/prepared` no Telegram lista a inbox ou diz `Fila vazia.`
- `just prod-daily-generate 1` com um pacote na inbox gera `story_01.json` com o título
  do pacote e `"source": "prepared"`.

### Testes (escrever primeiro, ver falhar)

- [X] T028 [P] [US5] Testes de `PreparedStoryQueue` em tests/test_prepared_story_queue.py com `tmp_path`: cria `inbox/done/failed` sob demanda; `list_inbox` em ordem de mtime e depois nome; JSON inválido é movido para `failed/` com `error.txt` e não entra na lista; `mark_done` move e grava `outcome.json` com os campos do data-model.md; `mark_failed` move e grava `error.txt`; `known_post_urls` = inbox ∪ done
- [X] T029 [P] [US5] Testes do fluxo diário em tests/test_daily_prepared_flow.py (padrão de tests/test_publish_slots.py: `SimpleNamespace` para service/publisher/llm, monkeypatch de `_discover_stories`, `container`, `bot_config`, `_build_tiktok_publisher`, `TIKTOK_PUBLISH_LOG_PATH` em `tmp_path`): os sete invariantes da tabela de contracts/queue.md, cobrindo `run_daily_auto_publish` e `run_daily_generate`; `load_generated_videos` aceita manifesto sem `source`
- [X] T030 [P] [US5] Teste de dedup com o publish log em tests/test_daily_prepared_flow.py: CSV com linhas `scheduled` e `failed` → só as `scheduled` entram em `exclude_urls`; arquivo ausente → conjunto vazio

### Implementação

- [X] T031 [US5] Criar `PreparedStoryQueue(root)` e `QueuedPackage` (path, package, mtime) em src/services/prepared_story_queue.py conforme data-model.md; mover com `os.replace`; `outcome.json` e `error.txt` ao lado do pacote movido
- [X] T032 [US5] Registrar `prepared_story_queue = providers.Singleton(PreparedStoryQueue, root=main_config.provided.bots.satisfying_bot.prepared_stories.inbox_dir)` em src/core/container.py
- [X] T033 [US5] Em bots/satisfying_bot.py: dataclass `_WorkItem` (`prepared`, `summary`, `hashtags`, `source`, `queued`, `story`) e `_scheduled_post_urls(path)` que lê `post_url` das linhas `status == "scheduled"` do publish log (arquivo ausente → set vazio)
- [X] T034 [US5] Em bots/satisfying_bot.py: `_collect_candidates(count) -> list[_WorkItem]` que carrega `queue.list_inbox()`, valida cada pacote com `validate_package(pkg, text_censor, config.language)` mais versão (inválido → `mark_failed` + mensagem `⚠️ #i Pacote inválido: ...`), converte em `_WorkItem(prepared=pkg.to_prepared_story(), source="prepared")`, envia `📦 N história(s) preparada(s) na fila.` quando N > 0, e, se `len < count` e `fill_with_discovery`, chama `_discover_stories(exclude_urls=known ∪ scheduled)` e anexa itens `source="auto"`; passar `exclude_urls` por `_discover_stories` até `find_best_stories`
- [X] T035 [US5] Em bots/satisfying_bot.py: reescrever o laço de `run_daily_auto_publish` e `run_daily_generate` sobre `_collect_candidates`: item preparado pula `_prepare_story_with_retries` e envia `#i Usando roteiro preparado: "<título>"`; `_generate_video_for_story` recebe `summary` e `source` do item e grava `source` no manifesto (`_save_manifest`); `_publish_one_video` recebe `hashtags` do item e só chama `generate_hashtags` quando `None`; após sucesso `queue.mark_done` (em `--generate-only`, `status: generated`), após falha em qualquer etapa `queue.mark_failed`; preservar textos das mensagens existentes para o caminho automático
- [X] T036 [P] [US5] Comando `/prepared` em bots/satisfying_bot.py (`CommandHandler("prepared", cmd_prepared)` com `is_user_allowed`): lista `post_id`, título e `created_at` de `queue.list_inbox()` ou `Fila vazia.`
- [X] T037 [P] [US5] Criar docs/prepared-stories.md em português: por que o fluxo existe, os sete passos com as receitas `just`, formato do pacote (link para o contrato), o que acontece em `inbox/done/failed`, `fill_with_discovery`, como reenviar um pacote de `failed/`; adicionar link na seção de scripts do README.md
- [X] T038 [US5] Atualizar `AGENTS.md`/`CLAUDE.md` se necessário e `docs/architecture.md` com o desvio do job diário (fila antes da descoberta) no diagrama de pipeline

### Live verification (milestone gate)

- [X] T039 [US5] Rodar `uv run pytest tests/test_prepared_story_queue.py tests/test_daily_prepared_flow.py tests/test_publish_slots.py -q` (verde, existentes intactos), `just deploy`, e o quickstart.md §5 no servidor: pacote na inbox → `just prod-daily-generate 1` gera `story_01.json` com o título do pacote e `"source": "prepared"`, pacote em `done/` com `outcome.json`, log sem `Evaluating`/`Gerando roteiro`; inbox vazia → fluxo idêntico ao anterior com `"source": "auto"`; pacote com `"language": "en"` → `failed/` + `error.txt` e a run completa por descoberta; `/prepared` no Telegram; registrar a evidência aqui

  **Evidência (2026-09-22)**

  - `uv run pytest tests/test_prepared_story_queue.py tests/test_daily_prepared_flow.py
    tests/test_publish_slots.py -q` → **57 passed** (41 novos: 13 da fila, 28 do fluxo
    diário). Suíte inteira: `1 failed, 298 passed` — a única falha continua sendo a
    conhecida `tests/test_translation_pipeline.py::test_pipeline`, herdada da 002.
  - Caminho feliz, real e local (`CONFIG_PATH` com `low_quality: true`, pacote
    `1wmh90e` do M1 em `.storage/prepared/inbox/`):
    `uv run python scripts/daily_auto_publish.py --generate-only --count 1` →
    `🔄 Busca diária iniciada...`, `📦 1 história(s) preparada(s) na fila.`,
    `✅ Busca finalizada: 1 histórias disponíveis...`,
    `#1 Usando roteiro preparado: "Lavei a louça que não era minha..."`,
    `#1 Vídeo finalizado.`, `✅ Geração finalizada: 1/1 vídeos prontos.`
    `grep -cE "Evaluating|Gerando roteiro"` no log → **0**: nenhuma chamada de
    avaliação nem de roteiro (SC-004 no fluxo real).
    Manifesto `story_01.json` com `"source": "prepared"`, o título, o resumo e o
    `post_url` do pacote. Pacote em `done/` com
    `outcome.json` = `{status: "generated", scheduled_at: null, hashtags:
    ["reddit","historias","amizade"], video_path, manifest_path}` — as hashtags saíram
    do pacote, sem passar pelo LLM.
  - Fila vazia, real e local: mesma receita sem pacote na inbox → **nenhuma** mensagem
    `📦`, 35 candidatas avaliadas, `🎬 Gerando história #1: "..."`,
    `#1 Gerando roteiro...`, `#1 Roteiro finalizado. Gerando vídeo...` — exatamente as
    mensagens de antes da feature — e manifesto com `"source": "auto"`. `done/` e
    `failed/` não ganharam nada: com a fila vazia o job não a toca além do `list_inbox`
    (SC-003).
  - Pacote inválido, real e local: cópia do `1wmh90e` com `"language": "en"` na inbox e
    `fill_with_discovery: false` → `⚠️ #1 Pacote inválido: language: package=en
    server=pt. Movido para failed/.` e `Nenhuma história boa encontrada hoje.`; o pacote
    foi para `failed/` com `1wmh90e.error.txt` contendo a mesma mensagem, e **nenhum**
    vídeo chegou a ser gerado.
  - Fiação do container com a config real: `container.prepared_story_queue().root` →
    `.storage/prepared`, vindo de `bots.satisfying_bot.prepared_stories.inbox_dir`.
  - Dedup com o publish log, contra o arquivo real:
    `_scheduled_post_urls(_publish_log_path())` lê `.storage/tiktok_publish_log.csv` e
    devolve só as linhas `scheduled`.
  - `/prepared` exercitado contra a fila real (chamando `cmd_prepared` com um `update`
    de mentira, sem o transporte do Telegram): com um pacote na inbox →
    `📦 1 história(s) na fila:` + `1wmh90e  22/09 09:29  <título>`; inbox vazia →
    `Fila vazia.`; usuário fora de `allowed_user_ids` → a recusa padrão do bot.
  - **Não verificado**: `just deploy` e a run no servidor (`just prod-daily-generate 1`),
    porque `192.168.1.100` continua fora do ar (`ssh` → `Operation timed out`), o mesmo
    bloqueio registrado em T027. Também ficam sem verificação real o `/prepared` pelo
    transporte do Telegram e o `mark_done` com `status: "scheduled"`, que depende de uma
    publicação de verdade no TikTok — o publisher é server-only. Os três estão cobertos
    por teste. O que as runs locais cobrem é todo o resto do caminho: a fila lida da
    config, a validação, os dois manifestos, os movimentos entre `inbox/`, `done/` e
    `failed/`, e as mensagens dos dois fluxos.
  - Achado fora do escopo, corrigido aqui porque o M3 passou a depender do arquivo:
    `tests/test_publish_slots.py` não isolava `TIKTOK_PUBLISH_LOG_PATH` e vinha
    escrevendo suas linhas de fixture no `.storage/tiktok_publish_log.csv` de verdade
    desde 2026-05 — as 145 linhas do log deste laptop são todas `url-1/2/3` de teste.
    Como `_collect_candidates` agora lê esse log para excluir posts já agendados, o teste
    passou a isolar o caminho com `monkeypatch.setenv`. O log local não foi apagado (é do
    operador); ele só não recebe mais linhas de teste.
  - Desvio de contrato registrado: o contrato prevê `⚠️ #i Pacote inválido: <erro>` para
    todo pacote recusado, mas um arquivo que nem chega a parsear (JSON quebrado, `version`
    desconhecida) não tem um `#i` no run — ele é recusado no `list_inbox`, antes de virar
    candidato. Esses saem como `⚠️ Pacote inválido (<arquivo>): <erro>. Movido para
    failed/.`, que diz ao operador qual arquivo olhar. Os recusados pela validação, que
    têm posição no run, seguem o formato do contrato.
  - Segundo desvio: com `fill_with_discovery: false` e a fila curta, a mensagem final
    conta contra o que foi pedido (`1/2`), não contra o que era alcançável. Com a
    descoberta ligada o denominador continua sendo o de hoje (o número de histórias
    disponíveis), como a tabela de invariantes exige.

- [ ] T039b [US5] **Pendente do servidor** — quando `192.168.1.100` voltar: `just deploy`, depois o quickstart.md §5 lá: pacote na inbox → `just prod-daily-generate 1` com `"source": "prepared"` no manifesto e o pacote em `done/`; inbox vazia → `"source": "auto"`; `/prepared` pelo Telegram de verdade; e um `just prod-daily-publish 1` para exercitar `mark_done` com `status: "scheduled"` (o publisher é server-only). Também repetir aqui o `just story-ship`/`just story-queue` sem `--remote` que ficou pendente no T027. Nada disso se verifica no laptop: gerar vídeo localmente não é o fluxo — o laptop só produz áudio e texto para revisão

**Checkpoint**: [X] Milestone 3 DONE (2026-09-22) — o loop está fechado; fila vazia = comportamento de hoje. O gate no servidor (`just deploy` + `just prod-daily-generate 1`) fica pendente de o host voltar; tudo o que não depende dele foi verificado em runs reais no laptop.

---

## Phase 6: Milestone 4 — Histórias em duas partes pelo fluxo preparado (US6 / P3)

**Goal**: o operador escolhe, por história, entre um vídeo e duas partes; o assistente
recebe o prompt de duas partes exato do servidor, o pacote `version: 2` é validado e
ouvido parte a parte, e o job diário produz os dois vídeos com o mesmo método do vídeo
único e agenda a parte 2 no slot seguinte ao da parte 1. A descoberta automática não
muda.

**Independent test criteria** (antes de implementar):

- `just story-prompt N --two-part` imprime byte a byte o que `generate_two_part_story`
  enviaria, exemplos inclusos.
- Um pacote `version: 2` passa em `validate`, gera dois mp3 em `preview` e aparece em
  `list` como `2 partes`; sem o CTA no fim da parte 1, `validate` falha nomeando
  `part1_text`.
- No servidor, um pacote `version: 2` na inbox produz `story_01.mp4` e
  `story_01_p2.mp4` com covers ` - Parte 1` / ` - Parte 2`, sem chamada de roteiro, e
  publica os dois em slots consecutivos; um servidor sem o M4 move o mesmo pacote para
  `failed/` com `unsupported package version`.

### Tests for Milestone 4

- [X] T042 [P] [US6] Testes de `TwoPartStoryPackage` e `load_package` em tests/test_prepared_story_package.py: round-trip JSON; `to_story_script()` mapeia para `StoryScript`; `to_prepared_stories()` devolve dois `PreparedStory` com `story_title` sufixado ` - Parte 1`/` - Parte 2` e `script_text` igual à parte; `load_package` devolve o modelo certo para `version` 1 e 2 e levanta `ValueError("unsupported package version")` para 3; **`PreparedStoryPackage.model_validate` rejeita `version: 2`** (é a garantia de SC-009 num servidor antigo); `part1_text`/`part2_text` vazios rejeitados
- [X] T043 [P] [US6] Teste de regressão em tests/test_render_two_part_prompt.py, no padrão de `test_render_story_prompt.py`: `render_two_part_story_prompt(title, content, language)` é byte a byte o `messages[0]["content"]` que `PromptLLMProxy.generate_two_part_story` envia (com `litellm.acompletion` falso); o texto começa com `You are an expert TikTok scriptwriter.` e contém os três exemplos de `src/proxies/examples/two_part_story.yaml`
- [X] T044 [P] [US6] Testes de `validate_package` para a versão 2 em tests/test_prepared_story_package.py: palavra proibida em `story_title`, `part1_text` e `part2_text` reportada com o nome do campo e o contexto; idioma diferente; `part1_text` sem `Curta e me siga para a parte 2.` no fim (com e sem espaços finais) → `part1_text: precisa terminar com ...`; idioma sem CTA fixado pula a regra; pacote válido → lista vazia
- [X] T045 [P] [US6] Testes do CLI em tests/test_prepare_story_cli.py: `prompt N --two-part` imprime o prompt de duas partes; `validate` aceita versão 1 e 2 e imprime problemas por campo; `list` marca `2 partes`; `preview` de versão 2 chama `generate_speech` duas vezes com o gênero do pacote, grava `<post_id>.part1.preview.mp3` e `<post_id>.part2.preview.mp3` e imprime duas durações e o total; `queue` lista um pacote versão 2 pelo título
- [X] T046 [P] [US6] Testes do bot em tests/test_daily_prepared_flow.py (sem rede, padrão de `test_publish_slots.py`): pacote versão 2 na inbox com meta 1 → uma história, zero chamadas a `find_best_stories`/`prepare_satisfying_story`, `generate_satisfying_video_from_story` chamado duas vezes com os títulos sufixados, `story_01.mp4` + `story_01_p2.mp4` e manifestos com `part` 1 e 2 e o mesmo `post_url`; publicação → `publish_video` duas vezes, o segundo `schedule_at` = `next_publish_slot(after=<slot da parte 1>)`, mesmas hashtags (geradas uma vez quando o pacote não as traz), duas linhas no publish log, `done/` com `outcome.json` listando os dois vídeos; parte 2 falha na produção → `publish_video` nunca chamado, `failed/` com o erro; parte 2 falha na publicação → `failed/` com mensagem contendo o slot da parte 1; `--generate-only` → `done/` com `status: generated` e os dois vídeos; fila vazia → comportamento de M3 intacto (nenhum item com `part2`); `run_daily_publish` a partir de um diretório com `story_01.json` e `story_01_p2.json` agenda em ordem e em slots consecutivos

### Implementation for Milestone 4

- [X] T047 [P] [US6] `TwoPartStoryPackage`, `_PackageBase` e `load_package` em src/entities/prepared_story.py conforme data-model.md; `PreparedStoryPackage` passa a herdar da base sem mudar de forma (T002 continua verde)
- [X] T048 [P] [US6] `render_two_part_story_prompt` em src/proxies/prompts/render.py (carrega `examples/two_part_story.yaml` como o proxy faz hoje) e `PromptLLMProxy.generate_two_part_story` em src/proxies/llm_prompt_proxy.py passando a chamá-lo (T043 verde)
- [X] T049 [US6] `validate_package` em src/services/prepared_story_validation.py aceitando as duas formas: campos de texto por versão, CTA da parte 1 por idioma (mapa `PART2_CTA`, só `pt-br` por ora), mensagens por campo (T044 verde; depende de T047)
- [X] T050 [US6] src/services/prepared_story_queue.py: `QueuedPackage.package` lido com `load_package`; um arquivo com `version` desconhecida continua indo para `failed/` no `list_inbox` com a mensagem `unsupported package version` (testes de M3 intactos; depende de T047)
- [X] T051 [US6] scripts/prepare_story.py: `prompt --two-part`; `_load_package` via `load_package`; `list` com `2 partes`; `preview` por parte com nomes `<post_id>.partN.preview.mp3`, durações e total; `queue` imprimindo o título das duas formas; receita `story-prompt n *args` no Justfile (T045 verde; depende de T047–T049)
- [X] T052 [US6] bots/satisfying_bot.py: `_WorkItem.part2`; `_collect_candidates` monta parte 1 e parte 2 de um pacote versão 2 (uma história na meta, `#i Usando roteiro preparado em duas partes`); `_generate_video_for_story` produz as duas partes em sequência com `generate_satisfying_video_from_story`, nomes `story_NN.mp4`/`story_NN_p2.mp4`, `GeneratedVideo.part`, dois manifestos, falha do item inteiro se qualquer parte falhar; `_publish_one_video` reutilizado para a parte 2 com `last_slot` = slot da parte 1 e as hashtags da parte 1; `mark_done` só depois das duas, `outcome.json` com `videos`; parte 2 falhando ao publicar → `mark_failed` com o slot da parte 1; `run_daily_generate`, `run_daily_auto_publish` e `run_daily_publish` cobrindo os dois vídeos (T046 verde; depende de T047 e T050)
- [X] T053 [P] [US6] .claude/skills/prepare-story/SKILL.md: passo 3 apresenta a escolha do formato e quando sugerir duas partes (prévia única longa ou gancho natural antes do desfecho), com o comando `just story-prompt N --two-part` e o esquema `version: 2`; passo 6 com as duas prévias; a decisão do formato listada entre as que são do operador
- [X] T054 [P] [US6] docs/prepared-stories.md: seção "Histórias em duas partes" (quando usar, formato do pacote, o que o servidor faz, o que acontece se uma parte falhar)
- [X] T055 [US6] Rodar o quickstart.md §6 na parte local (prompt, validação, prévia, `list`) e registrar aqui; a parte de servidor (`just prod-daily-generate 1` com pacote versão 2, covers com sufixo, slots consecutivos, e o `failed/` num servidor sem o M4) fica pendente junto com T039b até o host voltar

  **Evidência (2026-09-22, laptop)**

  Testes: `uv run pytest tests/test_prepared_story_package.py
  tests/test_render_two_part_prompt.py tests/test_prepare_story_cli.py
  tests/test_prepared_story_queue.py tests/test_daily_prepared_flow.py
  tests/test_publish_slots.py tests/test_render_story_prompt.py -q` → **177 passed**.
  Suíte inteira: `1 failed, 357 passed` — a única falha é a pré-existente
  `tests/test_translation_pipeline.py::test_pipeline`, conhecida desde a feature 002.

  Quickstart §6, parte local, rodado de verdade com as candidatas reais do dia em
  `output/prepared/candidates.json` (38 candidatas) e o pacote escrito em
  `output/prepared-m4/` para não tocar nos pacotes versão 1 do operador:

  - `just story-prompt 1 --two-part` → 133 linhas começando com
    `You are an expert TikTok scriptwriter.` seguido de `Take the provided original
    Reddit post and turn it into a 2-part story...`, com `Expected Output JSON:`
    aparecendo 3 vezes (os três exemplos de `examples/two_part_story.yaml`).
  - Pacote `version: 2` escrito para `1wn08nz` (a história do sogro, cujo roteiro
    único tinha 6393 chars ≈ 5 min — exatamente o caso que pede o corte):
    `part1_text` 3716 chars terminando no celular apitando na sala, `part2_text`
    2730 chars abrindo na notificação. `just story-validate` → `✓`, exit 0.
  - Apagando o `Curta e me siga para a parte 2.` do fim da parte 1:
    `✗ 1wn08nz.json` / `- part1_text: precisa terminar com "Curta e me siga para a
    parte 2."`, exit 1. Restaurado → `✓` de novo.
  - `just story-preview` → `1wn08nz.part1.preview.mp3` **02:50**,
    `1wn08nz.part2.preview.mp3` **02:09**, `Total 04:59`, com a voz `male` do pacote.
    Os dois mp3 foram entregues ao operador para ouvir.
  - `story-list` no diretório: `1wn08nz  2026-09-22T13:39:53  [mp3 ok]  [2 partes]
    Meu sogro de 60 anos...` — e `[sem mp3]` antes das prévias, com as duas exigidas
    para o `mp3 ok`.

  Não verificado aqui (fica com T039b, pendente do host): `just prod-daily-generate 1`
  com um pacote versão 2 na inbox, os covers com sufixo, os slots consecutivos de
  verdade e o `failed/` com `unsupported package version` num servidor sem o M4.
  Gerar vídeo no laptop não é o fluxo — daqui só saem áudio e texto para revisão.

**Checkpoint**: [X] Milestone 4 DONE (2026-09-22) — a metade local verificada no laptop (prompt, validação por parte, duas prévias, `list`); o gate no servidor pendente do host, como em M3 (ver T039b).

---

## Phase 7: Polish

- [ ] T040 [P] Rodar `uv run black src scripts tests bots` e revisar os diffs dos quatro PRs contra a constituição (fail fast fora dos pontos justificados; nada de I/O em `src/entities`/`src/services` além do diretório da fila)

  **Parcial (2026-09-22, PR de polish)**: `black==26.5.1` adicionado ao extra `dev` do
  pyproject (não estava instalado) e `uv run black src scripts tests bots` rodado —
  60 arquivos reformatados, quase todos com drift anterior a esta feature; os módulos
  novos do M1 já saíram praticamente formatados. Receita `fmt` do Justfile passou a
  usar `uv run` e a incluir `bots`, para o drift não voltar. Suíte depois da
  formatação: `1 failed, 239 passed` (mesma falha pré-existente).

  Revisão do diff do **PR 1 (M1)** contra a constituição: sem I/O em
  `src/entities/prepared_story.py` nem em `src/services/prepared_story_validation.py`
  (todo o acesso a arquivo vive em `scripts/prepare_story.py`); o único ponto que não
  falha na hora é o `validate`, que captura `ValidationError` porque relatar problemas
  de pacote é exatamente o contrato do subcomando. Falta revisar os diffs de M2 e M3,
  que ainda não existem — por isso a tarefa continua aberta.
- [ ] T041 Rodar o quickstart.md §7 completo e a suíte inteira `uv run pytest -q`; registrar o resultado no plan.md (seção "Verificação pós-implementação", como na feature 002)

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2 → M1 → M2 → M3 → M4 → Polish**. Milestone N+1 não começa antes do gate de N (M4 aceita o gate de servidor de M3 pendente, porque a parte local não depende dele).
- **Dentro de M1**: T004–T007 (testes) em paralelo; T008 e T009/T010 em paralelo (arquivos diferentes); T011 depende de T008; T012 depende de T009, T010 e T011; T013 pode andar junto com T011; T014 depende de T012 e T013; T015 depende de T011; T016 fecha.
- **Dentro de M2**: T017–T019 em paralelo; T020 antes de T021, T023 e T024; T022 independe de T020; T025 junto com T022; T026 depois de T023/T024; T027 fecha.
- **Dentro de M3**: T028–T030 em paralelo; T031 → T032 → T033 → T034 → T035 em sequência (mesmo arquivo para T033–T035); T036 e T037 em paralelo com T035; T038 depois de T035; T039 fecha.
- **US3 e US4** são independentes entre si (arquivos distintos no CLI), mas compartilham o PR 2.
- **US5** depende de M1 (entidade + validação) e de M2 (config `prepared_stories`, pacotes reais na inbox para o gate).
- **Dentro de M4**: T042–T046 (testes) em paralelo; T047 e T048 em paralelo (arquivos diferentes); T049 e T050 depois de T047, em paralelo; T051 depois de T047–T049; T052 depois de T047 e T050; T053 e T054 a qualquer momento; T055 fecha.
- **US6** depende de M1 (entidade, validação, CLI), M2 (prévia) e M3 (fila e `_collect_candidates`); não toca `story.jinja2` nem a descoberta automática.

## Parallel Example: Milestone 1

```bash
# Testes primeiro, todos em paralelo (arquivos diferentes):
Task: "T004 find_candidates em tests/services/test_story_finder_service.py"
Task: "T005 regressão de render_story_prompt"
Task: "T006 validate_package em tests/test_prepared_story_package.py"
Task: "T007 CLI em tests/test_prepare_story_cli.py"

# Depois, implementação em paralelo:
Task: "T008 find_candidates em src/services/story_finder_service.py"
Task: "T009 render_story_prompt em src/proxies/prompts/render.py"
Task: "T010 validate_package em src/services/prepared_story_validation.py"
```

## Implementation Strategy

1. **MVP = M1** (T001–T016). Ao final, o operador já consegue descobrir, escolher com o
   assistente e produzir um pacote validado. É a parte que o usuário quer nos próximos
   três dias.
2. **M2** (T017–T027) fecha a experiência local: ouvir e enfileirar. O gate roda contra
   `localhost`; repetir contra o servidor quando ele estiver acessível.
3. **M3** (T028–T039) só quando o servidor estiver acessível para o gate; o código pode
   ser escrito antes, com os testes cobrindo tudo sem rede.
4. **M4** (T042–T055) só depois de M3 fechado; a metade local roda no laptop, a de
   servidor junta-se ao gate pendente de M3.
5. Commit por tarefa ou grupo lógico; cada milestone é um PR.

## Notes

- Nenhuma tarefa de M1/M2 toca `bots/satisfying_bot.py`; o comportamento do servidor
  só muda no PR 3.
- `RedditVideoService`, `ILLMProxy` e `IRedditProxy` não mudam de contrato em nenhum
  milestone. Em M4 as duas partes são produzidas com `generate_satisfying_video_from_story`
  chamado duas vezes; `compose_two_part_video` continua sem consumidor.
- Nunca aplicar `TextCensor.censor` ao texto que vai para o TTS; na validação ele é só
  detector.
