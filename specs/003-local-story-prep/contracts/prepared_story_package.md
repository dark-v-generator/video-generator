# Contrato: PreparedStoryPackage (JSON)

Arquivo `<post_id>.json`, UTF-8, sem BOM. Produzido localmente pelo skill/CLI,
consumido pelo servidor. Campos e regras em [data-model.md](../data-model.md).

## Exemplo mínimo válido

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

## Regras que o servidor aplica ao ler

1. `version` desconhecida → `failed/` com erro `unsupported package version`.
2. JSON inválido ou campo obrigatório ausente → `failed/` com a mensagem do pydantic.
3. `language` ≠ `config.language` → `failed/` com `language mismatch: package=<x> server=<y>`.
4. `story_title` e `script_text` são usados verbatim (SC-005). A censura visual de
   produção (`TextCensor`) continua sendo aplicada às legendas e ao cover, como hoje.
5. `hashtags` presente (mesmo lista vazia) → não chama `generate_hashtags`; a
   normalização (`normalize_hashtags`) e o cap de 3 continuam valendo.

## Regras que o CLI aplica antes de enviar (`validate`)

Tudo acima, mais a detecção de palavras proibidas em `story_title` e `script_text`
via `TextCensor` da config local. Saída em caso de erro:

```text
✗ 1vuze4m.json
  - script_text: 'matou' em "...o cara quase matou o garçom de..."
  - language: package=en server=pt-br
```

Código de saída 1. `ship` roda a mesma validação e recusa com a mesma saída.

## Compatibilidade

- Chaves extras são ignoradas na leitura (`extra="ignore"`), para permitir que o skill
  anexe notas (ex.: `"notes"`) sem quebrar o servidor.
- `version` só será incrementada em mudança incompatível de campo obrigatório.
