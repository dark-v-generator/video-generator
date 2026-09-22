# Tasks: Preparação local de histórias e hand-off para o servidor

**Input**: Design documents from `/specs/003-local-story-prep/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Incluídos — os gates de verificação do plan.md exigem testes por milestone e
o projeto tem suíte pytest estabelecida (`asyncio_mode = auto`). Escrever os testes de
cada story primeiro e vê-los falhar antes de implementar.

**Organization**: 3 milestones = 3 PRs (ver Delivery Plan). M1 cobre US1+US2 (um PR,
porque o skill que fecha US2 depende do `find` de US1 e ambos são a metade local que o
usuário quer primeiro); M2 cobre US3+US4; M3 cobre US5 e só é verificável no servidor.
Tarefas dentro de um milestone são commits do mesmo PR, nunca PRs separados.

## Format: `[ID] [P?] [Story] Description`

## Delivery Plan

| PR | Milestone | Stories | Conteúdo |
|----|-----------|---------|----------|
| 1 | M1 — Descobrir, roteirizar e validar localmente | US1, US2 | `find_candidates`, `render_story_prompt`, `PreparedStoryPackage`, `validate_package`, CLI `find/show/prompt/validate/list`, receitas `just`, skill `/prepare-story`, testes |
| 2 | M2 — Ouvir e enviar | US3, US4 | `PreparedStoriesConfig`, CLI `preview/ship/queue`, receitas `just`, skill fechando o loop, testes |
| 3 | M3 — O servidor consome a fila | US5 | `PreparedStoryQueue`, `_collect_candidates` no bot, dedup com publish log, `/prepared`, manifesto com `source`, doc do operador, testes |

Projeção: **3 PRs** (≤ 8, ok).

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

- [ ] T028 [P] [US5] Testes de `PreparedStoryQueue` em tests/test_prepared_story_queue.py com `tmp_path`: cria `inbox/done/failed` sob demanda; `list_inbox` em ordem de mtime e depois nome; JSON inválido é movido para `failed/` com `error.txt` e não entra na lista; `mark_done` move e grava `outcome.json` com os campos do data-model.md; `mark_failed` move e grava `error.txt`; `known_post_urls` = inbox ∪ done
- [ ] T029 [P] [US5] Testes do fluxo diário em tests/test_daily_prepared_flow.py (padrão de tests/test_publish_slots.py: `SimpleNamespace` para service/publisher/llm, monkeypatch de `_discover_stories`, `container`, `bot_config`, `_build_tiktok_publisher`, `TIKTOK_PUBLISH_LOG_PATH` em `tmp_path`): os sete invariantes da tabela de contracts/queue.md, cobrindo `run_daily_auto_publish` e `run_daily_generate`; `load_generated_videos` aceita manifesto sem `source`
- [ ] T030 [P] [US5] Teste de dedup com o publish log em tests/test_daily_prepared_flow.py: CSV com linhas `scheduled` e `failed` → só as `scheduled` entram em `exclude_urls`; arquivo ausente → conjunto vazio

### Implementação

- [ ] T031 [US5] Criar `PreparedStoryQueue(root)` e `QueuedPackage` (path, package, mtime) em src/services/prepared_story_queue.py conforme data-model.md; mover com `os.replace`; `outcome.json` e `error.txt` ao lado do pacote movido
- [ ] T032 [US5] Registrar `prepared_story_queue = providers.Singleton(PreparedStoryQueue, root=main_config.provided.bots.satisfying_bot.prepared_stories.inbox_dir)` em src/core/container.py
- [ ] T033 [US5] Em bots/satisfying_bot.py: dataclass `_WorkItem` (`prepared`, `summary`, `hashtags`, `source`, `queued`, `story`) e `_scheduled_post_urls(path)` que lê `post_url` das linhas `status == "scheduled"` do publish log (arquivo ausente → set vazio)
- [ ] T034 [US5] Em bots/satisfying_bot.py: `_collect_candidates(count) -> list[_WorkItem]` que carrega `queue.list_inbox()`, valida cada pacote com `validate_package(pkg, text_censor, config.language)` mais versão (inválido → `mark_failed` + mensagem `⚠️ #i Pacote inválido: ...`), converte em `_WorkItem(prepared=pkg.to_prepared_story(), source="prepared")`, envia `📦 N história(s) preparada(s) na fila.` quando N > 0, e, se `len < count` e `fill_with_discovery`, chama `_discover_stories(exclude_urls=known ∪ scheduled)` e anexa itens `source="auto"`; passar `exclude_urls` por `_discover_stories` até `find_best_stories`
- [ ] T035 [US5] Em bots/satisfying_bot.py: reescrever o laço de `run_daily_auto_publish` e `run_daily_generate` sobre `_collect_candidates`: item preparado pula `_prepare_story_with_retries` e envia `#i Usando roteiro preparado: "<título>"`; `_generate_video_for_story` recebe `summary` e `source` do item e grava `source` no manifesto (`_save_manifest`); `_publish_one_video` recebe `hashtags` do item e só chama `generate_hashtags` quando `None`; após sucesso `queue.mark_done` (em `--generate-only`, `status: generated`), após falha em qualquer etapa `queue.mark_failed`; preservar textos das mensagens existentes para o caminho automático
- [ ] T036 [P] [US5] Comando `/prepared` em bots/satisfying_bot.py (`CommandHandler("prepared", cmd_prepared)` com `is_user_allowed`): lista `post_id`, título e `created_at` de `queue.list_inbox()` ou `Fila vazia.`
- [ ] T037 [P] [US5] Criar docs/prepared-stories.md em português: por que o fluxo existe, os sete passos com as receitas `just`, formato do pacote (link para o contrato), o que acontece em `inbox/done/failed`, `fill_with_discovery`, como reenviar um pacote de `failed/`; adicionar link na seção de scripts do README.md
- [ ] T038 [US5] Atualizar `AGENTS.md`/`CLAUDE.md` se necessário e `docs/architecture.md` com o desvio do job diário (fila antes da descoberta) no diagrama de pipeline

### Live verification (milestone gate)

- [ ] T039 [US5] Rodar `uv run pytest tests/test_prepared_story_queue.py tests/test_daily_prepared_flow.py tests/test_publish_slots.py -q` (verde, existentes intactos), `just deploy`, e o quickstart.md §5 no servidor: pacote na inbox → `just prod-daily-generate 1` gera `story_01.json` com o título do pacote e `"source": "prepared"`, pacote em `done/` com `outcome.json`, log sem `Evaluating`/`Gerando roteiro`; inbox vazia → fluxo idêntico ao anterior com `"source": "auto"`; pacote com `"language": "en"` → `failed/` + `error.txt` e a run completa por descoberta; `/prepared` no Telegram; registrar a evidência aqui

**Checkpoint**: Milestone 3 DONE — o loop está fechado; fila vazia = comportamento de hoje.

---

## Phase 6: Polish

- [ ] T040 [P] Rodar `uv run black src scripts tests bots` e revisar os diffs dos três PRs contra a constituição (fail fast fora dos pontos justificados; nada de I/O em `src/entities`/`src/services` além do diretório da fila)

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
- [ ] T041 Rodar o quickstart.md §6 completo e a suíte inteira `uv run pytest -q`; registrar o resultado no plan.md (seção "Verificação pós-implementação", como na feature 002)

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2 → M1 → M2 → M3 → Polish**. Milestone N+1 não começa antes do gate de N.
- **Dentro de M1**: T004–T007 (testes) em paralelo; T008 e T009/T010 em paralelo (arquivos diferentes); T011 depende de T008; T012 depende de T009, T010 e T011; T013 pode andar junto com T011; T014 depende de T012 e T013; T015 depende de T011; T016 fecha.
- **Dentro de M2**: T017–T019 em paralelo; T020 antes de T021, T023 e T024; T022 independe de T020; T025 junto com T022; T026 depois de T023/T024; T027 fecha.
- **Dentro de M3**: T028–T030 em paralelo; T031 → T032 → T033 → T034 → T035 em sequência (mesmo arquivo para T033–T035); T036 e T037 em paralelo com T035; T038 depois de T035; T039 fecha.
- **US3 e US4** são independentes entre si (arquivos distintos no CLI), mas compartilham o PR 2.
- **US5** depende de M1 (entidade + validação) e de M2 (config `prepared_stories`, pacotes reais na inbox para o gate).

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
4. Commit por tarefa ou grupo lógico; cada milestone é um PR.

## Notes

- Nenhuma tarefa de M1/M2 toca `bots/satisfying_bot.py`; o comportamento do servidor
  só muda no PR 3.
- `RedditVideoService`, `ILLMProxy` e `IRedditProxy` não mudam de contrato em nenhum
  milestone.
- Nunca aplicar `TextCensor.censor` ao texto que vai para o TTS; na validação ele é só
  detector.
