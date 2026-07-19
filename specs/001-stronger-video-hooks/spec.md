# Feature Specification: Ganchos mais fortes nos vídeos de história

**Feature Branch**: `001-stronger-video-hooks`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Melhorar o gancho (hook) dos vídeos de história do TikTok gerados pelo projeto, para aumentar a retenção nos primeiros segundos e o watch-through."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Título lidera pela promessa e pelo conflito (Priority: P1)

Como operador do canal, quero que o roteiro gerado a partir de um post do Reddit traga um
título exibido na imagem de capa que já entrega a promessa e os stakes da história — com
uma vítima ou protagonista por quem torcer e um antagonista ou injustiça claros — para que
o espectador sinta, nos primeiros segundos, que vale a pena parar o scroll e assistir. O
título **não é narrado**: ele aparece na capa (lido pelo espectador) enquanto a narração já
começa direto na história, para não gastar os primeiros segundos lendo o título em voz alta.

**Why this priority**: O título exibido na imagem de capa é o primeiro ponto de contato
visual e o maior determinante de retenção inicial. Como não é mais narrado, os primeiros
segundos de áudio já são a história — o gancho visual (capa) e o gancho narrado (abertura da
Parte 1) trabalham juntos. É a mudança de maior impacto e a que sustenta o objetivo central
da feature (parar o scroll). Entrega valor sozinha, mesmo sem as demais histórias.

**Independent Test**: Gerar roteiros para uma amostra de posts do Reddit e verificar que
cada título nomeia (implícita ou explicitamente) alguém por quem torcer, um
antagonista/injustiça e um dano ou conflito concreto, sem revelar o desfecho — comparando
com os títulos vagos produzidos antes.

**Acceptance Scenarios**:

1. **Given** um post do Reddit com vítima e antagonista identificáveis, **When** o roteiro
   é gerado, **Then** o título lidera pela promessa/tensão, deixa claro quem sofre o dano e
   quem/o que o causa, e cria uma lacuna que só fecha assistindo.
2. **Given** uma história cuja injustiça pode ser cristalizada numa fala curta e
   revoltante, **When** o roteiro é gerado, **Then** o título pode carregar essa fala como
   citação, sem entregar o desfecho.
3. **Given** qualquer post, **When** o título é gerado, **Then** ele soa como algo que uma
   pessoa diria em voz alta (tom natural e falado), não como manchete escrita.

---

### User Story 2 - Parte 1 abre direto no conflito (Priority: P2)

Como operador do canal, quero que a narração da Parte 1 comece direto no conflito ou nos
stakes — já na primeira palavra falada, sem título, sem marcador "Parte 1." e sem preâmbulo
ou cena lenta de contextualização — para que a energia do gancho da capa se mantenha e o
espectador não desista nos primeiros segundos da narração.

**Why this priority**: Um título forte perde efeito se a narração começa devagar. Reforça
a retenção inicial imediatamente após o gancho, mas depende do título já estar forte (P1).

**Independent Test**: Gerar roteiros para uma amostra e verificar que a primeira palavra
narrada da Parte 1 entra no conflito/tensão (sem título nem marcador falado) em vez de
introdução lenta.

**Acceptance Scenarios**:

1. **Given** um post do Reddit, **When** o roteiro é gerado, **Then** a narração da Parte 1
   abre no conflito ou nos stakes já na primeira palavra, sem título, sem marcador "Parte 1."
   e sem preâmbulo.
2. **Given** a abertura da Parte 1, **When** avaliada, **Then** ela dá continuidade natural
   à promessa feita pelo título da capa, sem repetir o desfecho nem antecipar o clímax.

---

### User Story 3 - Vale em múltiplos idiomas com fraseado natural (Priority: P3)

Como operador do canal que publica em pt-br e em outros idiomas alvo, quero que a lógica de
gancho forte funcione em qualquer idioma alvo com fraseado local natural, para manter a
retenção sem soar como tradução literal.

**Why this priority**: Amplia o alcance da melhoria para todos os idiomas do canal, mas é
uma generalização do comportamento já definido em P1/P2.

**Independent Test**: Gerar roteiros para o mesmo conjunto de posts em pelo menos dois
idiomas alvo e verificar que os títulos e aberturas mantêm a anatomia do gancho forte com
fraseado idiomático local.

**Acceptance Scenarios**:

1. **Given** um idioma alvo diferente de pt-br, **When** o roteiro é gerado, **Then** o
   título e a abertura seguem a mesma anatomia de gancho forte com fraseado natural do
   idioma.

---

### Edge Cases

- **História sem antagonista humano claro** (ex.: infortúnio, doença, sistema/instituição):
  o gancho deve liderar pelo dano ou injustiça concreta e por quem torcer, sem inventar um
  vilão que não existe na história (não é clickbait mentiroso).
- **História sem uma fala citável revoltante**: a frase-citação é opcional; o gancho ainda
  deve ser forte pelos demais elementos (vítima, dano concreto, promessa de virada).
- **Post fraco ou sem stakes reais**: o gancho não deve prometer um payoff que a história
  não entrega; a promessa fica limitada ao que a história de fato sustenta.
- **Elementos do gancho colidem com a política de palavras fortes** (ex.: dano envolve
  violência/morte): o gancho preserva a intensidade por contexto e eufemismo, sem usar
  palavras proibidas no título nem na narração.
- **Desfecho tentador de antecipar**: mesmo com um gancho mais forte, o clímax permanece na
  Parte 2 e o título não revela o resultado.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O título gerado MUST liderar pela promessa, pelos stakes ou pela tensão
  central da história, deixando claro quem sofre o dano/por quem torcer e quem ou o que
  provoca o conflito, criando uma lacuna que só se fecha assistindo.
- **FR-002**: O título MUST ir direto ao ponto, sem aquecimento ou setup vago, e MUST NOT
  revelar o desfecho da história.
- **FR-003**: O título MUST soar como fala natural e coloquial (algo que uma pessoa diria em
  voz alta), não como manchete escrita.
- **FR-004**: Quando a história oferecer uma injustiça cristalizável, o título MAY carregar
  uma frase curta e revoltante como citação; a citação é opcional e não deve ser forçada.
- **FR-005**: A abertura da Parte 1 MUST entrar direto no conflito ou nos stakes já na
  primeira palavra narrada, sem preâmbulo ou contextualização lenta, dando continuidade à
  promessa do título da capa.
- **FR-006**: A promessa do gancho MUST corresponder ao que a história realmente entrega —
  não pode ser clickbait mentiroso.
- **FR-007**: O comportamento de gancho forte MUST valer para pt-br e demais idiomas alvo,
  sempre com fraseado local natural.
- **FR-008**: A orientação de gancho MUST ser expressa por racional (o porquê do
  comportamento), não por regras casuísticas do tipo "quando o título contiver X faça Y", e
  sem usar CAPS para dar ênfase, permitindo que o agente generalize.
- **FR-009**: Os exemplos few-shot MUST ser consistentes com a instrução de gancho forte —
  nenhum exemplo pode contradizer a anatomia definida.
- **FR-010**: O título e toda a narração MUST continuar respeitando a política de palavras
  fortes (eufemismos para moderação de TTS/TikTok); nenhuma palavra proibida pode aparecer.
- **FR-011**: O contrato de saída do LLM MUST manter as chaves `title`, `narrator_gender`,
  `part1`, `part2`. O campo `title` continua sendo gerado (é o gancho exibido na capa), mas
  `part1`/`part2` deixam de começar por `"<title>. Parte N."`.
- **FR-012**: A estrutura de duas partes MUST ser preservada: o clímax sempre na Parte 2 e o
  CTA de "curta e siga para a parte 2" ao fim da Parte 1.
- **FR-013**: Os caminhos paralelos de geração de roteiro (single-part e o caminho DSPy)
  MUST refletir a mesma orientação de gancho quando produzirem título e abertura, para não
  divergirem do caminho ativo.
- **FR-014**: O título e o marcador "Parte N." MUST NOT ser narrados. A narração de
  `part1`/`part2` começa direto na história; o título e "Parte N." são exibidos apenas na
  imagem de capa. O contrato de saída não inclui mais o título/marcador embutido na narração.
- **FR-015**: A imagem de capa MUST ser exibida como sobreposição nos primeiros segundos do
  vídeo enquanto a história já é narrada por baixo, por uma duração curta configurável
  (`video_config.cover_duration`), em vez de durar o tempo de narração do título.

### Key Entities *(include if feature involves data)*

- **Roteiro de história (script)**: unidade gerada a partir de um post do Reddit, composta
  por `title`, `narrator_gender`, `part1` e `part2`. O título (exibido na capa) e a abertura
  narrada da Parte 1 são os elementos afetados por esta feature; `part1`/`part2` não embutem
  mais o título nem o marcador.
- **Gancho (hook)**: combinação do título **exibido na capa** (gancho visual) e da abertura
  **narrada** da Parte 1 (gancho de áudio); sua força é medida pelos elementos da anatomia
  (vítima/protagonista, antagonista/injustiça, dano concreto, frase-citação opcional,
  promessa de virada).
- **Post do Reddit (fonte)**: entrada com título e texto originais a partir da qual o gancho
  é derivado; define quais elementos da anatomia estão de fato disponíveis.
- **Avaliação de gancho**: nota "Força do Gancho" (0–100) atribuída por uma avaliação
  existente, usada como sinal comparativo de melhoria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Numa amostra de posts do Reddit, a nota média de "Força do Gancho" (0–100) da
  avaliação existente melhora em relação à geração com o prompt anterior.
- **SC-002**: Em pelo menos 80% dos roteiros de uma amostra, o título nomeia (implícita ou
  explicitamente) alguém por quem torcer e um antagonista/injustiça, e não revela o desfecho.
- **SC-003**: Em pelo menos 80% dos roteiros de uma amostra, a primeira frase da Parte 1
  entra no conflito ou nos stakes, sem preâmbulo.
- **SC-004**: Nenhuma palavra proibida aparece no título ou na narração em 100% dos roteiros
  gerados na amostra.
- **SC-005**: 100% dos roteiros da amostra mantêm as chaves do contrato (`title`,
  `narrator_gender`, `part1`, `part2`) e a estrutura de duas partes com clímax na Parte 2 e
  CTA ao fim da Parte 1; e 100% têm `part1`/`part2` que **não** começam pelo título nem pelo
  marcador "Parte N." (título/marcador ficam só na capa).
- **SC-006**: A melhoria se sustenta em pelo menos dois idiomas alvo (incluindo pt-br),
  verificada na mesma amostra de posts.

## Assumptions

- A "amostra de posts do Reddit" para validação é um conjunto representativo de posts já
  usados pelo projeto; não há necessidade de um dataset novo para medir a melhoria.
- A avaliação de "Força do Gancho" existente permanece a referência de medição e não muda
  seus critérios como parte desta feature.
- A anatomia de gancho forte e as referências de estilo (exemplos forte/fraco) fornecidas na
  descrição são a calibração de qualidade desejada.
- Os idiomas alvo são definidos pela configuração atual do projeto; "pelo menos dois
  idiomas" inclui pt-br e um segundo idioma já suportado.
- A melhoria é entregue via ajuste de prompts e exemplos few-shot; composição de vídeo,
  geração de imagem/áudio e publicação no TikTok permanecem fora de escopo.
- A frase-citação revoltante é aplicada apenas quando a história de fato a oferece; sua
  ausência não caracteriza gancho fraco.
