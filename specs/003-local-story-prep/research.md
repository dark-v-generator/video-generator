# Research: Preparação local de histórias e hand-off para o servidor

Todas as decisões abaixo foram tomadas lendo o código atual (`bots/satisfying_bot.py`,
`src/services/reddit_video_service.py`, `src/services/story_finder_service.py`,
`src/proxies/llm_prompt_proxy.py`, `Justfile`). Não restou nenhum NEEDS CLARIFICATION.

## 1. Onde cortar o pipeline

**Decision**: o pacote serializa exatamente `PreparedStory`
(`src/services/reddit_video_service.py:101`) mais os metadados que o publicador usa
(`summary`, `hashtags`, `language`, `source_url`).

**Rationale**: o docstring de `PreparedStory` já diz "contains everything needed to
produce the video without further LLM calls". Depois dele, `generate_satisfying_video_from_story`
faz TTS, legendas, cover e render sem LLM (a única chamada restante, `enhance_transcription`
nas legendas, é do `llm_proxy` barato e faz parte da produção, não da criação). Tudo
que o pacote precisa carregar já está nesse dataclass: `post` (`RedditPost` completo,
porque o cover usa `community`, `author` e `community_url_photo`), `script_text`,
`story_title`, `narrator_gender`, `resolved_gender`, `original_post_md`.

**Alternatives considered**:
- Enviar só a URL + o roteiro e deixar o servidor re-raspar o post: adiciona uma
  dependência de rede (Reddit) ao caminho manual e pode falhar se o post for apagado.
  Rejeitado.
- Enviar o áudio já sintetizado: o servidor tem o mesmo edge-tts; mandar mp3 só
  aumenta o pacote e cria dois lugares para a voz divergir. Rejeitado.

## 2. Formato do pacote

**Decision**: JSON, um arquivo por história, nome `<post_id>.json` onde `post_id` é o
id do post extraído da URL (`/comments/<id>/`). Modelo pydantic `PreparedStoryPackage`
com `version: 1`.

**Rationale**: os manifestos de `output/daily/*.json` já são JSON; a saída do prompt
editorial (`story.jinja2`) já é JSON com `title`/`narrator_gender`/`script`, então o
assistente produz o pacote quase direto. O nome pelo `post_id` torna a duplicata
detectável por `test -e` remoto sem abrir arquivos (FR-009) e dá idempotência natural.

**Alternatives considered**:
- YAML via `BaseYAMLModel` (como `RedditHistory`): mais legível para editar à mão,
  mas o assistente emite JSON com mais confiabilidade e o restante do fluxo diário já
  fala JSON. Rejeitado.
- Um diretório por pacote (json + mp3 + md): mais arquivos para transportar; a prévia
  de áudio é local e não viaja. Rejeitado; o mp3 fica ao lado com sufixo `.preview.mp3`.

## 3. Shortlist local sem LLM

**Decision**: extrair de `StoryFinderService.find_best_stories` um método
`find_candidates(sort, time_filter, posts_per_sub, top_per_sub, subreddits,
exclude_urls)` que devolve `list[StoryCandidate]` ordenada por `deterministic_score`.
`find_best_stories` passa a ser `find_candidates` + laço de `evaluate_story` + corte
por veredito, sem mudar comportamento. O CLI `find` chama só `find_candidates`.

**Rationale**: o ranking determinístico (`score_candidates`) já pesa engajamento,
tamanho, qualidade textual e frescor; é o que hoje seleciona os finalistas antes do
LLM. Para o operador escolher com o próprio assistente, isso basta e custa zero.
`exclude_urls` serve tanto ao CLI (ignorar o que já está em `output/prepared/`)
quanto ao servidor (FR-014).

**Alternatives considered**:
- Flag `skip_llm` no método existente: mistura dois modos, retorno ambíguo. Rejeitado
  (ver Complexity Tracking no plano).
- Rodar a avaliação por LLM localmente via API: viola SC-002. Rejeitado.

## 4. Fonte única das regras editoriais (FR-003)

**Decision**: função pura `render_story_prompt(title, content, language) -> str` em
`src/proxies/prompts/render.py`, usada por `PromptLLMProxy.generate_story` e pelo
subcomando `prompt` do CLI. O skill manda o assistente executar `prompt N`, seguir o
texto renderizado e responder com o mesmo JSON que o servidor espera.

**Rationale**: o assistente recebe literalmente o prompt que o Kimi receberia, com o
post já embutido. Um teste de regressão garante que o proxy e o CLI produzem o mesmo
texto. Sem duplicar regras no skill.

**Alternatives considered**:
- Skill lendo `story.jinja2` cru: o assistente teria que interpretar Jinja e adivinhar
  `target_language`. Rejeitado.
- Copiar as regras para o `SKILL.md`: drift garantido. Rejeitado.

## 5. Como o assistente avalia as candidatas

**Decision**: o skill pede ao assistente que leia `candidates.json` e use os cinco
critérios de `src/proxies/prompts/evaluate_story.jinja2` (retenção, qualidade,
viralização, adequação ao TikTok, gancho) como lente para propor as 3 a 5 melhores,
explicando em uma linha por que cada uma. A nota numérica não é exigida; a decisão é
do operador.

**Rationale**: o objetivo é substituir o modelo de avaliação pago pelo julgamento do
assistente da assinatura. Reusar os critérios mantém o gosto consistente com o que o
servidor faria, sem exigir JSON de notas que ninguém vai consumir.

## 6. Validação local

**Decision**: `validate_package(pkg, censor, expected_language) -> list[str]` em
`src/services/prepared_story_validation.py`. Verifica campos obrigatórios (pydantic
já cobre), roteiro não vazio, `language` igual ao `config.language`, e palavras
proibidas em `story_title` e `script_text` usando `TextCensor` como detector:
tokeniza por palavra e acusa toda palavra em que `censor(word) != word`, reportando a
palavra e um trecho de contexto.

**Rationale**: `TextCensor` já codifica as famílias proibidas da política de
palavras fortes (mesma lista de `story.jinja2`) e aceita `extra_word_replacements`
da config, então a validação local e a censura de produção concordam por construção.
O docstring do censor diz para não aplicá-lo ao texto que vai para o TTS; aqui ele
não altera o texto, só detecta.

**Alternatives considered**:
- Lista própria de palavras na validação: segunda fonte de verdade. Rejeitado.

## 7. Prévia de áudio

**Decision**: subcomando `preview` usa `container.speech_service().generate_speech(text,
gender=resolved_gender, rate=1.0, language=pkg.language)` e grava
`<post_id>.preview.mp3`. Duração via `AudioClip(bytes=...).clip.duration`.

**Rationale**: é a mesma chamada que `generate_satisfying_video_from_story` faz com
`speech_rate=1.0`; o `EdgeTTSProxy` multiplica por `default_rate` (1.5 em produção),
então o operador ouve exatamente o que será publicado, desde que rode com o mesmo
`config.yaml` (o de produção é o `config.prod.yaml`; o quickstart instrui
`CONFIG_PATH=config.prod.yaml` para a prévia).

**Alternatives considered**:
- Renderizar o vídeo completo localmente: já existe (`daily_auto_publish.py
  --generate-only`), é lento e não é necessário para julgar o roteiro. Fora do escopo.

## 8. Transporte para o servidor

**Decision**: `ship` faz, via `subprocess`, `ssh <host> mkdir -p <dir>/inbox`, `ssh
<host> test -e <dir>/inbox/<post_id>.json` (duplicata → pede confirmação, a menos de
`--force`), e `scp <file> <host>:<dir>/inbox/`. `queue` faz `ssh <host> 'for f in
<dir>/inbox/*.json; do cat "$f"; done'` e imprime título, URL e mtime. O destino vem
de `bots.satisfying_bot.prepared_stories.remote` (default
`gustavo@192.168.1.100:~/video-generator/.storage/prepared`), sobrescrevível por
`--remote`.

**Rationale**: o `Justfile` já depende de `ssh`/`rsync` para deploy e para sincronizar
runs do TikTok; nenhum serviço novo, nenhuma porta nova. O IP já está no `Justfile`
versionado. Pôr a lógica no Python (e não só na receita `just`) permite testar a
recusa de pacote inválido e a confirmação de duplicata com `subprocess` mockado.

**Alternatives considered**:
- Upload pelo bot do Telegram (documento): funciona do celular e sem SSH; fica como
  possível adição futura, registrada na spec. Não agora, para não tocar o bot antes
  do M3.
- Endpoint HTTP no servidor: `main.py` referencia um `src/main_fastapi` que não existe;
  reviver isso é escopo à parte. Rejeitado.
- Commit no git + deploy: `just deploy` reinicia o bot; misturar dados com deploy é
  frágil. Rejeitado.

## 9. Fila no servidor e ordem de consumo

**Decision**: `PreparedStoryQueue(root)` com `inbox/`, `done/`, `failed/`. `list_inbox()`
ordena por mtime e depois nome (FIFO). `mark_done` move para `done/` e grava
`<post_id>.outcome.json` (status, slot agendado, hashtags, caminho do vídeo).
`mark_failed` move para `failed/` e grava `<post_id>.error.txt`. `known_post_urls()`
lê `inbox/` + `done/`.

No bot, `_collect_candidates(count)` devolve uma lista de itens de trabalho: primeiro
os pacotes (já `PreparedStory` + `summary` + `hashtags`), depois, se `len < count` e
`fill_with_discovery`, o resultado de `find_best_stories(exclude_urls=known ∪ publish_log)`.
O laço existente passa a receber esse item: quando já vem preparado, pula
`_prepare_story_with_retries`.

**Rationale**: espelha a estrutura já usada para runs do TikTok em `.storage/`. FIFO
por mtime é o que o operador espera ("o que enviei primeiro sai primeiro"). A lista
de trabalho unificada é a menor mudança no laço do bot que preserva o caminho atual
byte a byte quando a fila está vazia.

**Alternatives considered**:
- Um segundo laço só para pacotes antes do laço atual: duplica o tratamento de
  agendamento e log. Rejeitado.
- Expiração de pacotes antigos: fora do escopo (spec).

## 10. Deduplicação com o histórico de publicação (FR-014)

**Decision**: ler `post_url` de `.storage/tiktok_publish_log.csv` (colunas já
existentes: `status`, `post_url`) para linhas com `status == "scheduled"`, unir com
`known_post_urls()` da fila, e passar como `exclude_urls` à descoberta.

**Rationale**: o log já é a fonte de verdade do que foi agendado; é lido pelo mesmo
processo que o escreve. Nenhum índice novo.

## 11. Skill do Claude Code

**Decision**: `.claude/skills/prepare-story/SKILL.md` no repo (o diretório já hospeda
os skills do speckit). Estrutura: objetivo e por que o fluxo existe; passos com o
comando `just`/`uv run` de cada um; o que o assistente decide sozinho (ranking,
redação, revisão) e o que sempre pergunta ao operador (qual história, aprovar o
roteiro, enviar). Linguagem no espírito do princípio III: explica o porquê, não
enumera casos.

**Rationale**: o skill é a interface do operador com a feature; mantê-lo no repo faz
ele evoluir junto com o CLI e as templates.

## 12. Config

**Decision**: `PreparedStoriesConfig` aninhado em `TelegramBotConfig`
(`bots.satisfying_bot.prepared_stories`): `remote: str`, `inbox_dir: str =
".storage/prepared"`, `fill_with_discovery: bool = True`. Omitir o bloco = defaults
(padrão do projeto: `config.yaml` é override parcial).

**Rationale**: a fila pertence ao bot que a consome; o `remote` mora ao lado porque o
CLI local lê o mesmo `config.yaml`.
