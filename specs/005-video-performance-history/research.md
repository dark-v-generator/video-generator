# Research: Histórico de desempenho dos vídeos

**Feature**: 005-video-performance-history | **Date**: 2026-09-28

Nenhum `NEEDS CLARIFICATION` ficou no Technical Context; as decisões abaixo
fixam o que a spec deixou para o planejamento e registram as alternativas.

## 1. Onde o histórico vive: SQLite atrás de um `HistoryStore` próprio

**Decisão**: `sqlite3` da biblioteca padrão, um arquivo em
`.storage/history.sqlite` (`HISTORY_DB_PATH` sobrescreve), esquema criado na
primeira abertura, uma transação por operação do contrato. Um Protocol novo,
`HistoryStore`, ao lado do `RunStore` existente.

**Racional**: a clarificação escolheu SQLite. O modelo é relacional (registro →
snapshots do Reddit, tentativas, snapshots de desempenho) e a visão cruzada é uma
consulta com `JOIN`, ordenação e filtro; em SQL isso é uma função, em JSON seria
um agregador em Python. Um arquivo só se sincroniza com `rsync` como o resto de
`.storage/`. `sqlite3` já vem com o Python, então a promessa "nenhuma dependência
nova" da feature 004 se mantém.

**Alternativas**: estender `RunStore` (rejeitado: o golden fixa o CSV e os
manifests, e o `FileRunStore` teria de crescer um histórico em arquivos ou o
SQLite teria de imitar o CSV); um ORM (SQLAlchemy, rejeitado: dependência nova
para seis tabelas e meia dúzia de consultas); JSON por registro (rejeitado pela
clarificação).

**Detalhes que importam**: `PRAGMA journal_mode=WAL` para o script de relatório
poder ler enquanto a rodada escreve; `foreign_keys=ON`; timestamps em ISO 8601
UTC como texto; dinheiro nenhum, então inteiros e reais bastam. A cópia do
laptop é somente leitura na prática (o `sync-history` puxa, nunca empurra).

## 2. Como ler o TikTok Studio: patchright sobre o perfil do publisher, interceptando JSON

**Decisão**: o proxy abre um contexto persistente do Chromium `patchright`
apontando para o mesmo `user_data_dir` do publisher
(`.storage/tiktok_cookies_userdata/`, derivado de `cookies_path`), injeta o
script do `playwright-stealth` como o publisher já faz, navega até o TikTok
Studio e **intercepta as respostas JSON** que a página busca para montar a lista
de conteúdo e a analytics por vídeo, em vez de raspar o DOM. Sem `browser-use`,
sem LLM, sem cliques além de navegar e rolar.

**Racional**: a clarificação pediu leitura determinística com a sessão que já
existe. O DOM do Studio muda com frequência e é localizado (a conta está em
pt-BR); o JSON que alimenta a página muda menos e traz os números crus. Toda a
literatura de scraping de TikTok em 2026 converge para "abrir a página num
navegador real e capturar as respostas da API interna" (Scrapfly, HasData,
ScrapingBee). O perfil persistente evita novo login e novo captcha, que só se
resolvem por VNC no servidor.

**O que se sabe e o que a sondagem fixa**: os objetos de post do TikTok expõem
`id`, `desc`, `createTime` e um bloco de estatísticas; nos endpoints públicos o
bloco moderno é `statsV2` com `playCount`, `diggCount`, `commentCount`,
`shareCount`, `collectCount` como strings (o `stats` legado estoura em 32 bits).
Retenção (tempo médio assistido, % que assistiu até o fim) só aparece na
analytics por vídeo do Studio. Os **caminhos exatos dos endpoints do Studio e os
nomes dos campos de retenção não são verificáveis fora de uma sessão logada**,
por isso o M3 começa pelo `scripts/tiktok_studio_probe.py`: ele grava todas as
respostas JSON interceptadas e o parser é escrito contra esse dump, que vira o
fixture redigido dos testes. Quando o Studio mudar, roda-se a sondagem de novo e
o parser é ajustado contra o novo fixture; o proxy estoura nomeando o campo
ausente em vez de gravar zeros.

**Alternativas**: API oficial do TikTok (rejeitada na clarificação: exige app e
aprovação, e a Display API não dá retenção); export manual do Studio (rejeitado
como primeira implementação, fica como possível segundo `PerformanceSource`);
agente `browser-use` como no publisher (rejeitado: não determinístico, gasta
tokens, e o log de publicações mostra que ele falha por "acabaram os passos");
raspar o DOM (rejeitado: frágil e localizado).

**Restrição operacional**: um perfil de Chromium só pode estar aberto por um
processo. O bot roda a coleta sob o mesmo `RunLock` da rodada; na linha de
comando, `patchright` falha ao abrir um perfil em uso e a coleta estoura cedo.
Roda no servidor sob `xvfb-run`, headful como o publisher (menos detectável).

## 3. Casar um vídeo do TikTok com o registro: legenda e horário

**Decisão**: a legenda publicada é `title` mais hashtags
(`_format_description`). O casamento normaliza a `desc` do TikTok (remove
hashtags finais, colapsa espaços, `casefold`) e compara com o `title` do
registro normalizado do mesmo jeito. Um só candidato: casado. Mais de um (mesma
história republicada após falha): fica o cujo `scheduled_at` da última
tentativa `scheduled` está a menos de 12 h do `createTime` do TikTok; se ainda
sobrar mais de um, `ambiguous`. Sem candidato: `unmatched`. O `tiktok_video_id`
é gravado no registro e nas coletas seguintes casa direto por id. `--assign`
resolve à mão.

**Racional**: a clarificação rejeitou marcador na legenda. Com três vídeos por
dia e títulos distintos a colisão só acontece por republicação, e aí o horário
resolve. A regra é pequena e pura (`capabilities/performance/matching.py`), sem
I/O, testável com listas.

**Alternativas**: só horário (rejeitado: o TikTok publica no slot com minutos de
diferença, e dois vídeos podem cair perto); fuzzy matching de texto (rejeitado:
o título é copiado literalmente, igualdade após normalização basta; quando não
bate, é melhor reportar).

## 4. Receita de produção: fingerprint do prompt e valores da config

**Decisão**: `prompts.fingerprint(name)` = sha256 do conteúdo do arquivo
`.jinja2`, 12 hex. A receita leva `story_prompt_version` (`story.jinja2`),
`grading_prompt_version` (`evaluate_story.jinja2`), `writer_model`
(`provider/model` do `history_adaptation_llm_config`, senão do `llm_config`),
`grader_model` (`llm_config`), `rendering_strategy`, `speech_provider` (`type`),
`speech_rate` (`default_rate` do edge-tts, `None` no ElevenLabs), `voice_id`
(resolvido por história via `ISpeechProxy.voice_id(gender, language)`),
`language`. Hashtags ficam na tentativa de publicação e no registro quando a
primeira tentativa acontece.

**Racional**: FR-005 e US4 pedem que dois vídeos feitos com prompts diferentes
sejam distinguíveis sem o operador nomear versões; um hash do arquivo faz isso
de graça. Os demais valores já estão em `MainConfig`; o container é o único
lugar que conhece a config inteira, então monta a receita lá.

**Alternativas**: versionar prompts com um campo `version:` no template
(rejeitado: exige disciplina e esquece); hash do prompt renderizado (rejeitado:
muda a cada história porque inclui o texto do post).

## 5. Duração e voz efetiva: pequenas extensões de contratos existentes

**Decisão**: `RenderedPart.duration_seconds` preenchido pelo renderizador (o
`VideoComposer` já conhece `total_duration`); `ISpeechProxy.voice_id(gender,
language)` devolve o id que `generate_speech` usaria.

**Racional**: o fluxo não pode abrir o mp4 (traria moviepy para dentro), e a
regra "voz padrão por idioma e gênero" vive no proxy de fala. Registrado em
Complexity Tracking do plano.

## 6. Sinais do Reddit: dois tipos de snapshot na mesma tabela

**Decisão**: `reddit_snapshots` guarda `source` (`discovery` | `collection`),
`taken_at`, `score`, `num_comments`, `upvote_ratio`, `available`. A descoberta
grava o primeiro a partir do `RedditPost` já em mãos; cada coleta grava um por
registro tocado via `StoryDiscovery.signals(url)`, que usa
`IRedditProxy.get_reddit_post` (o proxy JSON já devolve `score`, `num_comments`,
`upvote_ratio`). Post removido: `available=False` e números `NULL`.

**Racional**: a clarificação pediu snapshots datados como os do TikTok; uma
tabela com `source` evita duas tabelas iguais.

## 7. Importar o passado: linhas do CSV e manifests, sem reavaliar

**Decisão**: `scripts/import_history.py` lê o CSV e os manifests, cria
`video_records` com `imported=True` e o que existe (título, post_url, parte,
video_path, summary), e uma `publish_attempts` por linha do CSV. Chave natural
`(video_path, created_at)` torna a importação idempotente. Não busca o Reddit
(os posts de meses atrás não trariam o número da descoberta) e não avalia.

**Racional**: FR-017 e o edge case sobre linhas de teste. A exclusão de posts já
agendados continua lendo o CSV (golden), então a importação não precisa ser
perfeita para a rodada funcionar; ela serve à visão cruzada.

## 8. Onde cada coisa roda

- Rodada diária e coleta: no servidor (sessão do TikTok, Chromium, Xvfb).
- Visão cruzada: no laptop, sobre a cópia puxada por `just sync-history`
  (memória do projeto: o laptop é para revisão, não para gerar). O script também
  roda no servidor se preciso.
- Importação: no servidor (`just prod-import-history`), onde está o CSV real; a
  cópia local do CSV tem quase só linhas de teste.

Fontes consultadas para o §2: [Scrapfly: How to scrape TikTok (2026)](https://scrapfly.io/blog/posts/how-to-scrape-tiktok-python-json),
[HasData: Scrape TikTok with Python (2026)](https://hasdata.com/blog/tiktok-scraping-python),
[ScrapingBee: Scrape TikTok profile stats and videos](https://www.scrapingbee.com/blog/how-to-scrape-tiktok/),
[Retensis: TikTok retention benchmarks 2026](https://retensis.com/blog/tiktok-retention-rate-benchmarks-2026),
[Kleene: TikTok analytics in 2026](https://kleene.ai/blog/tiktok-analytics-1).
