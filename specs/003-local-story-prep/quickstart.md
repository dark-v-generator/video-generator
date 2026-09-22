# Quickstart: validar a feature de ponta a ponta

Pré-requisitos locais: `uv sync`, `.env` com `REDDIT_CLIENT_ID` e
`REDDIT_CLIENT_SECRET`, `config.yaml` com a lista de subreddits e `language: pt-br`.
Nenhuma chave de LLM é necessária para as seções 1 a 4.

Contratos: [cli.md](./contracts/cli.md), [prepared_story_package.md](./contracts/prepared_story_package.md),
[queue.md](./contracts/queue.md).

## 1. Descobrir candidatas sem API (M1, US1)

```bash
just story-find
```

Esperado: tabela ranqueada com rank, score, comunidade, pontos, comentários, tamanho,
título e link; arquivo `output/prepared/candidates.json`. No log não aparece nenhuma
linha `LiteLLM` nem `Evaluating`. Um subreddit indisponível aparece como aviso e os
outros são listados.

```bash
just story-show 1
```

Esperado: texto original completo do candidato 1.

## 2. Escrever e validar o pacote (M1, US2)

No Claude Code, dentro do repo:

```text
/prepare-story
```

Esperado: o assistente propõe 3 a 5 candidatas com justificativa, pergunta qual, roda
`just story-prompt N`, escreve `output/prepared/<post_id>.json`, roda
`just story-validate` até passar e mostra o roteiro para revisão.

Verificação da fonte única de regras (FR-003):

```bash
just story-prompt 1 | head -5
```

Esperado: o texto começa com `You are an expert TikTok scriptwriter.`, idêntico ao
início de `src/proxies/prompts/story.jinja2` renderizado.

Verificação da validação: edite o pacote inserindo `matou` no roteiro e rode

```bash
just story-validate output/prepared/<post_id>.json
```

Esperado: `✗` com a palavra e o contexto, exit 1. Desfaça a edição e rode de novo:
`✓`, exit 0.

## 3. Ouvir a narração (M2, US3)

```bash
just story-preview output/prepared/<post_id>.json
```

Esperado: `output/prepared/<post_id>.preview.mp3` e a duração impressa. A voz é a do
gênero em `resolved_gender` e a velocidade é a de produção (1.5x). Edite o roteiro,
rode de novo: o mp3 é substituído e a duração muda.

## 4. Enviar para a fila (M2, US4)

Sem acesso ao servidor, use o próprio laptop como destino:

```bash
uv run python scripts/prepare_story.py ship output/prepared/<post_id>.json \
  --remote "$USER@localhost:$PWD/.storage/prepared"
```

Esperado: `→ enviado <post_id>.json para ...` e o arquivo em
`.storage/prepared/inbox/`. Rodar de novo pergunta `já existe na fila, substituir?
[y/N]`; `--force` pula a pergunta.

```bash
uv run python scripts/prepare_story.py queue --remote "$USER@localhost:$PWD/.storage/prepared"
```

Esperado: uma linha com `post_id`, título, URL e horário.

Pacote inválido:

```bash
uv run python scripts/prepare_story.py ship /caminho/invalido.json
```

Esperado: recusa com os erros de validação, exit 1, nada enviado.

Com o servidor acessível, o mesmo sem `--remote`:

```bash
just story-ship output/prepared/<post_id>.json
just story-queue
```

## 5. O servidor consome a fila (M3, US5)

Requer acesso ao servidor. Deixe um pacote na inbox (seção 4) e rode só geração:

```bash
just prod-daily-generate 1
```

Esperado no Telegram/stdout: `📦 1 história(s) preparada(s) na fila.`, `#1 Usando
roteiro preparado: "<título>"`, sem `Busca diária`/`Gerando roteiro`. No servidor:
`output/daily/story_01.json` com o `title` do pacote e `"source": "prepared"`;
`.storage/prepared/done/<post_id>.json` e `<post_id>.outcome.json`.

Fila vazia:

```bash
just prod-daily-generate 1
```

Esperado: fluxo idêntico ao anterior à feature (busca, avaliação, roteiro), manifesto
com `"source": "auto"`.

Idioma errado: envie um pacote com `"language": "en"` e rode de novo. Esperado:
`⚠️ #1 Pacote inválido: language mismatch ...`, pacote em `failed/` com
`<post_id>.error.txt`, e a run completa o vídeo por descoberta.

## 6. História em duas partes (M4, US6)

Prompt de duas partes, byte a byte o do servidor:

```bash
just story-prompt 3 --two-part | head -3
```

Esperado: o texto começa com `You are an expert TikTok scriptwriter.` seguido de `Take
the provided original Reddit post and turn it into a 2-part story`, e contém os três
exemplos de `src/proxies/examples/two_part_story.yaml`.

No Claude Code, `/prepare-story` com um post longo: o assistente oferece o formato de
duas partes e, se o operador escolher, escreve `output/prepared/<post_id>.json` com
`"version": 2`, `part1_text` e `part2_text`.

Validação por parte: apague o `Curta e me siga para a parte 2.` do fim de
`part1_text` e rode

```bash
just story-validate output/prepared/<post_id>.json
```

Esperado: `✗` com `part1_text: precisa terminar com "Curta e me siga para a parte 2."`,
exit 1. Restaure e rode de novo: `✓`.

Prévia por parte:

```bash
just story-preview output/prepared/<post_id>.json
```

Esperado: `<post_id>.part1.preview.mp3` e `<post_id>.part2.preview.mp3`, com a duração de
cada parte e o total impressos. `just story-list` mostra o pacote com `2 partes`.

Envio e fila (seção 4) funcionam sem mudança. No servidor, com o pacote na inbox:

```bash
just prod-daily-generate 1
```

Esperado: `#1 Usando roteiro preparado em duas partes: "<título>"`, `#1 Parte 1
gerada`, `#1 Parte 2 gerada`; `output/daily/story_01.mp4` e `story_01_p2.mp4`, cada um
com seu manifesto (`"part": 1` / `"part": 2`, mesmo `post_url`, `"source": "prepared"`)
e o cover com ` - Parte 1` / ` - Parte 2`; nenhuma chamada de roteiro no log; pacote em
`done/` com `outcome.json` listando os dois vídeos. Com `just prod-daily-publish 1`, os
dois `Agendamento concluído` caem em slots consecutivos.

Servidor sem suporte (antes do deploy do M4): o mesmo pacote na inbox termina em
`failed/` com `unsupported package version` e nada é gerado.

## 7. Testes automatizados

```bash
uv run pytest tests/test_prepared_story_package.py tests/test_prepare_story_cli.py \
  tests/test_prepared_story_queue.py tests/test_daily_prepared_flow.py \
  tests/test_render_story_prompt.py tests/test_render_two_part_prompt.py \
  tests/services/test_story_finder_service.py
```

Esperado: tudo verde; os testes existentes de `story_finder_service` e
`test_publish_slots.py` passam sem alteração.
