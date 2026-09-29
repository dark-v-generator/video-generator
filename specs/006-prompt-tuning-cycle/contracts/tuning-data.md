# Pacote de dados do relatório (M2, completado no M4 e M5)

`just tuning-data` faz toda a conta. A skill lê o resultado e interpreta.

## Comando

```text
just tuning-data [--since DATA] [--until DATA] [--days N] [--json ARQUIVO]
                 [--min-settled N] [--max-age-days N] [--settle-days N]
```

| Argumento | Padrão | Efeito |
|---|---|---|
| `--days` | 30 | período terminando hoje, quando `--since` não é dado |
| `--json` | stdout | grava o pacote em arquivo |
| `--min-settled` | 30 | abaixo disso, recusa |
| `--max-age-days` | 3 | idade máxima da última coleta |
| `--settle-days` | 7 | dias entre publicação e coleta para um vídeo assentar |

Lê `HISTORY_DB_PATH` (o arquivo puxado por `just sync-history`) e `TUNING_DIR`.

**Recusas** (código de saída 2, mensagem em uma linha, nada em stdout):

- última coleta mais velha que `--max-age-days`: "última coleta em DATA; rode
  `just prod-collect-performance`";
- menos vídeos assentados que `--min-settled`: "N vídeos assentados no período;
  o mínimo é M; amplie com `--days`".

## Formato

```json
{
  "generated_at": "2026-10-06T14:02:11",
  "period": {"since": "2026-09-06", "until": "2026-10-06"},
  "data_as_of": "2026-10-05T23:10:00",
  "cycle": {"number": 1, "opened": "2026-10-02", "deployed": "2026-10-02",
            "prompts": {"story": "…", "evaluate_story": "…", "generate_hashtags": "…", "evaluate_exploration": null}},
  "prompt_drift": [{"prompt": "story", "recorded": "…", "on_disk": "…"}],
  "videos": {
    "considered": 71,
    "excluded": {"unsettled": 9, "no_snapshot": 3, "ambiguous_goal": 0}
  },
  "channel": {
    "weekly": [{"week": "2026-09-07", "videos": 19, "median_views": 880}],
    "lost_uploads": {"attempts_failed": 12, "never_published": 7}
  },
  "rows": [
    {"record_id": 322, "title": "…", "summary": "…", "published_at": "…",
     "settled": true, "views": 5400, "relative": 4.9, "neighbours": 10,
     "grade_overall": 82.0, "avg_watch_seconds": 38.1, "retained_3s": 0.71,
     "for_you_share": 0.93, "new_followers": 12,
     "goal": "base", "exploration_experiment": null, "exploration_fit": null,
     "cycle": 1, "story_prompt_version": "…", "grading_prompt_version": "…",
     "label": {"kind": "workplace", "narrator_acts": true, "title_promise": "reaction"}}
  ],
  "unlabelled": [330, 331],
  "cycle_comparison": {
    "current": {"cycle": 1, "base_videos": 14, "median_relative": 1.1},
    "previous": {"cycle": 0, "base_videos": 57, "median_relative": 1.0},
    "also_changed": [],
    "verdict_possible": false,
    "reason": "14 vídeos de base assentados no ciclo; o mínimo é 20"
  },
  "exploration": {
    "share_intended": 0.25,
    "share_since": "2026-10-02",
    "share_achieved": 0.21,
    "slots": 5, "filled": 4,
    "experiments": [
      {"id": "E001", "produced": 4, "settled": 2, "target": 10,
       "median_relative": 0.7, "videos": [341, 344],
       "days_to_target": 19, "target_reached": false}
    ]
  }
}
```

## Regras de cálculo

- **`relative`**: [research.md §5](../research.md). `null` com menos de 5
  vizinhos e nos vídeos não assentados. Os vizinhos vêm do histórico inteiro,
  não só do período, assim como os vídeos de cada ciclo e de cada experimento.
- **`published_at`**: `scheduled_at` da tentativa agendada mais recente; sem
  ela, o `tiktok_created_at` do snapshot (o publicador às vezes relata falha de
  um vídeo que o TikTok publicou).
- **`settled`**: `taken_at − published_at ≥ settle-days`, com o `taken_at` do
  snapshot do próprio vídeo. `rows` traz todos os
  vídeos do período; `considered` conta só os assentados com snapshot.
- **`cycle_comparison`**: só vídeos com `goal = base` (ou NULL, para os
  anteriores à feature), assentados (FR-034). `previous.cycle = 0` é tudo o que
  veio antes do primeiro ciclo. Vídeo sem `cycle` gravado pertence ao ciclo
  mais recente implantado (`deployed`) até o dia em que foi feito. `also_changed` lista `writer_model`,
  `grader_model` e `rendering_strategy` quando diferem entre os dois ciclos:
  com a lista não vazia, a skill diz que o efeito não é atribuível só ao prompt.
  `verdict_possible` exige 20 vídeos de base assentados em cada lado.
- **`share_achieved`**: vídeos com `goal` de experimento ÷ vídeos produzidos,
  desde `share_since`.
- **`days_to_target`**: `(target − settled) ÷ ritmo`, onde ritmo é
  `produced ÷ dias desde a abertura`; `null` com `produced = 0`.
- **`unlabelled`**: `record_id` do período sem linha em `story_labels.csv`.
- **`prompt_drift`**: mesma comparação da verificação 8 de `tuning-check`.
- **`lost_uploads`**: tentativas com falha e registros sem nenhuma tentativa
  bem-sucedida, no período.

Antes do M4, `goal`, `exploration_*` e `cycle` vêm `null` nas linhas, e cada
experimento aberto aparece com `produced: 0`. `slots` e `filled` somam
`run_summaries` desde `share_since` (`null` sem `share_since`); as rodadas
anteriores ao M5 contam 0.

## Onde fica a lógica

`src/capabilities/tuning/` recebe `list[CrossedRow]`, o `ExplorationPlan`, os
`Cycle` e os rótulos, e devolve dataclasses; não abre arquivo nem banco.
`scripts/tuning_data.py` monta as entradas, chama e serializa.
