# Gerador de Vídeos Narrados

Cria vídeos verticais narrados a partir de posts do Reddit e os agenda no TikTok. A rodada diária descobre e avalia histórias, escreve o roteiro com LLM, sintetiza a narração, transcreve legendas, compõe o vídeo sobre uma compilação de fundo (do YouTube ou de uma pasta local) com a capa do post e agenda a publicação. Uma história pode ter várias partes: cada parte vira um vídeo, agendado no horário seguinte ao da anterior.

Documentação:

- [docs/quickstart.md](docs/quickstart.md) — instalar e rodar a primeira vez
- [docs/configuration.md](docs/configuration.md) — todas as chaves do `config.yaml` e do `.env`
- [docs/architecture.md](docs/architecture.md) — capacidades, o fluxo diário e como estender

## Instalação

### Pré-requisitos

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Dependências

```bash
uv sync                              # dependências + ferramentas de teste
uv run playwright install chromium   # usado para renderizar a capa
```

## Configuração

Toda a configuração é feita via `config.yaml` na raiz do projeto. Valores omitidos usam os defaults definidos nos modelos Pydantic.

Existem dois templates de configuração prontos para copiar:

```bash
# Dev / teste local (mock LLM, edge-tts, whisper local)
cp config.dev.yaml config.yaml

# Produção (LLM via OpenRouter, ElevenLabs, whisper local)
cp config.prod.yaml config.yaml
```

### Proxies disponíveis

| Chave | Opções | Notas |
|-------|--------|-------|
| `proxies.llm_config.type` | `mock`, `prompt`, `dspy` | `mock` não precisa de API key; `prompt` usa os templates de `src/prompts/` |
| `proxies.speech_config.type` | `edge-tts`, `elevenlabs` | `edge-tts` é gratuito |
| `proxies.transcription_config.type` | `local`, `openai` | `local` usa Whisper (`base`/`small`/`medium`/`large`) |
| `proxies.reddit_config.type` | `json`, `bs4` | a listagem de subreddits sempre usa a API OAuth do Reddit |
| `services.video_config.footage_source` | `youtube`, `local` | `local` lê os `.mp4` de `local_footage_dir`, sem rede |

Os prompts dos modelos ficam em `src/prompts/*.jinja2`: editar o arquivo muda o
texto enviado, sem mexer em código. Um template com erro de sintaxe impede o
processo de subir e o erro nomeia o arquivo.

### Anti-fingerprint do background

Para reduzir a chance de takedown automático em vídeos derivados de
conteúdo do YouTube, o pipeline aplica transformações sutis e
randomizadas em cada compilação, do YouTube ou da pasta local (espelha horizontal, dá um leve zoom,
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
REDDIT_CLIENT_ID=...               # descoberta (app do tipo "script" em reddit.com/prefs/apps)
REDDIT_CLIENT_SECRET=...
OPENROUTER_API_KEY=...             # llm provider: openrouter e o agente do TikTok
TELEGRAM_SATISFYING_BOT_TOKEN=...  # bot do Telegram
GOOGLE_API_KEY=...                 # se llm provider: google
OPENAI_API_KEY=...                 # se llm provider: openai ou transcription: openai
ELEVENLABS_API_KEY=...             # se speech: elevenlabs
```

A lista completa, com `TIKTOK_EMAIL`/`TIKTOK_PASSWORD` e o PO token do YouTube,
está em [docs/configuration.md](docs/configuration.md#secrets-env).

## Scripts

### Rodada diária (descobrir → gerar → agendar)

```bash
just daily-generate 1                 # só gera; grava output/daily/story_NN.mp4 + story_NN.json
just daily-publish-only output/daily  # agenda o que já foi gerado
just daily-publish 3                  # rodada completa
```

No servidor, o bot do Telegram (`python -m bots.satisfying_bot`) roda a mesma
rodada todo dia no horário configurado e aceita `/autopost [n]`; mandar a URL de
um post do Reddit para o bot devolve a narração e o vídeo daquela história. Os
`just prod-daily-*` rodam os mesmos comandos no servidor.

### Histórico e desempenho

Toda rodada grava um histórico em `.storage/history.sqlite` (no servidor), ao lado
dos manifests e do CSV de publicação, que continuam como antes:

- **por vídeo**: título, post do Reddit, parte, duração; upvotes e comentários do
  post na descoberta; a nota do modelo e as sub-notas; a receita que o produziu
  (versão do prompt `story.jinja2`, modelos, estratégia de renderização, voz,
  taxa de fala); as hashtags;
- **por tentativa de publicação**: a mesma linha do CSV (agendado ou falha, slot,
  erro), sem substituir as anteriores;
- **por rodada**: modo, pedidos, candidatas, produzidos, agendados, pulos por motivo.

Só resultados entram; o raciocínio do modelo e os prompts renderizados não.

**Importar o passado (uma vez).** Os vídeos de antes do histórico entram a partir
do CSV e dos manifests, sem nota nem números do Reddit. Rodar de novo não duplica.

```bash
just prod-import-history
```

**Coletar o desempenho.** A coleta lê o TikTok Studio com a sessão do publisher,
casa cada vídeo com o seu registro pela legenda e pelo horário agendado, e grava
views, likes, comentários, shares, saves, watch médio e % assistido até o fim, mais
os upvotes do post no Reddit agora. Rode alguns dias depois de publicar e repita
para acompanhar: cada coleta acrescenta um retrato datado, sem mexer nos anteriores.

```bash
just prod-collect-performance      # lookback_days do config (30)
just prod-collect-performance 60   # últimos 60 dias
```

Pelo Telegram: `/collect` ou `/collect 60`. A coleta termina com
"K casados, U sem par, A ambíguos" e uma linha por vídeo sem par ou ambíguo, com
legenda, data e id do TikTok. Para resolver, diga a qual registro o vídeo pertence;
a coleta seguinte já casa pelo id:

```bash
just prod-collect-performance "--assign 7678762304107810068 322"
```

A coleta e a publicação usam o mesmo perfil do Chromium e **nunca podem rodar ao
mesmo tempo**. O bot já recusa ("Já existe um fluxo em andamento."); pela linha de
comando, não comece uma coleta com uma publicação em andamento.

**Ver o cruzamento.** No laptop, puxe o histórico do servidor (só servidor →
laptop) e peça a visão cruzada: uma linha por vídeo com nota, upvotes na
descoberta e agora, views, likes, comentários, shares, saves, watch médio,
% até o fim, versão do prompt e modelo. Vídeo ainda sem coleta aparece com essas
colunas vazias.

```bash
just sync-history
just report --sort grade_overall:desc                    # nota alta e poucas views aparecem no topo
just report --sort latest_views                          # os menos vistos primeiro
just report --filter story_prompt_version=42072ca8893c   # só uma versão do prompt
just report --since 2026-09-01 --csv /tmp/cruzamento.csv # todas as colunas, para planilha
just report --columns                                    # colunas de --sort e --filter
```

`--sort COLUNA:desc` inverte a ordem; vazios ficam no fim nos dois sentidos.
`--filter` é repetível e compara igualdade. As colunas e a estrutura do banco
estão em [docs/architecture.md](docs/architecture.md#the-history-and-the-crossed-view).

### Renderizar uma história escrita à mão

```bash
just render-story story.json pasta/com/clipes   # grava output/render/part1.mp4, part2.mp4, ...
```

`story.json` tem `title`, `parts` (uma string por parte), `narrator_gender`,
`language` e `origin`; o formato completo está em
[docs/quickstart.md](docs/quickstart.md#render-a-story-by-hand). Usa só o
renderizador configurado e os clipes da pasta: sem Reddit, sem LLM escrevendo,
sem YouTube.

### Diagnóstico da descoberta

```bash
uv run python scripts/find_best_stories.py --top-per-sub 2   # ranking das histórias do dia
uv run python scripts/evaluate_story.py <url>                # nota de um post
uv run python scripts/list_posts.py --sub pettyrevenge        # posts recentes (sem --sub: todos do config)
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

## Comandos úteis

```bash
# Adicionar dependência
uv add package-name

# Atualizar dependências
uv lock --upgrade

# Executar testes (sem rede e sem modelo)
uv run pytest

# Formatar
just fmt

# Ver ajuda da rodada diária
uv run python scripts/daily_auto_publish.py --help
```
