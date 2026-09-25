# Configuração: o que muda nos `config*.yaml`

## Removido dos arquivos do repositório (M1)

```yaml
proxies:
  image_generation_config: ...        # removido
  portrait_generation_config: ...     # removido
bots:
  image_story_bot: ...                # removido
  satisfying_bot:
    prepared_stories: ...             # removido (estava comentado)
services:
  video_config:
    draw_transition_duration: ...     # removido (só o image story usava)
```

Um `config.yaml` local que ainda tenha essas chaves continua carregando: os
modelos de configuração ignoram chaves desconhecidas.

## Novo (M4, M5), com os padrões que reproduzem o comportamento atual

```yaml
services:
  video_config:
    # De onde vem o vídeo de fundo. "youtube" é o que roda hoje; "local"
    # concatena os .mp4 de local_footage_dir e não toca na rede.
    footage_source: youtube
    # local_footage_dir: assets/backgrounds
    # Como a história vira vídeo. Só existe uma estratégia hoje; uma nova
    # (animação, sequência de imagens) é registrada no container e escolhida aqui.
    rendering_strategy: narration-over-footage
```

## Segredos (`.env`) que deixam de ser lidos (M1)

`LEONARDO_API_KEY`, `RUNPOD_API_KEY`, `LEGNEXT_API_KEY`,
`TELEGRAM_IMAGE_STORY_BOT_TOKEN`. Podem ficar no arquivo; são ignorados.

## Receitas `just` (M1, M5)

Removidas: `generate-reddit`, `generate-reddit-fast`, `story-find`, `story-show`,
`story-prompt`, `story-validate`, `story-list`, `story-preview`, `story-ship`,
`story-queue`.

Mantidas: `daily-publish`, `daily-generate`, `daily-publish-only`, `prod-*`,
`deploy`, `fmt`, `sync-tiktok-runs`, `push-tiktok-learnings`, `tiktok-*`.

Nova (M5): `render-story story_json footage_dir` →
`scripts/render_story.py`, o exemplo de SC-008.
