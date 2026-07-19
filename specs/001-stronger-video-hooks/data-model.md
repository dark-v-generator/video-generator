# Data Model: Ganchos mais fortes nos vídeos de história

**Feature**: 001-stronger-video-hooks | **Date**: 2026-07-18

Esta feature **não introduz novas entidades de dados persistidas nem altera o schema de
saída**. O modelo abaixo descreve as entidades conceituais envolvidas e — o mais
relevante — a estrutura do few-shot que muda de forma.

## Entidades conceituais

### Post do Reddit (fonte)
- **title**: título original do post.
- **text**: corpo original do post.
- **Papel**: entrada da geração; determina quais elementos da anatomia do gancho estão de
  fato disponíveis (vítima, antagonista, dano, frase citável).

### Roteiro de história (saída do LLM) — contrato INALTERADO
- **title** (string): gancho falado sobre a imagem de capa.
- **narrator_gender** (`male` | `female` | `unknown`).
- **part1** (string): abre no conflito, termina antes do clímax com CTA de parte 2.
- **part2** (string): clímax e resolução, termina com pergunta de engajamento + CTA.
- **Regras** (mantidas): marcadores "Parte 1./2." após o título; clímax sempre na Parte 2;
  política de palavras fortes em todo o texto e no título.

### Gancho (conceito de qualidade — não é um campo)
Combinação de `title` + abertura de `part1`. Sua força é avaliada pelos elementos:
- vítima/protagonista por quem torcer;
- antagonista/injustiça claros;
- dano ou conflito concreto (não intriga abstrata);
- frase curta e revoltante como citação — **opcional**, só quando a história a oferece;
- promessa implícita de virada/justiça;
- não revela o desfecho.

### Avaliação de gancho (sinal de medição) — INALTERADA
- **notas.gancho.nota** (0–100) e **justificativa**. Usada como comparação antes/depois.

## Estrutura de few-shot que MUDA de forma

Arquivo: `src/proxies/examples/two_part_story.yaml` (lista de entradas).

### Antes (forma atual)
```yaml
- original_post:
    title: <título original em inglês>
    text: <texto original>
  narrator_gender: <male|female|unknown>
  part1: <script pt-br, começa com o gancho embutido + "Parte 1.">
  part2: <script pt-br + "Parte 2.">
```
O template renderiza `"title": "{{ example.original_post.title }}"` — ensinando o título
de saída como o **original em inglês** (contradição com a instrução).

### Depois (forma proposta)
```yaml
- original_post:
    title: <título original em inglês>
    text: <texto original>
  title: <gancho forte traduzido — mesmo texto que abre part1 antes de "Parte 1.">
  narrator_gender: <male|female|unknown>
  part1: <script pt-br, começa com o gancho + "Parte 1.">
  part2: <script pt-br + "Parte 2.">
```
- **Novo campo**: `title` (gancho forte traduzido) no nível da entrada.
- **Consumo**: o template passa a referenciar `example.title`; o carregador de few-shot do
  DSPy passa a usar `entry["title"]` em vez de fazer split de `part1` em ". Parte 1.".
- **Regra de validação**: `entry.title` deve ser idêntico ao trecho de `part1` anterior ao
  marcador "Parte 1." (mesma frase de gancho), garantindo coerência entre o campo e a
  narração.

## Transições de estado
N/A — não há máquina de estados. A geração é uma transformação sem estado
(post → roteiro).
