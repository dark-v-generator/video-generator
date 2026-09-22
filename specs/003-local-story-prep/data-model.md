# Data Model: Preparação local de histórias e hand-off para o servidor

## PreparedStoryPackage (`src/entities/prepared_story.py`)

Entidade pydantic serializada em JSON. É o único artefato que viaja do laptop para o
servidor. Campos:

| Campo | Tipo | Obrigatório | Origem | Uso no servidor |
|-------|------|-------------|--------|-----------------|
| `version` | `Literal[1]` | sim | CLI | rejeita versões desconhecidas |
| `source` | `str` (`"claude-code"`, `"manual"`) | sim, default `"claude-code"` | skill/CLI | manifesto (`source: prepared`) e log |
| `language` | `Language` (aceita `pt-br`) | sim | `config.language` local | deve ser igual ao `config.language` do servidor |
| `created_at` | `datetime` (ISO) | sim | CLI | listagem da fila |
| `post` | `RedditPost` | sim | `find`/`show` (Reddit) | cover (`community`, `author`, `community_url_photo`), `post_url` no manifesto |
| `story_title` | `str` não vazio | sim | assistente | título do cover e `description` da publicação |
| `script_text` | `str` não vazio | sim | assistente | TTS e base das legendas |
| `narrator_gender` | `"male" \| "female" \| "unknown"` | sim | assistente | registrado em `story.md` |
| `resolved_gender` | `"male" \| "female"` | sim | derivado (`narrator_gender` ou `male`) | voz do TTS |
| `summary` | `str` | sim | assistente (3 a 5 frases) | `summary` do manifesto e entrada de `generate_hashtags` |
| `hashtags` | `list[str] \| None` | não | assistente/operador | se presente, pula `generate_hashtags` |

Derivados (propriedades, não serializados):

- `post_id`: id do post extraído de `post.url` (`/comments/<id>/`); nome do arquivo é
  `<post_id>.json`. URL sem esse padrão é erro de validação.
- `original_post_md`: `f"# {post.title}\n\n{post.content}\n"`, igual ao que
  `prepare_satisfying_story` monta.
- `to_prepared_story() -> PreparedStory`: mapeamento 1:1 para o dataclass existente.

Regras de validação (pydantic + `validate_package`):

1. Campos obrigatórios presentes e não vazios (pydantic).
2. `post.url` presente e com id extraível.
3. `language` igual ao idioma esperado (parâmetro; no servidor, `config.language`).
4. Nenhuma palavra de `story_title` ou `script_text` é alterada por
   `TextCensor.censor`; cada ocorrência é reportada como `"<campo>: '<palavra>' em
   '...contexto...'"`.
5. `resolved_gender` coerente com `narrator_gender` quando este é `male`/`female`.

## Candidates file (`output/prepared/candidates.json`)

Saída do subcomando `find`; consumida por `show`, `prompt` e pelo skill.

```json
{
  "generated_at": "2026-09-21T10:12:00",
  "sort": "top", "time_filter": "day",
  "subreddits": ["pettyrevenge", "..."],
  "candidates": [
    {
      "rank": 1,
      "deterministic_score": 78.4,
      "score_breakdown": {"rel_upvotes": 70.0, "length": 100.0, "...": 0},
      "post": { "...RedditPost..." }
    }
  ]
}
```

`rank` é 1-based e é o número que o operador usa em `show N` e `prompt N`.

## PreparedStoriesConfig (`src/entities/configs/bots.py`)

Aninhado em `TelegramBotConfig` como `prepared_stories`:

| Campo | Tipo | Default | Quem usa |
|-------|------|---------|----------|
| `remote` | `str` | `gustavo@192.168.1.100:~/video-generator/.storage/prepared` | CLI `ship`/`queue` |
| `inbox_dir` | `str` | `.storage/prepared` | servidor (`PreparedStoryQueue`) |
| `fill_with_discovery` | `bool` | `true` | job diário |

## PreparedStoryQueue (`src/services/prepared_story_queue.py`)

Serviço sobre um diretório raiz. Estados de um pacote são diretórios:

```text
<root>/
├── inbox/   <post_id>.json                       # aguardando
├── done/    <post_id>.json + <post_id>.outcome.json   # produzido e agendado
└── failed/  <post_id>.json + <post_id>.error.txt      # falhou em validação/produção/publicação
```

Transições:

- `inbox → done`: após o pacote ser produzido e publicado (ou, em `--generate-only`,
  produzido). `outcome.json`: `{status, scheduled_at, hashtags, video_path, manifest_path}`.
- `inbox → failed`: pacote inválido (idioma, versão, campos), falha na geração ou
  na publicação. `error.txt`: mensagem truncada como no Telegram.
- Sem transição de volta; reenviar é responsabilidade do operador (`ship --force`
  sobrescreve em `inbox/`).

Operações:

- `list_inbox() -> list[QueuedPackage]` (FIFO por mtime, depois nome). Um arquivo que
  não parseia como `PreparedStoryPackage` é movido para `failed/` na hora e não entra
  na lista.
- `mark_done(item, outcome)`, `mark_failed(item, error)`.
- `known_post_urls() -> set[str]`: `inbox` ∪ `done`.

## Work item do job diário (`bots/satisfying_bot.py`)

Estrutura interna (dataclass) que unifica os dois caminhos no laço existente:

| Campo | Preparado (fila) | Automático (descoberta) |
|-------|------------------|-------------------------|
| `prepared: PreparedStory \| None` | `pkg.to_prepared_story()` | `None` (preenchido por `_prepare_story_with_retries`) |
| `summary` | `pkg.summary` | `story.resumo[:400]` |
| `hashtags: list[str] \| None` | `pkg.hashtags` | `None` (gera via LLM) |
| `source` | `"prepared"` | `"auto"` |
| `queued: QueuedPackage \| None` | item da fila (para `mark_done`/`mark_failed`) | `None` |

## GeneratedVideo manifest (`output/daily/<name>.json`)

Ganha um campo, retrocompatível (`load_generated_videos` ignora chaves extras):

```json
{ "video_path": "...", "title": "...", "summary": "...", "post_url": "...", "source": "prepared" }
```
