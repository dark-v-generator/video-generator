# Contrato: PreparedStoryPackage e TwoPartStoryPackage (JSON)

Arquivo `<post_id>.json`, UTF-8, sem BOM. Produzido localmente pelo skill/CLI,
consumido pelo servidor. Campos e regras em [data-model.md](../data-model.md). O campo
`version` diz qual das duas formas o arquivo tem: `1` é uma história em um vídeo,
`2` é uma história em duas partes (dois vídeos). Os dois têm o mesmo nome de arquivo
e a mesma identidade (o `post_id` da URL).

## Versão 1 — exemplo mínimo válido

```json
{
  "version": 1,
  "source": "claude-code",
  "language": "pt-br",
  "created_at": "2026-09-21T10:40:12",
  "post": {
    "title": "No second date and I can't be happier",
    "content": "I work as a waiter in a fancy restaurant ...",
    "community": "r/MaliciousCompliance",
    "author": "u/someone",
    "community_url_photo": "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png",
    "url": "https://www.reddit.com/r/MaliciousCompliance/comments/1vuze4m/no_second_date_and_i_cant_be_happier/",
    "score": 4120,
    "num_comments": 310,
    "upvote_ratio": 0.96,
    "created_utc": 1789900000.0
  },
  "story_title": "Ele pediu pra eu ignorar o primeiro encontro dele... e ela veio reclamar do atendimento na minha cara",
  "script_text": "A acompanhante dele veio reclamar comigo que ninguém tinha atendido a mesa. Foi ele que pediu. ...",
  "narrator_gender": "male",
  "resolved_gender": "male",
  "summary": "Um garçom de restaurante sofisticado recebe um cliente que exige não ser interrompido ...",
  "hashtags": ["historia", "reddit", "garcom"]
}
```

## Versão 2 — exemplo mínimo válido

Mesmos campos, exceto que `script_text` dá lugar a `part1_text` e `part2_text`:

```json
{
  "version": 2,
  "source": "claude-code",
  "language": "pt-br",
  "created_at": "2026-09-22T18:05:00",
  "post": { "...igual à versão 1..." },
  "story_title": "Meu sogro de 60 anos trouxe a funcionária de 19 pra dentro de casa e jurou pra filha que não tinha nada",
  "part1_text": "Ele olhou bem nos olhos da própria filha e jurou ... Curta e me siga para a parte 2.",
  "part2_text": "As mensagens no celular dele não deixavam dúvida ... Curta, me siga e deixe nos comentários.",
  "narrator_gender": "male",
  "resolved_gender": "male",
  "summary": "...",
  "hashtags": ["historia", "reddit", "familia"]
}
```

O título do cover de cada vídeo é `story_title` com o sufixo ` - Parte 1` ou
` - Parte 2`, acrescentado pelo servidor; o pacote guarda o título sem sufixo.

## Regras que o servidor aplica ao ler

1. `version` desconhecida → `failed/` com erro `unsupported package version`. Um
   servidor anterior ao suporte a duas partes só conhece a versão 1, então um pacote
   de versão 2 cai nesta regra lá (SC-009): nada é produzido.
2. JSON inválido ou campo obrigatório ausente → `failed/` com a mensagem do pydantic.
3. `language` ≠ `config.language` → `failed/` com `language mismatch: package=<x> server=<y>`.
4. `story_title` e o(s) roteiro(s) são usados verbatim (SC-005, SC-008). A censura
   visual de produção (`TextCensor`) continua sendo aplicada às legendas e ao cover,
   como hoje.
5. `hashtags` presente (mesmo lista vazia) → não chama `generate_hashtags`; a
   normalização (`normalize_hashtags`) e o cap de 3 continuam valendo. Na versão 2 as
   mesmas hashtags vão nos dois vídeos.
6. Versão 2: os dois vídeos são produzidos antes de qualquer publicação; falha em
   qualquer um → `failed/`, nenhum publicado. Parte 1 publicada e parte 2 falhando ao
   publicar → `failed/` com erro que nomeia o slot da parte 1.

## Regras que o CLI aplica antes de enviar (`validate`)

Tudo acima, mais a detecção de palavras proibidas em `story_title` e no(s)
roteiro(s) via `TextCensor` da config local. Na versão 2, também: parte vazia e
parte 1 que não termina com o CTA localizado da parte 2 (`pt-br`: `Curta e me siga
para a parte 2.`). Cada problema nomeia o campo (`part1_text`, `part2_text`):

```text
✗ 1vuze4m.json
  - script_text: 'matou' em "...o cara quase matou o garçom de..."
  - language: package=en server=pt-br
✗ 1wn08nz.json
  - part1_text: precisa terminar com "Curta e me siga para a parte 2."
  - part2_text: 'arma' em "...pegou a arma que ele guardava..."
```

Código de saída 1. `ship` roda a mesma validação e recusa com a mesma saída.

## Compatibilidade

- Chaves extras são ignoradas na leitura (`extra="ignore"`), para permitir que o skill
  anexe notas (ex.: `"notes"`) sem quebrar o servidor.
- `version` só será incrementada em mudança incompatível de campo obrigatório. A
  versão 2 não substitui a 1: pacotes de versão 1 já enfileirados continuam válidos
  e são produzidos como hoje.
