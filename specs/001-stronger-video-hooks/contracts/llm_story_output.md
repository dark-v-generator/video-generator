# Contract: Saída do LLM de geração de roteiro (INALTERADA)

**Feature**: 001-stronger-video-hooks

Este contrato é uma **invariante congelada** — a feature NÃO pode alterá-lo. Serve como
guarda: testes devem falhar se a forma abaixo mudar.

## Caminho 2-part (ativo — `two_part_story.jinja2` / `TwoPartTikTokStorySignature`)

```json
{
  "title": "<gancho falado, string não vazia>",
  "narrator_gender": "<male | female | unknown>",
  "part1": "<'<title>. Parte 1.' + setup que abre no conflito, termina antes do clímax + CTA parte 2>",
  "part2": "<'<title>. Parte 2.' + clímax e resolução + pergunta de engajamento + CTA final>"
}
```

**Regras verificáveis**:
- Chaves exatamente `title`, `narrator_gender`, `part1`, `part2` (nenhuma adicionada/removida).
- `narrator_gender` ∈ {`male`, `female`, `unknown`}.
- `part1` e `part2` começam com o título seguido do marcador localizado
  ("Parte 1." / "Parte 2." em pt-br).
- `part1` termina com CTA de parte 2 (pt-br: "Curta e me siga para a parte 2.").
- `part2` termina com pergunta de engajamento + CTA final (pt-br:
  "Curta, me siga e deixe nos comentários" / "Curta, me siga e conta nos comentários").
- O clímax ocorre em `part2`, nunca em `part1`.
- Nenhuma palavra da lista proibida (política de palavras fortes) em `title`, `part1` ou
  `part2`.

## Caminho single-part (`story.jinja2` / `TikTokStorySignature`)

```json
{
  "title": "<gancho falado, string não vazia>",
  "narrator_gender": "<male | female | unknown>",
  "script": "<'<title>. ' + história completa + pergunta de engajamento + CTA final>"
}
```

**Regras verificáveis**: chaves exatamente `title`, `narrator_gender`, `script`; demais
regras de política de palavras fortes e CTA final análogas ao caminho 2-part.

## Nota

A feature altera **o conteúdo do `title` e a abertura de `part1`/`script`** (qualidade do
gancho), não a **forma** destes objetos.
