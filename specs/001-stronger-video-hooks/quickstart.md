# Quickstart: Validar ganchos mais fortes

**Feature**: 001-stronger-video-hooks | **Date**: 2026-07-18

Guia de validação end-to-end. Prova que os roteiros gerados têm um gancho forte sem
quebrar as invariantes (contrato JSON, duas partes, política de palavras).

## Pré-requisitos

- Ambiente Python do projeto instalado (dependências de `requirements`/`pyproject`).
- Um proxy de LLM configurado (config ativa do projeto, ex.: `config.dev.yaml`).
- Uma amostra fixa de posts do Reddit para comparação antes/depois (reusar a amostra já
  usada pelo projeto; ver Assumptions da spec).

## 1. Baseline (antes da mudança)

Antes de alterar os prompts, gere roteiros para a amostra e registre a nota "gancho"
(0–100) da avaliação existente (`evaluate_story`) para cada post. Guarde a média — é o
baseline de SC-001.

## 2. Rodar os testes de guarda

```bash
pytest tests/ -k "story or prompt or hook" -q
```

Esperado: passam os testes que verificam
- forma do contrato de saída (chaves `title`, `narrator_gender`, `part1`, `part2`);
- marcadores "Parte 1./2." e CTAs;
- ausência de palavras proibidas em título e narração.

Referência de forma: [contracts/llm_story_output.md](./contracts/llm_story_output.md).

## 3. Gerar roteiros com o prompt novo

Gere roteiros para a mesma amostra pelo caminho ativo (2-part). Para cada roteiro,
verifique manualmente contra a anatomia do gancho
([contracts/hook_anatomy.md](./contracts/hook_anatomy.md)):

- **Título**: lidera por promessa/stakes (H1), tem vítima (H2) e antagonista/injustiça
  (H3), dano concreto (H4), **não revela o desfecho** (H5), tom falado (H6).
- **Parte 1**: a primeira frase após "Parte 1." entra no conflito (O1), sem preâmbulo.

Meta (SC-002/SC-003): ≥ 80% dos roteiros satisfazem os critérios de título e de abertura.

## 4. Reavaliar o gancho e comparar

Rode `evaluate_story` nos roteiros novos e compare a média da nota "gancho" com o baseline
do passo 1. Esperado: **melhora** da média (SC-001).

## 5. Checagem multilíngue (SC-006)

Repita os passos 3–4 para pelo menos um segundo idioma alvo além de pt-br. Esperado: a
anatomia do gancho se mantém com fraseado local natural (C2).

## 6. Paridade de caminhos (Milestone 2)

Repita os passos 2–3 para o caminho single-part (`story.jinja2`) e para o caminho DSPy.
Esperado: os três caminhos produzem ganchos com a mesma anatomia; nenhum diverge (FR-013).

## Critérios de aprovação

- [ ] Testes de guarda passam (contrato, marcadores/CTA, palavras proibidas).
- [ ] ≥ 80% dos títulos satisfazem H1–H6; ≥ 80% das aberturas satisfazem O1.
- [ ] Média da nota "gancho" melhora vs. baseline.
- [ ] Nenhuma palavra proibida em 100% da amostra.
- [ ] Contrato JSON e estrutura de duas partes preservados em 100% da amostra.
- [ ] Anatomia mantida em ≥ 2 idiomas; três caminhos consistentes.
