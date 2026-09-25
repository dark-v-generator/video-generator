# Contrato do fluxo diário — `src/flows/daily_run.py` (M6)

```python
Progress = Callable[[str], Awaitable[None]]

class DailyRun:
    def __init__(
        self, *,
        discovery: StoryDiscovery, writer: StoryWriter, renderer: Renderer,
        publisher: ITikTokPublisherProxy, hashtags: HashtagSuggester,
        store: RunStore, config: DailyRunConfig, progress: Progress,
        now: Callable[[], datetime] = datetime.now,
    ): ...

    async def generate(self, *, count: int | None = None,
                       output_dir: str = "output/daily") -> list[GeneratedVideo]
    async def publish(self, videos: list[GeneratedVideo]) -> None
    async def run(self, *, count: int | None = None,
                  output_dir: str = "output/daily") -> None
```

## Modos

| Modo | Método | Hoje |
|------|--------|------|
| Completo | `run` | `run_daily_auto_publish` |
| Só gerar | `generate` | `run_daily_generate` |
| Só publicar | `publish(store.load_manifests(dir))` | `run_daily_publish(load_generated_videos(dir))` |

## Decisões que ficam no fluxo (FR-014)

1. Meta do dia: `count` do argumento, senão `config.count`; limitada ao número
   de candidatas disponíveis.
2. Exclusão: `discovery.find_best_stories(exclude_urls=store.scheduled_post_urls())`.
3. Roteiro: `discovery.fetch(url)` e `writer.write(origin)`; até 3 tentativas com
   backoff 5 s, 10 s em `WriterTransientError`; `WriterContentBlockedError` e
   `WriterError` pulam a candidata. `story.summary` recebe `resumo[:400]` da
   avaliação.
4. Renderização: `renderer.render(story)`; qualquer falha pula a candidata sem
   publicar nada dela. Cada `RenderedPart` vira `story_NN[_pk].mp4` +
   manifest via `store.save_manifest`.
5. Publicação: `hashtags.suggest` uma vez por história (ou `hashtags.normalize`
   se `story.hashtags`); parte k no `next_publish_slot(after=slot da parte k-1)`;
   falha em qualquer parte → linha `failed`, candidata pulada, próxima começa
   após o último slot efetivamente agendado.
6. Meta conta histórias, não vídeos.
7. Lock: `RunLock` em `src/flows/progress.py`; o bot recusa uma segunda rodada
   com a mensagem atual. O CLI não usa lock (como hoje).

## Mensagens de progresso

Idênticas às atuais, em português, na mesma ordem. O golden
(`tests/fixtures/daily_run_golden.json`) é a referência; a lista abaixo é o
resumo dos formatos:

- `🔄 Busca diária iniciada...`
- `Erro ao buscar histórias: {e}` / `Nenhuma história boa encontrada hoje.`
- `✅ Busca finalizada: {n} histórias disponíveis. Iniciando geração de {count} vídeo{s}.`
  (generate) / `... Iniciando geração de vídeo e agendamento.` (run)
- `🎬 Gerando história #{i}: "{title}"`, `#{i} Gerando roteiro...{ (tentativa a/3)}`,
  `#{i} Roteiro finalizado. Gerando vídeo...`
- `⏳ #{i} Erro temporário, tentando de novo em {d}s (tentativa a/3)...`
- `⚠️ #{i} Bloqueado por filtro de conteúdo, pulando.`
- `❌ #{i} Erro no roteiro: {e}. Tentando outra história para completar {count}.`
- `❌ #{i} Erro na geração de vídeo: {e}. Pulando para a próxima história.`
- `#{i} Parte {k} gerada` (só com mais de uma parte), `#{i} Vídeo finalizado.`
  (generate) / `#{i} Vídeo finalizado. Agendando história...` (run)
- `#{i} Agendamento concluído para {dd/mm HH:MM}`
- `❌ #{i} Erro ao publicar: {e}. Pulando para uma nova história.` (run) /
  `❌ [#{i} — {title[:60]}] Erro: {e}` (publish-only)
- `✅ Geração finalizada: {p}/{count} vídeos prontos.` /
  `✅ Fluxo finalizado: {p}/{count} vídeos agendados.` /
  `📤 Agendando {n} vídeos...` e `🏁 Agendamento concluído.` (publish-only)

Erros são truncados em 300 caracteres com `…`, como hoje.

## Adaptadores

- `bots/satisfying_bot.py`: `/autopost [n]` e o job diário chamam
  `container.daily_run(progress=send_to_chat).run(count=n)` sob `RunLock`;
  URL → vídeo usa `discovery.fetch`, `writer.write`, `renderer.render` e
  `send_video_bytes` na fila de jobs.
- `scripts/daily_auto_publish.py`: `--count`, `--output-dir`, `--generate-only`,
  `--publish-only DIR` chamam os três modos com `progress=print`.
- Ambos são testados com um `DailyRun` falso: só se verifica que o método certo
  foi chamado com os argumentos certos.
