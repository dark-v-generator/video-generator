# Contrato: `scripts/prepare_story.py` e receitas `just`

Todos os subcomandos leem `CONFIG_PATH` (default `config.yaml`) e usam o container
existente. Nenhum subcomando chama modelo de LLM.

| Subcomando | Argumentos | Efeito | Saída | Milestone |
|------------|------------|--------|-------|-----------|
| `find` | `--sort top\|new\|hot` (top), `--time day\|week\|...` (day), `--per-sub N` (25), `--top-per-sub N` (5), `--sub r/x` (repetível), `--out DIR` (`output/prepared`) | `StoryFinderService.find_candidates`, excluindo URLs de pacotes já em `--out` | Tabela: `rank`, score, comunidade, pontos, comentários, chars, título, URL. Grava `candidates.json` | M1 |
| `show N` | rank | Imprime título, metadados e o texto original completo do candidato N | texto | M1 |
| `prompt N` | rank, `--language` (config) | `render_story_prompt(post.title, post.content, language)` | o prompt exato do servidor, em stdout | M1 |
| `validate FILE...` | caminhos | `PreparedStoryPackage` + `validate_package` | `✓ file` ou lista de problemas; exit 1 se algum falhar | M1 |
| `list` | `--out DIR` | Lista pacotes locais | título, `post_id`, criado em, se há `.preview.mp3` | M1 |
| `preview FILE` | caminho, `--rate` (1.0) | `speech_service.generate_speech` com gênero/idioma do pacote; grava `<post_id>.preview.mp3` ao lado (sobrescreve) | caminho do mp3 e duração `mm:ss` | M2 |
| `ship FILE...` | caminhos, `--remote user@host:dir` (config), `--force` | valida; `ssh mkdir -p dir/inbox`; se `dir/inbox/<post_id>.json` existe e não `--force`, pergunta `y/N`; `scp` | `→ enviado <post_id>.json para <remote>/inbox` ou erro; arquivo local intacto em qualquer falha | M2 |
| `queue` | `--remote` | `ssh` lista e lê `dir/inbox/*.json` | tabela: `post_id`, título, URL, `created_at`, mtime remoto | M2 |

Códigos de saída: 0 sucesso; 1 validação falhou / recusa; 2 erro de rede ou ssh
(mensagem inclui o comando que falhou e o stderr).

## Receitas `just`

```text
story-find *args        → uv run python scripts/prepare_story.py find {{args}}
story-show n            → ... show {{n}}
story-prompt n          → ... prompt {{n}}
story-validate file     → ... validate {{file}}
story-preview file      → CONFIG_PATH=config.prod.yaml ... preview {{file}}
story-ship file         → ... ship {{file}}
story-queue             → ... queue
```

`story-preview` usa `config.prod.yaml` por padrão para que a voz e a velocidade
(`default_rate: 1.5`) sejam as de produção. As demais receitas usam o `config.yaml`
local (mesma lista de subreddits e mesmo `language`).

## Skill `.claude/skills/prepare-story/SKILL.md`

Entrada: `/prepare-story` (opcionalmente com `--sub` ou uma URL do Reddit para pular
a descoberta). Passos que o skill conduz:

1. Roda `just story-find` e lê `output/prepared/candidates.json`.
2. Propõe 3 a 5 candidatas com uma linha de justificativa cada, usando os critérios
   de `src/proxies/prompts/evaluate_story.jinja2` como lente. Pergunta qual.
3. Roda `just story-prompt N`, segue o prompt renderizado e escreve o JSON do pacote em
   `output/prepared/<post_id>.json` (com `summary` e `hashtags`).
4. Roda `just story-validate`; corrige e repete até passar.
5. Mostra o roteiro ao operador e aceita revisões (mantém o arquivo anterior até o
   operador aprovar).
6. Roda `just story-preview` e pede para o operador ouvir; volta ao passo 5 se pedir.
7. Só envia (`just story-ship`) com confirmação explícita do operador.

O que o assistente nunca faz sozinho: escolher a história, aprovar o roteiro, enviar.
