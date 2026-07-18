# Contract: Saída do LLM de geração de roteiro (INALTERADA)

**Feature**: 001-stronger-video-hooks

Este contrato é uma **invariante congelada** — a feature NÃO pode alterá-lo. Serve como
guarda: testes devem falhar se a forma abaixo mudar.

## Caminho 2-part (ativo — `two_part_story.jinja2` / `TwoPartTikTokStorySignature`)

```json
{
  "title": "<gancho para a CAPA (não narrado), string não vazia>",
  "narrator_gender": "<male | female | unknown>",
  "part1": "<abre direto no conflito (sem título, sem 'Parte 1.'), termina antes do clímax + CTA parte 2>",
  "part2": "<continua direto na história (sem título, sem 'Parte 2.'), clímax e resolução + pergunta de engajamento + CTA final>"
}
```

**Regras verificáveis**:
- Chaves exatamente `title`, `narrator_gender`, `part1`, `part2` (nenhuma adicionada/removida).
- `title` é string não vazia — é o gancho **exibido na capa**, **não narrado**.
- `narrator_gender` ∈ {`male`, `female`, `unknown`}.
- `part1` e `part2` **NÃO** começam pelo título nem pelo marcador "Parte N." — a narração
  entra direto na história (o título e "Parte N." vão só na capa).
- `part1` termina com CTA de parte 2 (pt-br: "Curta e me siga para a parte 2.").
- `part2` termina com pergunta de engajamento + CTA final (pt-br:
  "Curta, me siga e deixe nos comentários" / "Curta, me siga e conta nos comentários").
- O clímax ocorre em `part2`, nunca em `part1`.
- Nenhuma palavra da lista proibida (política de palavras fortes) em `title`, `part1` ou
  `part2`.

## Caminho single-part (`story.jinja2` / `TikTokStorySignature`)

```json
{
  "title": "<gancho para a CAPA (não narrado), string não vazia>",
  "narrator_gender": "<male | female | unknown>",
  "script": "<história completa começando direto no conflito (sem título) + pergunta de engajamento + CTA final>"
}
```

**Regras verificáveis**: chaves exatamente `title`, `narrator_gender`, `script`; `script`
**não** começa pelo título; demais regras de política de palavras fortes e CTA final
análogas ao caminho 2-part.

## Nota

A feature altera **o conteúdo do `title` (gancho da capa) e a abertura de `part1`/`script`**
(que agora começam direto na história). O título e o marcador "Parte N." deixam de ser
narrados: são exibidos apenas na imagem de capa (ver FR-014/FR-015). As chaves do JSON
permanecem as mesmas.
