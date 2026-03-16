# Gerador de Vídeos Narrados

Cria vídeos verticais narrados a partir de posts do Reddit para redes sociais. O projeto extrai o post, gera um roteiro em duas partes com LLM, sintetiza a narração, transcreve legendas e compõe o vídeo final.

Há dois modos de geração:

- **Two-part history** — vídeo de fundo (compilação YouTube) + narração + legendas + cover.
- **Image story** — imagens geradas por IA timed com a narração, com introdução (blur + cover), transições e call-to-action.

## Instalação

### Pré-requisitos

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Dependências

```bash
uv sync
```

## Configuração

Toda a configuração é feita via `config.yaml` na raiz do projeto. Valores omitidos usam os defaults definidos nos modelos Pydantic.

### Configuração para teste local (sem APIs externas)

```yaml
proxies:
  llm_config:
    type: mock            # mock | prompt | dspy
  image_generation_config:
    type: mock            # mock | local | leonardo
  speech_config:
    type: edge-tts        # edge-tts | elevenlabs
  transcription_config:
    type: local           # local | openai
    model: base           # tiny | base | small | medium | large
  cover_config:
    title_font_size: 150
services:
  captions_config:
    font_path: default_font.ttf
  video_config:
    call_to_action_path: assets/call_to_action.png
    youtube_channel_url: https://www.youtube.com/channel/UCIXTGJvqvxWoWWstA66a2JQ
```

Com `mock` para LLM e image generation, nenhuma API key é necessária. O speech usa `edge-tts` (gratuito) e a transcrição usa Whisper local.

### Configuração para produção

```yaml
proxies:
  llm_config:
    type: prompt          # ou dspy
    provider_config:
      provider: google    # google | openai | ollama
      model: gemini-2.0-flash
  image_generation_config:
    type: leonardo        # ou local
  speech_config:
    type: elevenlabs
  transcription_config:
    type: openai
```

Variáveis de ambiente necessárias para produção:

```
GOOGLE_API_KEY=...        # se provider: google
OPENAI_API_KEY=...        # se provider: openai ou transcription: openai
ELEVENLABS_API_KEY=...    # se speech: elevenlabs
LEONARDO_API_KEY=...      # se image_generation: leonardo
```

## Scripts

### Image Story Video (imagens IA + narração)

Gera um vídeo com imagens de IA sincronizadas com a narração. Pipeline completo: scrape Reddit -> roteiro -> speech -> legendas -> LLM gera prompts de imagens -> gera imagens -> compõe vídeo.

```bash
# Uso básico
uv run python scripts/image_story_video.py <URL_DO_POST_REDDIT>

# Preview rápido (resolução baixa)
uv run python scripts/image_story_video.py <URL_DO_POST_REDDIT> --low-quality

# Todas as opções
uv run python scripts/image_story_video.py <URL_DO_POST_REDDIT> \
    --output-dir output \
    --language pt \
    --gender male \
    --rate 1.0 \
    --low-quality
```

Artefatos gerados em `output/`:
- `part1.mp4`, `part2.mp4` — vídeos finais
- `audio_part1.mp3`, `audio_part2.mp3` — áudios da narração
- `captions_part1.json`, `captions_part2.json` — legendas
- `image_story_part1.json`, `image_story_part2.json` — timeline de imagens
- `story.md` — roteiro gerado
- `original_post.md` — post original
- `cover.png` — capa

### Two-Part History Video (vídeo de fundo YouTube)

Gera um vídeo com compilação de vídeos do YouTube como fundo. Mesmo pipeline de roteiro/speech/legendas, mas com background de gameplay.

```bash
# Uso básico
uv run python scripts/reddit_two_part_history.py <URL_DO_POST_REDDIT>

# Preview rápido
uv run python scripts/reddit_two_part_history.py <URL_DO_POST_REDDIT> --low-quality

# Todas as opções
uv run python scripts/reddit_two_part_history.py <URL_DO_POST_REDDIT> \
    --output-dir output \
    --language pt \
    --gender female \
    --rate 1.2 \
    --low-quality
```

### Gerar imagem de Call to Action

```bash
uv run python scripts/generate_call_to_action.py
```

## Opções comuns dos scripts

| Flag | Descrição | Default |
|------|-----------|---------|
| `--output-dir` | Diretório de saída | `output` |
| `--language` | Idioma do roteiro e narração (`pt`, `en`, etc.) | `pt` |
| `--gender` | Gênero da voz (`male`/`female`). Auto-detectado se omitido | auto |
| `--rate` | Velocidade da narração (1.0 = normal) | `1.0` |
| `--low-quality` | Renderiza em 400px de largura para preview rápido | off |

## Comandos úteis

```bash
# Adicionar dependência
uv add package-name

# Atualizar dependências
uv lock --upgrade

# Executar testes
uv run pytest

# Ver ajuda de qualquer script
uv run python scripts/image_story_video.py --help
uv run python scripts/reddit_two_part_history.py --help
```
