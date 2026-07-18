# Research: Ganchos mais fortes nos vídeos de história

**Feature**: 001-stronger-video-hooks | **Date**: 2026-07-18

Não há marcadores NEEDS CLARIFICATION no Technical Context. Este documento consolida as
decisões de design que orientam a implementação.

## D1 — Instrução de gancho por racional (não casuística)

- **Decisão**: Reescrever a instrução de título e de abertura da Parte 1 comunicando o
  *porquê* de um gancho forte reter (dano concreto a alguém por quem torcer, antagonista/
  injustiça claros, promessa implícita de virada, tom falado, ir direto ao ponto sem
  revelar o desfecho) e deixar o agente generalizar. Apresentar a "anatomia" como
  critérios a perseguir e usar os exemplos forte/fraco da descrição apenas como
  calibração de energia, explicitando por que um é forte e o outro é fraco.
- **Rationale**: Alinha ao Princípio III da constituição (prompts baseados em racional,
  sem regras "quando X faça Y", sem CAPS). Uma anatomia com racional cobre casos não
  antecipados melhor do que uma checklist rígida.
- **Alternativas consideradas**:
  - Regras casuísticas por tipo de história (vingança/família/trabalho) — rejeitada:
    viola o Princípio III e engessa o agente.
  - Enumerar padrões de título fixos para copiar — rejeitada: gera títulos genéricos e
    repetitivos; a descrição pede padrões como *ilustração*, não fórmula.

## D2 — Consistência dos few-shot com a instrução

- **Decisão**: Tornar os exemplos few-shot coerentes com a nova instrução. (a) Adicionar
  um campo `title` explícito por exemplo em `two_part_story.yaml` com o gancho forte
  traduzido, e referenciá-lo no template em vez de `example.original_post.title`; (b)
  revisar títulos de exemplo que revelam o desfecho (ex.: "Fiz minha chefe ser
  demitida…") para liderarem pelo dano/injustiça sem entregar o resultado.
- **Rationale**: Hoje o bloco "Expected Output JSON" do template ensina o título de saída
  como o título original em inglês (`example.original_post.title`), o que contradiz a
  instrução de gerar um gancho traduzido e forte. Few-shot que contradiz a instrução é o
  sinal mais forte para o modelo (FR-009 / critério de aceite "few-shot não contradizem").
- **Alternativas consideradas**:
  - Manter o template extraindo o título da primeira frase do `part1` (como o DSPy faz por
    split em ". Parte 1.") — rejeitada: frágil e implícito; um campo `title` explícito é
    mais simples e legível (Princípio I).

## D3 — Avaliação de gancho permanece o critério de medição (inalterada)

- **Decisão**: Não alterar `evaluate_story.jinja2` nem a signature de avaliação DSPy. Usar
  a nota "gancho" (0–100) como sinal comparativo antes/depois numa amostra fixa de posts.
- **Rationale**: A avaliação é a régua; mudá-la invalidaria a comparação exigida por
  SC-001. A Assumption da spec fixa que os critérios de avaliação não mudam nesta feature.
- **Observação (fora de escopo)**: o critério "gancho" descreve "título clickbaity", termo
  em leve tensão com a filosofia "não é clickbait mentiroso". Isso é registrado como dívida
  para uma feature futura; não é alterado aqui para preservar a régua de comparação.

## D4 — Paridade entre os três caminhos de geração

- **Decisão**: Replicar o mesmo racional de gancho no caminho single-part
  (`story.jinja2`) e nas signatures DSPy (`TwoPartTikTokStorySignature`,
  `TikTokStorySignature`, incluindo as descrições de `viral_title`/`part1_script`).
- **Rationale**: FR-013 exige que os caminhos paralelos não divirjam. Se apenas o caminho
  ativo mudar, trocas de proxy/config produziriam ganchos inconsistentes.
- **Alternativas consideradas**:
  - Adiar o DSPy para outra feature — rejeitada: deixaria um caminho de produção com o
    prompt antigo e contradiria o critério de aceite de consistência.

## D5 — Multilíngue com fraseado local natural

- **Decisão**: Expressar a anatomia do gancho de forma agnóstica de idioma; usar exemplos
  em pt-br apenas como calibração, instruindo explicitamente que outros idiomas alvo
  devem buscar o mesmo efeito com fraseado local natural (não tradução literal).
- **Rationale**: FR-007 e SC-006. O projeto já parametriza `target_language`; a instrução
  deve carregar o efeito desejado, não frases fixas.

## D6 — Restrições invariantes preservadas

- **Decisão**: Não tocar no contrato JSON de saída, nos marcadores "Parte 1./2.", no CTA
  de fim da Parte 1, na regra de clímax na Parte 2, nem na política de palavras fortes.
  Testes de guarda protegem essas invariantes.
- **Rationale**: Restrições explícitas da spec (FR-010, FR-011, FR-012) e do princípio de
  Fail Fast/Simplicidade — a mudança é de conteúdo de gancho, não de estrutura.
