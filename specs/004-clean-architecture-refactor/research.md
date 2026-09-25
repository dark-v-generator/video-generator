# Research: Capacidades isoladas e fluxos de negócio finos

**Feature**: 004-clean-architecture-refactor | **Date**: 2026-09-25

Não há `NEEDS CLARIFICATION` no Technical Context: a stack é a existente e a
única decisão de escopo (o que preservar) foi resolvida no spec. As decisões
abaixo são de desenho, tomadas a partir da leitura do código atual.

## 1. Onde vivem as capacidades: `src/capabilities/<nome>/` com o contrato ao lado

**Decision**: um pacote por capacidade (`discovery`, `writing`, `footage`,
`rendering`, `publishing`), cada um com `contract.py` (um `typing.Protocol` mais
os erros de domínio) e as implementações no mesmo diretório. `src/services/`
deixa de existir; `src/proxies/` continua sendo a borda de I/O.

**Rationale**: o pedido é "cada parte como quase uma lib, com interface". Um
diretório por capacidade torna a fronteira visível no sistema de arquivos e
deixa o contrato no lugar onde quem vai trocar a implementação procura.
`Protocol` em vez de `ABC` porque os fakes dos testes e as implementações futuras
não precisam herdar de nada; a tipagem estrutural basta e não cria dependência
de import da capacidade no teste.

**Alternatives considered**: manter `src/services/` e só reorganizar métodos
(não dá nome às fronteiras; foi o que produziu o serviço de 1096 linhas);
pacotes de topo `src/discovery/`, `src/writing/`... (equivalente, mas mistura
capacidades com `entities`, `proxies`, `core` no mesmo nível e perde o
agrupamento).

## 2. Fluxo como classe injetada, adaptadores como funções finas

**Decision**: `src/flows/daily_run.py` expõe `DailyRun`, construído com as
capacidades, o store, a configuração do dia, um `Progress` (`Callable[[str],
Awaitable[None]]`) e um relógio. O container tem um `providers.Factory`
`daily_run(progress)`. O bot e o CLI só constroem o `Progress` e chamam
`generate`, `publish` ou `run`.

**Rationale**: é o que faz FR-011 (nada de Telegram, terminal ou caminhos no
fluxo) e FR-012 (bot e CLI chamam o mesmo fluxo) serem verificáveis por teste:
um `DailyRun` com fakes roda em memória; um adaptador com um `DailyRun` falso
prova que só traduz. Hoje o CLI importa três funções do módulo do bot, e o bot
lê `config` e `bot_config` como globais de módulo, o que impede testar sem
monkeypatch de módulo inteiro.

**Alternatives considered**: funções de módulo com parâmetros (como hoje, mas em
`flows/`): funciona, mas espalha a injeção por oito funções; usar `@inject` do
dependency-injector no fluxo: acopla o fluxo ao container, que é exatamente o
tipo de detalhe que ele não deve conhecer.

## 3. Equivalência: golden gravado do código antigo

**Decision**: no M1, depois da remoção, um teste roda os três modos do bot antigo
com fakes determinísticos e grava `tests/fixtures/daily_run_golden.json` com a
sequência de mensagens de progresso, os manifests, as linhas do publish log
(sem `created_at`) e as chamadas ao publisher. Do M2 ao M6 o mesmo teste, apontado
para o código novo em M6, compara com o fixture. Regravar exige `--update-golden`
e revisão do diff.

**Rationale**: SC-001 pede equivalência de conjunto de saídas, e a rodada diária
tem muitas mensagens em português cuja ordem e texto o operador vê no Telegram.
Um fixture é a forma mais barata de fixar tudo isso de uma vez e de fazer um
diff legível quando algo muda. O cenário gravado cobre os ramos que existem no
código: roteiro com erro transitório e retry, roteiro bloqueado por filtro,
falha de publicação que pula para a próxima história, generate-only, publish-only.

**Alternatives considered**: asserções por caso (não pegam mudança de ordem nem
de coluna); comparar vídeos renderizados de verdade (lento, não determinístico
pelo anti-fingerprint aleatório, e o que importa para o operador são manifests,
agendamentos e mensagens).

## 4. Modelo de história: lista de partes desde já, produção com uma parte

**Decision**: `Story.parts: list[StoryPart]` com índice 1-based e texto;
`Story.cover_title_for(part)` acrescenta ` - Parte N` (localizado pelo idioma da
história) só quando `len(parts) > 1`. A renderização itera as partes; o fluxo
publica cada `RenderedPart` no slot seguinte ao anterior e só depois de todas
renderizadas; o manifest ganha `part` só quando há mais de uma. O escritor de
produção devolve sempre uma parte.

**Rationale**: FR-009/FR-010 e SC-004. O custo de generalizar é pequeno porque
o bot já tinha esse loop para duas partes (`_WorkItem.parts()`, `_publish_item`);
a refatoração tira o caso especial em vez de reescrevê-lo. A localização do
sufixo era o `PART_SUFFIXES` hardcoded em português; passa a ser uma função por
idioma com o mesmo texto para `pt-br`.

**Alternatives considered**: `Story.text: str` e um `MultiPartStory` depois
(volta a criar dois caminhos, que é o problema a resolver); partes como lista de
`Story` (perde a identidade "uma história, N vídeos" que a meta diária usa).

## 5. Prompts em `src/prompts/` com validação no boot

**Decision**: templates e exemplos saem de `src/proxies/prompts` e
`src/proxies/examples` para `src/prompts/` (`*.jinja2`, `examples/`,
`loader.py`). `loader.validate_all()` compila cada template ao construir o
proxy de LLM no container e falha nomeando o arquivo.

**Rationale**: FR-003 e o edge case "prompt com erro de renderização estoura na
primeira utilização, não no meio da run". Hoje o erro só aparece quando o
método do proxy renderiza, o que na run diária acontece depois da descoberta.
Mover para fora de `proxies/` diz que prompt é conteúdo editorial, não detalhe
do cliente HTTP; `render.py` (a função pura de 003) some junto com o CLI local.

**Alternatives considered**: diretório `prompts/` na raiz do repositório (fora
do pacote `src`, o build wheel de hatch não o incluiria); manter em
`proxies/prompts` e só adicionar a validação (não sinaliza que é editável).

## 6. Classificação de erro do roteiro fica na capacidade de escrita

**Decision**: `ModelStoryWriter` traduz exceções do proxy em
`WriterTransientError` (429, timeout, 502/503, `litellm.RateLimitError`),
`WriterContentBlockedError` (filtros de conteúdo) ou `WriterError`. O fluxo
faz retry com backoff nos transitórios, pula os bloqueados e os demais, com as
mesmas mensagens de hoje.

**Rationale**: FR-011 proíbe detalhe de cliente de modelo no fluxo; hoje o bot
importa `litellm` só para esse `isinstance`. As heurísticas por string continuam
as mesmas para não mudar comportamento.

**Alternatives considered**: hierarquia de erros nos proxies (toca três proxies e o
DSPy para o mesmo ganho); deixar no fluxo (viola FR-011).

## 7. O que o bot do Telegram mantém

**Decision**: o bot mantém `/start`, o envio de URL do Reddit que gera um vídeo e
o devolve no chat (fila de jobs sequencial), `/autopost` e o agendamento diário.
`/find` com botões "Gerar Vídeo", o botão de retry e `/prepared` são removidos.

**Rationale**: o spec preserva só a rodada diária, mas o envio de URL é a forma
que o operador tem de testar uma história no servidor e custa uma dezena de
linhas sobre `writer` + `renderer`. `/find` é uma listagem de descoberta com
~200 linhas de teclado inline e armazenamento de URLs em memória; a mesma
informação sai no log de `/autopost`. O operador pode pedir a volta de `/find`
como um adaptador de 30 linhas sobre `discovery.find_best_stories`.

**Alternatives considered**: manter tudo (o bot continuaria com 600 linhas de
Telegram); remover também o envio de URL (perde o único teste manual no servidor
sem publicar).

## 8. Fonte de footage local como segunda implementação real

**Decision**: `LocalFolderFootageSource` concatena os `.mp4` de um diretório em
ordem aleatória até a duração pedida, aplicando o mesmo anti-fingerprint, e
estoura `FootageShortfallError` com o déficit. Selecionada por
`services.video_config.footage_source: local` + `local_footage_dir`.

**Rationale**: SC-008 pede um fluxo executável pelo operador que renderiza sobre
um arquivo local, e SC-002 pede o renderizador testável sem rede. Uma segunda
implementação real é também a prova de que a fronteira existe (SC-005).

**Alternatives considered**: apenas um fake nos testes (não serve ao operador);
um "modo offline" dentro da fonte do YouTube (mistura duas responsabilidades).

## 9. Store de arquivos reproduz caminhos e formatos atuais

**Decision**: `FileRunStore` escreve `output/<dir>/story_NN.json` com os campos
`video_path`, `title`, `summary`, `post_url`, `source` (e `part` quando há mais
de uma parte) e acrescenta ao CSV `.storage/tiktok_publish_log.csv` com as
mesmas nove colunas na mesma ordem. `scheduled_post_urls()` continua lendo só
as linhas `scheduled`. `TIKTOK_PUBLISH_LOG_PATH` continua sendo respeitado.

**Rationale**: FR-015/FR-019 e o golden. Candidatas descobertas não são
persistidas hoje pela rodada diária; persistir agora acrescentaria um arquivo ao
conjunto de saídas e quebraria SC-001. A fronteira fica pronta para receber
esse método quando a interface web precisar (anotado em `contracts/storage.md`).

**Alternatives considered**: SQLite já nesta feature (fora do escopo por
decisão do spec).

## 10. Ordem dos milestones: remover, depois extrair de baixo para cima

**Decision**: M1 remove e grava o golden; M2 a M5 extraem uma capacidade por PR
apontando o bot antigo para cada uma; M6 substitui o miolo do bot pelo fluxo;
M7 fecha documentação e dependências.

**Rationale**: remover primeiro reduz em ~metade o código a mover e tira as
ramificações que tornariam a extração ambígua (`_WorkItem` com dois estados,
`PreparedStory` vs. `StoryScript`). Extrair de baixo para cima mantém o bot
funcional a cada PR, porque cada capacidade substitui uma chamada existente sem
mudar o que a envolve. O fluxo por último porque é o que muda de forma, e o
golden é o que permite fazer isso com segurança.

**Alternatives considered**: extrair o fluxo primeiro (teria que carregar o
serviço grande como dependência e ser reescrito de novo a cada capacidade);
um único PR (impossível de revisar e sem ponto de deploy intermediário).

## 11. Dependências órfãs

**Decision**: nenhuma dependência sai no M1. No M7, um grep confirma o uso de
cada entrada do `pyproject.toml` e as sem uso saem (candidatas: `coqui-tts`,
`azure-cognitiveservices-speech`, `fastapi`, `uvicorn`, `python-multipart`,
`ollama`, `anthropic`, `google-api-python-client`).

**Rationale**: remover dependência é barato de fazer e caro de errar num servidor
que roda `uv sync --frozen`; deixar para o fim, com a suíte verde como prova, é
mais seguro do que fazer junto com a remoção de código.
