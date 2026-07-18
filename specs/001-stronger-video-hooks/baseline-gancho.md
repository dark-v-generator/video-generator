# Baseline da nota "gancho" (T001) e comparação (T009)

**Feature**: 001-stronger-video-hooks
**Modelo de LLM**: `moonshotai/kimi-k2.6` (OpenRouter), temperature 0.7
**Data da medição**: 2026-07-18

Registro da nota `gancho` (0–100) de `evaluate_story` aplicada ao **roteiro gerado**
(título + Parte 1 + Parte 2), para a mesma amostra fixa de 3 posts, **antes** (prompt
antigo, via `git stash` do prompt/exemplos) e **depois** (prompt novo). O avaliador
(`evaluate_story.jinja2`) é a régua e permanece inalterado (D3).

Dados brutos: `results-baseline.json` e `results-after.json` neste diretório.

## Baseline (prompt antigo)

| # | Roteiro gerado (título) | Nota gancho |
|---|-------------------------|-------------|
| 1 | Meu vizinho de BMW achou que minha vaga era dele. Eu fiz ele estacionar a dois quarteirões de casa. | 90 |
| 2 | Minha irmã baniu meus filhos do casamento dela e ainda quis que eu pagasse o open bar | 95 |
| 3 | Meu chefe me excluiu da apresentação pro CEO pra roubar meu projeto | 92 |

**Média baseline: 92.3**

> Observação: o título #1 do baseline **revela o desfecho** ("Eu fiz ele estacionar a dois
> quarteirões") — viola H5. O prompt novo evita isso.

## Depois (prompt novo)

| # | Roteiro gerado (título) | Nota gancho |
|---|-------------------------|-------------|
| 1 | Meu vizinho novo ficava estacionando na minha vaga paga e riu na minha cara quando eu reclamei | 91 |
| 2 | Minha irmã baniu meus filhos do casamento dela e ainda exigiu que eu pagasse 3 mil dólares no bar aberto | 95 |
| 3 | Meu chefe tirou o crédito do meu projeto de três meses na frente do CEO e me proibiu de ir na apresentação | 93 |

**Média depois: 93.0**

## Resultado (SC-001)

**Δ = +0.7** (93.0 vs 92.3) → melhora vs. baseline. ✅

A margem numérica é pequena porque o critério "gancho" do avaliador premia "título
clickbaity" — já maximizado pelo prompt antigo (tensão registrada em research.md D3). O
ganho qualitativo mais relevante é a **anatomia**: no prompt novo, 3/3 títulos satisfazem
H1–H6 (lideram por dano/injustiça, sem revelar o desfecho) e 3/3 aberturas satisfazem O1
(entram direto no conflito), enquanto o baseline chegou a produzir um título que entrega o
desfecho.
