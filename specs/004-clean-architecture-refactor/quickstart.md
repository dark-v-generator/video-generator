# Quickstart: validação por milestone

**Feature**: 004-clean-architecture-refactor

Cada seção prova o gate de um milestone do [plan.md](./plan.md). Tudo roda no
laptop com `config.dev.yaml` (LLM mock, edge-tts, whisper local), exceto onde
diz "no servidor". Nenhum passo chama modelo pago.

## Pré-requisitos

```bash
uv sync
cp config.dev.yaml config.yaml    # se ainda não houver um config.yaml local
uv run pytest -q                  # linha de base verde antes de começar
```

## §1 — M1: removido e golden gravado

```bash
uv run pytest -q
grep -rEi "prepared_stor|two.?part|image.?story|interactive_bot|main_fastapi" \
  --include='*.py' --include='*.md' --include='*.yaml' --include=Justfile . \
  | grep -v '^./specs/' ; echo "exit=$?"     # esperado: nenhuma linha, exit=1
uv run pytest tests/flows/test_daily_run_golden.py -q
ls tests/fixtures/daily_run_golden.json
just daily-generate 1                       # config.dev.yaml; produz output/daily/story_01.mp4 e story_01.json
python -c "import json;print(json.load(open('output/daily/story_01.json'))['source'])"   # auto
```

Esperado: suíte verde; grep vazio fora de `specs/`; golden existe e passa; o
manifest tem `source: auto` e não tem `part`.

## §2 — M2: história e escrita

```bash
uv run pytest tests/capabilities/test_writing.py tests/flows -q
# prompt em um lugar só: edite src/prompts/story.jinja2 (uma palavra no título da seção VOICE),
# rode uma geração e procure a palavra no log do proxy
just daily-generate 1 2>&1 | grep -c "<palavra editada>"     # ≥ 1
git checkout src/prompts/story.jinja2
# prompt quebrado estoura no boot, nomeando o arquivo
printf '{%% if %%}' >> src/prompts/story.jinja2
uv run python -c "from src.core.container import container; container.llm_proxy()"   # TemplateSyntaxError ... story.jinja2
git checkout src/prompts/story.jinja2
```

## §3 — M3: descoberta isolada

```bash
uv run pytest tests/capabilities/test_discovery.py tests/capabilities/test_import_isolation.py -q
time uv run python -c "import src.capabilities.discovery"                       # < 2 s
uv run python -c "import sys, src.capabilities.discovery; print([m for m in sys.modules if m.startswith(('moviepy','whisper','torch'))])"   # []
uv run python scripts/find_best_stories.py                                        # lista candidatas (precisa de credenciais do Reddit no .env)
```

## §4 — M4: footage isolado

```bash
uv run pytest tests/capabilities/test_footage_youtube.py tests/capabilities/test_footage_local.py -q
mkdir -p /tmp/bg && cp <dois .mp4 quaisquer> /tmp/bg/
# em config.yaml: services.video_config.footage_source: local, local_footage_dir: /tmp/bg
just daily-generate 1 2>&1 | grep -ci "pytube\|youtube"    # 0
```

Esperado: vídeo produzido; nenhuma menção ao YouTube no log. Com
`footage_source: local` e sem `local_footage_dir`, o container falha ao
construir com a chave faltante nomeada.

## §5 — M5: renderização isolada

```bash
uv run pytest tests/capabilities/test_rendering.py -q
# SC-008: história escrita à mão sobre uma pasta local
cat > /tmp/story.json <<'JSON'
{"title": "Minha sogra tentou me expulsar da minha própria casa",
 "parts": ["Ela entrou com a chave que eu nunca dei..."],
 "narrator_gender": "female", "language": "pt-br",
 "origin": {"url": "https://www.reddit.com/r/x/comments/abc/t/", "title": "t", "content": "c",
            "community": "r/x", "author": "u/y", "community_image_url": ""}}
JSON
just render-story /tmp/story.json /tmp/bg              # escreve output/render/part1.mp4
wc -l scripts/render_story.py                          # ≤ 60
```

Esperado: um mp4 com capa, legendas e CTA; o script só usa
`container.renderer()` e o loader de `Story`.

## §6 — M6: fluxo, armazenamento e adaptadores

```bash
uv run pytest tests/flows tests/storage -q               # golden inalterado e verde
wc -l src/flows/daily_run.py                              # ≤ 300
grep -nE "telegram|argparse|os\.path|open\(" src/flows/daily_run.py   # vazio
just daily-generate 1
just daily-publish-only output/daily                      # agenda com o publisher (precisa de sessão TikTok) ou falha com log
```

No servidor, quando disponível:

```bash
just deploy
just prod-daily-generate 1
just prod-status
```

Esperado: `story_01.json` igual em forma ao do §1; `/autopost 1` pelo Telegram
imprime as mesmas mensagens de antes.

## §7 — M7: documentação e dependências

```bash
uv sync && uv run pytest -q
uv run black --check src scripts tests bots
grep -rEi "prepared_stor|two.?part|image.?story|interactive_bot" docs README.md AGENTS.md ; echo "exit=$?"   # exit=1
```

## Critérios de sucesso e onde cada um é verificado

| SC | Verificação |
|----|-------------|
| SC-001 | golden (§1 gravado, §6 comparado) |
| SC-002 | `tests/flows` sem rede (§6) |
| SC-003 | §2 (uma edição, zero código) |
| SC-004 | `tests/capabilities/test_rendering.py::test_three_parts` (§5) + `tests/flows/test_daily_run.py::test_three_part_story_schedules_consecutive_slots` (§6) |
| SC-005 | diff dos PRs M4/M5: registrar `LocalFolderFootageSource` não toca `discovery/`, `writing/`, `storage/`, `flows/` |
| SC-006 | `tests/flows/test_daily_run.py` com `InMemoryRunStore` (§6) |
| SC-007 | §3 |
| SC-008 | §5 |
| SC-009 | §6 (`wc -l`, `grep`) |
| SC-010 | suíte verde em todo PR; testes removidos listados no PR do M1 |
| SC-011 | grep do §1 e do §7 |
| SC-012 | `tests/storage/test_file_store.py::test_old_manifest_loads` (§6) |
