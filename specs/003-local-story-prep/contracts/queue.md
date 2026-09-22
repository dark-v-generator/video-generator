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
| `--generate-only` | pacote vai para `done/` com `status: generated` e `scheduled_at: null` |

## Mensagens no Telegram (novas)

- `📦 N história(s) preparada(s) na fila.` no início, só quando N > 0.
- `#i Usando roteiro preparado: "<título>"` no lugar de `Gerando roteiro...`.
- `⚠️ #i Pacote inválido: <erro>. Movido para failed/.`
- Comando `/prepared`: lista `inbox/` (`post_id`, título, criado em) ou `Fila vazia.`

## Manifesto

`output/daily/story_NN.json` ganha `"source": "prepared" | "auto"`. `load_generated_videos`
continua aceitando manifestos antigos sem o campo.
