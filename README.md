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

Existem dois templates de configuração prontos para copiar:

```bash
# Dev / teste local (mock LLM, mock images, edge-tts, whisper local)
cp config.dev.yaml config.yaml

# Produção (Leonardo Flux Dev, ElevenLabs, Google Gemma, whisper local)
cp config.prod.yaml config.yaml
```

### Proxies disponíveis

| Proxy | Opções | Notas |
|-------|--------|-------|
| `llm_config.type` | `mock`, `prompt`, `dspy` | `mock` não precisa de API key |
| `image_generation_config.type` | `mock`, `local`, `leonardo` | `leonardo` usa Flux Dev por padrão |
| `speech_config.type` | `edge-tts`, `elevenlabs` | `edge-tts` é gratuito |
| `transcription_config.type` | `local`, `openai` | `local` usa Whisper (`base`/`small`/`medium`/`large`) |

### Anti-fingerprint do background YouTube

Para reduzir a chance de takedown automático em vídeos derivados de
conteúdo do YouTube, o pipeline aplica transformações sutis e
randomizadas em cada compilação (espelha horizontal, dá um leve zoom,
muda brilho/contraste/matiz dentro de uma faixa pequena e altera
ligeiramente a velocidade). Cada execução produz um conjunto diferente
de parâmetros, então duas saídas nunca batem com o mesmo hash
perceptual.

Os valores padrão (definidos em `config.*.yaml` em
`services.video_config.anti_fingerprint`) são conservadores —
imperceptíveis para humanos, mas o suficiente para quebrar matching
fuzzy. Edite ou desligue por completo se quiser:

```yaml
services:
  video_config:
    anti_fingerprint:
      enabled: true
      mirror: true            # espelha horizontalmente
      zoom: 1.06              # corta ~5% das bordas
      brightness_delta: 0.04  # ±4% de brilho
      contrast_delta: 8.0     # amplitude de LumContrast
      hue_shift_degrees: 8.0  # ±8° de rotação de matiz
      speed_delta: 0.02       # ±2% de velocidade
```

### Variáveis de ambiente (produção)

Crie um arquivo `.env` na raiz ou exporte as variáveis:

```
GOOGLE_API_KEY=...        # se llm provider: google
OPENAI_API_KEY=...        # se llm provider: openai ou transcription: openai
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

### Auto-publicar / agendar no TikTok (AI agent — server-only)

> O publisher roda **somente no servidor de produção** (`gustavo@192.168.1.100`).
> Os cookies + fingerprint do dispositivo ficam exclusivamente no servidor para
> evitar inconsistência entre máquinas (TikTok faz fingerprint de canvas/WebGL/UA
> e quebraria a sessão se ela viajasse Mac↔Linux).

#### Setup inicial (uma vez)

1. **Push do código + deps + Xvfb + x11vnc + patchright Chromium para o servidor**:

   ```bash
   just deploy            # rsync + uv sync + restart do bot
   just prod-tiktok-setup # apt install xvfb x11vnc + patchright install chromium
   ```

   (Esse `apt install` pede a senha do `sudo` uma única vez.)

2. **Bootstrap do login via VNC** — funciona em qualquer máquina (Mac, Linux,
   Windows). O Chromium roda no servidor; você o vê via VNC pelo SSH tunnel.
   Sem XQuartz, sem login extra. macOS usa o cliente VNC nativo.

   ```bash
   just prod-tiktok-bootstrap-vnc output/part1.mp4
   ```

   No Mac, o cliente VNC abre automaticamente em ~8s. Em qualquer outro SO,
   abra `vnc://localhost:5900` no seu cliente VNC favorito (sem senha,
   conexão restrita ao tunnel SSH). Resolva o slider captcha quando aparecer
   — o agente espera até 2 minutos. Quando terminar, a sessão TikTok fica
   persistida em `~/video-generator/.storage/tiktok_cookies_userdata/` no
   servidor.

   > Alternativa para quem já tem XQuartz: `just prod-tiktok-bootstrap-x11`
   > (forwarding via X11). Usa a mesma lógica, só muda o transporte da janela.

#### Uso diário (sem display)

Após o bootstrap, posts/agendamentos rodam direto via SSH usando Xvfb (display
virtual em RAM) — não precisa de janela, não precisa de XQuartz, não precisa
do Mac aberto:

```bash
# Agendar para daqui a 6 horas
just prod-tiktok-publish output/part1.mp4 "--schedule-in 6h --hashtag fyp"

# Postar agora
just prod-tiktok-publish output/part1.mp4 "--description 'Já no ar' --hashtag teste"
```

Ou direto por SSH para o cron:

```bash
ssh gustavo@192.168.1.100 \
  "cd video-generator && xvfb-run -a uv run python scripts/publish_tiktok.py output/part1.mp4 --schedule-in 6h"
```

#### Manutenção

```bash
just prod-tiktok-status        # confere se a sessão está salva
just prod-tiktok-reset         # apaga cookies (forçar re-login)
just prod-tiktok-bootstrap-vnc # re-bootstrap após reset ou se TikTok forçar re-auth
```

#### Memória entre runs (lessons file)

Cada execução do agente é capturada em
`.storage/tiktok_runs/<timestamp>-<outcome>.json` no servidor. Logo após
capturar, um pequeno LLM "reflector" lê o histórico, extrai 0–5 lições
acionáveis (rótulos pt-BR que funcionaram, sequências erradas, anti-padrões)
e mescla em `.storage/tiktok_learnings.md`. Na próxima rodada, o conteúdo
desse arquivo entra no início do prompt da task — então o agente começa
cada run mais esperto que o anterior.

O arquivo é seedado com rótulos pt-BR já conhecidos (login, captcha,
"Programar", etc.) a partir de `assets/tiktok_seed_lessons.md` na primeira
execução em servidor limpo.

Para inspecionar/editar localmente:

```bash
just sync-tiktok-runs       # puxa runs + lessons do servidor (read-only)
just tiktok-last            # mostra o histórico do último run
just tiktok-lessons         # mostra as lessons acumuladas
$EDITOR .storage/tiktok_learnings.md  # edita à mão (poda lições ruins)
just push-tiktok-learnings  # devolve as edições para o servidor
```

`sync-tiktok-runs` roda automaticamente ao final de `prod-tiktok-publish`
e do `prod-tiktok-bootstrap-vnc`, então em fluxo normal o `.storage/` local
fica sempre fresco — não precisa lembrar de sincronizar.

#### Como funciona

Publica (ou agenda) um vídeo já renderizado direto no TikTok usando um
agente de IA no `browser-use`, com Chromium stealth via `patchright`
+ scripts do `playwright-stealth`. As credenciais ficam apenas em
`.env` (no servidor) e a sessão (cookies + localStorage + IndexedDB)
é persistida no `user_data_dir` do Chromium para que o login só
aconteça uma vez.

Segredos em `.env` (apenas credenciais):

```bash
TIKTOK_EMAIL=...
TIKTOK_PASSWORD=...
OPENROUTER_API_KEY=...
```

Configuração não-secreta em `config.yaml` (sob `proxies.tiktok_publisher_config`):

```yaml
proxies:
  tiktok_publisher_config:
    agent_model: deepseek/deepseek-v4-flash    # modelo OpenRouter
    cookies_path: .storage/tiktok_cookies.json # cookies persistidos
    headless: false                            # headful é menos detectável
    use_vision: false                          # ative se trocar p/ modelo com visão
    max_steps: 60
```

Qualquer setting do bloco acima pode ser sobrescrito pelo CLI
(`--model`, `--cookies-path`, `--headless`, `--use-vision`, `--max-steps`).

#### Postar agora

```bash
uv run python scripts/publish_tiktok.py output/part1.mp4 \
    --description "Texto da legenda" \
    --hashtag fyp --hashtag reddit
```

#### Agendar (TikTok Studio nativo)

O TikTok Studio permite agendar posts em até **10 dias** no futuro
(contas Creator/Business apenas, desktop only). Use `--schedule-at`
para um horário absoluto ou `--schedule-in` para um delta:

```bash
# Agendar para amanhã às 18:00 (horário local)
uv run python scripts/publish_tiktok.py output/part1.mp4 \
    --description "Texto da legenda" \
    --schedule-at "2026-05-05T18:00"

# Agendar daqui a 6 horas
uv run python scripts/publish_tiktok.py output/part1.mp4 \
    --schedule-in 6h

# Agendar para daqui a 1 dia e 12 horas
uv run python scripts/publish_tiktok.py output/part1.mp4 \
    --schedule-in 1d12h
```

O CLI valida a janela do TikTok antes de abrir o navegador: agendar
para menos de ~25 min ou mais de 10 dias falha cedo, sem gastar tokens.

#### Flags

| Flag | Descrição | Default |
|------|-----------|---------|
| `--description` | Legenda do post (digitada literalmente) | "" |
| `--hashtag` | Adiciona uma hashtag ao final (pode repetir) | — |
| `--schedule-at` | Horário absoluto ISO-8601 (`2026-05-05T18:00`) | — |
| `--schedule-in` | Delta a partir de agora (`30m`, `6h`, `2d`, `1d12h`) | — |
| `--cookies-path` | Onde salvar/ler os cookies persistidos | `.storage/tiktok_cookies.json` |
| `--headless` | Roda o Chromium sem janela | off (headful é menos detectável) |
| `--max-steps` | Limite de passos do agente | `60` |
| `--use-vision` | Envia screenshots ao LLM (custos sobem) | off |
| `--model` | Sobrescreve o modelo do agente | `$TIKTOK_AGENT_MODEL` |

`--schedule-at` e `--schedule-in` são mutuamente exclusivos.

#### Notas importantes

* O modelo padrão (`deepseek/deepseek-v4-flash`) é text-only e
  cumpre o fluxo determinístico (login + upload + caption + Schedule),
  mas **não resolve captchas**. Se o TikTok exibir um captcha de
  imagem, rode com `--use-vision` e troque para um modelo com visão
  (ex.: `google/gemini-2.5-flash-lite`), ou rode com janela visível
  (default) e resolva manualmente — uma vez resolvido, os cookies
  ficam salvos para a próxima execução.
* O agente recebe os domínios `*.tiktok.com` como allow-list, então
  ele não consegue navegar para fora do TikTok com as credenciais.
* O agendamento nativo só funciona em contas Creator ou Business. Em
  contas pessoais o botão "Schedule" não aparece — o script reporta
  o que vê e para. Faça o switch da conta uma única vez no
  TikTok Studio antes de usar `--schedule-*`.

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
