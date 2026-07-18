# Implementation Plan: Ganchos mais fortes nos vídeos de história

**Branch**: `001-stronger-video-hooks` | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-stronger-video-hooks/spec.md`

## Summary

Elevar a força do gancho dos roteiros de história gerados por LLM, reescrevendo a
instrução de título e de abertura da Parte 1 para liderar por dano concreto, vítima
por quem torcer, antagonista/injustiça claros e promessa implícita de virada — sem
revelar o desfecho e com tom natural falado. A mudança é essencialmente de
*prompt engineering* baseado em racional (não casuístico), aplicada ao caminho ativo
(`two_part_story.jinja2` + few-shot `two_part_story.yaml`) e replicada nos caminhos
paralelos (`story.jinja2` single-part e as signatures DSPy em `llm_dspy_proxy.py`),
mantendo intactos o contrato JSON de saída, a estrutura de duas partes e a política de
palavras fortes. A medição de melhoria usa o critério "Força do Gancho" (gancho 0–100)
da avaliação existente como sinal comparativo, sem alterar seus critérios.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Jinja2 (templates de prompt), DSPy (caminho alternativo de
LLM), proxies de LLM próprios (`ILLMProxy`), PyYAML (few-shot examples)

**Storage**: N/A (nenhuma persistência nova; arquivos de prompt/exemplo versionados)

**Testing**: pytest (`tests/`), com testes existentes de serviço/proxy como referência

**Target Platform**: Linux/macOS server (pipeline de geração de vídeo)

**Project Type**: Single project (Clean Architecture em módulos: `src/proxies`,
`src/services`, `src/entities`, `src/core`)

**Performance Goals**: N/A — a mudança não altera latência nem custo de forma material
(mesmo número de chamadas ao LLM; prompt marginalmente maior)

**Constraints**:
- Contrato de saída do LLM inalterado: JSON com `title`, `narrator_gender`, `part1`, `part2`.
- Estrutura de duas partes preservada: clímax na Parte 2, CTA "Curta e me siga para a
  parte 2." ao fim da Parte 1.
- Política de palavras fortes (eufemismos TTS/TikTok) válida para título e narração.
- Prompts baseados em racional, sem regras casuísticas do tipo "quando X faça Y" e sem CAPS.

**Scale/Scope**: 4 arquivos de prompt/exemplo no núcleo da mudança
(`two_part_story.jinja2`, `two_part_story.yaml`, `story.jinja2`, `llm_dspy_proxy.py`),
mais testes de guarda. Sem mudança de schema de dados ou de API.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Avaliação contra `.specify/memory/constitution.md` (v1.0.0):

| Princípio | Aderência | Notas |
|-----------|-----------|-------|
| **I. Fail Fast e Simplicidade** | ✅ Pass | Nenhum ramo defensivo novo. O contrato JSON já é validado a jusante; não adicionamos tratamento casuístico de "gancho fraco". Mudança concentrada em texto de prompt e exemplos. |
| **II. Arquitetura Limpa em Módulos** | ✅ Pass | Alterações ficam na borda (`src/proxies`: templates, few-shot, signatures DSPy). Regra de negócio, serviços e entidades não são tocados. Contrato de saída inalterado preserva a fronteira. |
| **III. Prompts Baseados em Racional** | ✅ Pass | A reescrita comunica *por que* um gancho forte retém (dano concreto, vítima, antagonista, promessa de virada) e deixa o agente generalizar. Remove-se linguagem prescritiva/"clickbait" e CAPS existentes onde forem contra o princípio. |

**Resultado do Gate**: PASS — sem violações; nenhuma entrada em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-stronger-video-hooks/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── llm_story_output.md   # Contrato JSON de saída (inalterado — congelado como guarda)
│   └── hook_anatomy.md       # Contrato de conteúdo do gancho (critérios observáveis)
├── checklists/
│   └── requirements.md  # Spec quality checklist (/speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
src/
├── proxies/
│   ├── prompts/
│   │   ├── two_part_story.jinja2     # [ALVO] instrução de título + abertura Parte 1
│   │   ├── story.jinja2              # [ALVO] caminho single-part (mesma orientação)
│   │   └── evaluate_story.jinja2     # [REFERÊNCIA] critério "gancho" — não alterado
│   ├── examples/
│   │   └── two_part_story.yaml       # [ALVO] few-shot alinhado à instrução de gancho
│   └── llm_dspy_proxy.py             # [ALVO] signatures DSPy (2-part e single) + few-shot
└── services/
    └── ...                          # não tocado

tests/
└── ...                              # [ALVO] testes de guarda (política de palavras, contrato)
```

**Structure Decision**: Single project em Clean Architecture. A feature altera apenas a
camada de borda de geração (`src/proxies`), preservando entidades, serviços e o contrato
de saída. Isso mantém a regra de negócio isolada dos detalhes de prompt.

## Delivery Plan

Trabalho agrupado em milestones independentemente testáveis (~1 PR cada). **PR count
projetado: 2** (dentro do limite de 8).

### Milestone 1 — Caminho ativo (2-part) com gancho forte  · ~1 PR

**Escopo**:
- Reescrever a instrução de título (item 2) e a abertura das partes (item 5) em
  `src/proxies/prompts/two_part_story.jinja2` para liderar por dano concreto, vítima,
  antagonista/injustiça e promessa de virada, sem revelar o desfecho, com tom falado —
  em racional, sem regras casuísticas nem CAPS.
- Alinhar o few-shot `src/proxies/examples/two_part_story.yaml` e o bloco de exemplos do
  template: adicionar um campo `title` explícito (o gancho forte traduzido) por exemplo e
  referenciá-lo no template em vez de `example.original_post.title` (que hoje ensina o
  título original em inglês). Revisar títulos de exemplo que revelam o desfecho
  (ex.: "Fiz minha chefe ser demitida…") para não contradizerem a instrução.
- Manter inalterados: contrato JSON, marcadores "Parte 1./2.", CTA, política de palavras.

**Verification gate**:
- Teste de guarda garante que a saída gerada mantém as chaves do contrato
  (`title`, `narrator_gender`, `part1`, `part2`) e os marcadores/CTA das duas partes.
- Teste garante ausência de palavras proibidas em título e narração numa amostra.
- Revisão manual: numa amostra de posts, os títulos lideram por promessa/stakes com vítima
  e antagonista e não revelam o desfecho; Parte 1 abre no conflito.
- Sinal comparativo: nota média "gancho" (0–100) da avaliação melhora vs. baseline.
- Consistência: nenhum few-shot contradiz a instrução (checagem de revisão).

### Milestone 2 — Caminhos paralelos alinhados (single-part + DSPy)  · ~1 PR

**Escopo**:
- Aplicar a mesma orientação de gancho por racional à instrução de título e à abertura em
  `src/proxies/prompts/story.jinja2` (single-part).
- Atualizar as signatures DSPy em `src/proxies/llm_dspy_proxy.py`
  (`TwoPartTikTokStorySignature` e `TikTokStorySignature`) e as descrições de
  `viral_title`/`part1_script` para o mesmo racional, retirando linguagem "clickbaity"
  onde conflita com o princípio. Se M1 introduzir `title` explícito no YAML, simplificar a
  extração de `viral_title` no carregamento de few-shot do DSPy para usá-lo.

**Verification gate**:
- Testes de guarda equivalentes aos de M1 para os caminhos single-part e DSPy
  (contrato de saída preservado; sem palavras proibidas).
- Revisão manual: os três caminhos produzem ganchos com a mesma anatomia; nenhum diverge.
- Verificação multilíngue: amostra em pt-br + um segundo idioma alvo mantém a anatomia com
  fraseado local natural (SC-006).

## Complexity Tracking

> Nenhuma violação de constituição a justificar. Seção intencionalmente vazia.
