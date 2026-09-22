# Contrato: fila no servidor e job diário

## Diretórios

Raiz: `bots.satisfying_bot.prepared_stories.inbox_dir` (default `.storage/prepared`,
relativo ao working directory do bot). Subdiretórios `inbox/`, `done/`, `failed/`,
criados sob demanda tanto pelo `ship` (via `ssh mkdir -p`) quanto pelo job diário.

## Comportamento do job diário (`run_daily_auto_publish` e `run_daily_generate`)

```text
work = []
for pkg in queue.list_inbox():                     # FIFO
    if len(work) == count: break
    work.append(prepared item)
if len(work) < count and fill_with_discovery:
    exclude = queue.known_post_urls() | publish_log_urls(status == scheduled)
    results = find_best_stories(..., exclude_urls=exclude)   # como hoje
    work += [auto item for each result]                       # o laço corta em count
```

Invariantes verificáveis em teste:

| Situação | Garantia |
|----------|----------|
| `inbox/` vazia | `find_best_stories` chamado com `exclude_urls` = URLs do publish log; nenhuma outra chamada da fila além de `list_inbox`; mensagens do Telegram e manifestos iguais aos atuais, exceto o campo `source: auto` |
| N pacotes, meta N | zero chamadas a `find_best_stories`, `prepare_satisfying_story`, `evaluate_story`; `generate_hashtags` só para pacotes sem `hashtags` |
| K < N pacotes, `fill_with_discovery: true` | K preparados primeiro, depois descoberta; `exclude_urls` contém os K |
| K < N pacotes, `fill_with_discovery: false` | só os K; mensagem final `K/N` |
| pacote inválido (versão, idioma, campos) | movido para `failed/` antes de gerar; mensagem `⚠️ #i Pacote inválido: <erro>`; run continua |
| geração ou publicação falha | `failed/` com o erro; run continua como hoje |
| sucesso | `done/` com `outcome.json`; publish log com `post_url` do pacote |
| pacote `version: 2` | conta como uma história na meta; gera `story_NN.mp4` e `story_NN_p2.mp4` (manifestos com `part`); publica a parte 1 no próximo slot e a parte 2 com `last_slot` = slot da parte 1, com as mesmas hashtags; duas linhas no publish log com o mesmo `post_url`; `done/` só depois das duas |
| `version: 2`, um dos vídeos falha | `failed/` com o erro, nenhum publicado, run continua |
| `version: 2`, parte 1 publicada, parte 2 falha ao publicar | `failed/` com erro `parte 2 não publicada; parte 1 agendada para <slot>`; run continua |
| `version: 2` num servidor sem suporte | `list_inbox` não parseia (`version` desconhecida) → `failed/`, nada produzido (SC-009) |
| `--generate-only` | pacote vai para `done/` com `status: generated` e `scheduled_at: null` |

## Mensagens no Telegram (novas)

- `📦 N história(s) preparada(s) na fila.` no início, só quando N > 0.
- `#i Usando roteiro preparado: "<título>"` no lugar de `Gerando roteiro...`.
- `⚠️ #i Pacote inválido: <erro>. Movido para failed/.`
- `#i Usando roteiro preparado em duas partes: "<título>"` para pacotes `version: 2`,
  seguido de `#i Parte 1 gerada` / `#i Parte 2 gerada` e de dois `Agendamento concluído`.
- Comando `/prepared`: lista `inbox/` (`post_id`, título, criado em) ou `Fila vazia.`

## Manifesto

`output/daily/story_NN.json` ganha `"source": "prepared" | "auto"`. `load_generated_videos`
continua aceitando manifestos antigos sem o campo.

Um pacote de duas partes produz `story_NN.mp4` + `story_NN.json` (`"part": 1`) e
`story_NN_p2.mp4` + `story_NN_p2.json` (`"part": 2`), ambos com o mesmo `post_url` e o
`title` já sufixado (`... - Parte 1` / `... - Parte 2`). Manifestos sem `part` são
vídeos únicos. `run_daily_publish` (publicar a partir do diretório) lê os manifestos em
ordem de nome, o que já coloca `_p2` logo depois do seu par; ele agenda a parte 2 no
slot seguinte ao da parte 1 pela mesma regra do job completo.
