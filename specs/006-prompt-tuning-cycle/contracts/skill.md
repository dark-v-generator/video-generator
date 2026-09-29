# Skill `/prompt-tuning` (M3)

`.claude/skills/prompt-tuning/SKILL.md`, com `references/records.md`
(formatos e categorias de rótulo), `references/recommendation.md` (critérios e
limites, com o motivo de cada um) e `references/reading-view.md` (roteiro da
página).

A skill é um prompt: explica o que cada passo protege, em vez de listar regras
(Princípio III). Fala com o operador em português.

## Invocação

```text
/prompt-tuning                 # relatório dos últimos 30 dias
/prompt-tuning 45              # últimos 45 dias
/prompt-tuning close           # relatório e, em seguida, fechamento do ciclo
```

Sem `close`, a skill nunca toca em `src/prompts/` nem em `tuning/cycles/`.

## Relatório (sempre)

| # | Passo | Saída | Protege |
|---|---|---|---|
| 1 | `just tuning-check` | falhas, se houver | raciocinar sobre registros quebrados |
| 2 | Se houver mudança de prompt fora da rotina: perguntar o motivo | entrada em `outside_changes` | misturar vídeos de antes e depois |
| 3 | `just sync-history` e `just tuning-data --json <scratch>` | pacote de dados | números inventados; recusa vira mensagem ao operador e a skill para |
| 4 | Rotular os `unlabelled` | linhas novas em `story_labels.csv` | achado que muda sem dado novo |
| 5 | Rodar `tuning-data` de novo, agora com rótulos | pacote completo | |
| 6 | Achados: o que funcionou, o que não, o que é inconclusivo | `findings` | pista tratada como conclusão |
| 7 | Estado do ciclo: experimentos, fatia, base contra o ciclo anterior | `cycle_state` | |
| 8 | O que mudou desde o relatório anterior | `since_previous` | achado repetido contado como confirmação |
| 9 | Sugestões de experimento (ao menos 2; ao menos 1 território novo ou desafio) | `suggestions` | só repetir o que já funciona |
| 10 | Recomendação: manter ou fechar, com motivos | `recommendation` | mudar antes de poder avaliar |
| 11 | Gravar `tuning/reports/AAAA-MM-DD.yaml` | registro | |
| 12 | Publicar a visão de leitura e mostrar o link | `view_url` | |
| 13 | Perguntar a decisão e o que fazer com os experimentos | `decision`, `experiment_changes` | |

Regras dos achados (em `references/recommendation.md`, com o porquê):

- todo achado traz os `record_id`, o relativo mediano e a confiança;
- menos de 10 vídeos: `is_lead: true`, e não justifica mudança de base;
- distorções do período (`channel.weekly` em queda, `lost_uploads`,
  `also_changed`) são escritas e ligadas aos achados que afetam;
- achado com os mesmos vídeos do relatório anterior recebe `unchanged_since`.

## Recomendação

Fechar quando ao menos uma vale:

- um experimento atingiu o alvo e o veredito muda uma crença da base;
- há achado com evidência suficiente para mudar um prompt;
- `cycle_comparison` mostra que a mudança do ciclo piorou;
- houve mudança de prompt fora da rotina.

Manter quando: experimentos abaixo do alvo, `verdict_possible: false`, ou nada
do que foi achado justifica mudar um prompt. Ciclo aberto há muito tempo sem
nada a aprender também é motivo para fechar, dito como tal.

A decisão do operador vale mesmo contra a recomendação; o relatório grava as
duas.

## Experimentos (em qualquer relatório)

- Para cada aberto: progresso, `days_to_target`, recomendação (manter, mudar,
  fechar). Alvo atingido: veredito contra a `decision_rule`, com os vídeos.
- Recomendar quantos manter abertos e em que ordem, dizendo quanto tempo cada
  um leva com a fatia atual, e avisar quando o conjunto é grande demais para
  concluir. A escolha do operador vale.
- Mudanças vão para `exploration.yaml` e para `experiment_changes` do ciclo.
  Mudar a fatia atualiza `share_since`.
- Experimento novo só é gravado como `open` com todos os campos; incompleto vai
  para `backlog`.
- Ao fim: lembrar de `just deploy`, porque o servidor só vê a mudança depois.

## Fechamento (`close`, ou decisão de fechar)

1. Vereditos dos experimentos que atingiram o alvo; os demais seguem abertos.
2. Avaliação do ciclo (`helped`, `hurt`, `unclear`, `not_evaluated`), a partir
   de `cycle_comparison`.
3. Atualizar `beliefs.yaml`: status e entrada em `history`.
4. Proposta de mudança nos prompts, uma a uma: redação atual, redação proposta,
   justificativa. Mudança que piorou: proposta de reversão. Crença refutada:
   proposta de mudança no trecho que dependia dela.
5. O operador aprova, modifica ou rejeita cada uma. Só as aprovadas são
   aplicadas em `src/prompts/`.
6. Fechar `cycles/NNN.yaml` (`closed`, `evaluation`, `closing`) e criar o
   seguinte com os fingerprints novos e `changes`.
7. Atualizar `exploration.yaml.cycle`.
8. `just tuning-check`, `just tuning-summary`, `uv run pytest tests/prompts -q`.
9. Mostrar o `git diff --stat` e lembrar de commit e `just deploy`; preencher
   `deployed` depois do deploy.

A skill não faz commit nem deploy: os dois são do operador.

Se o operador para antes do passo 5, o ciclo continua aberto e o que foi
escrito fica como relatório.

Redação das mudanças de prompt: a razão pela qual a audiência responde, de modo
que o modelo aplique a histórias que o achado nunca viu. A skill não propõe
regra do tipo "quando o título tiver X, faça Y"; se o achado só sustenta uma
regra assim, ele ainda é pista.

## Primeiro uso

Sem ciclo aberto além da semente: o ciclo 1 já existe (M1), com os prompts
atuais como linha de base e as crenças do relatório de setembro como pistas. O
primeiro relatório é um relatório comum.

## Visão de leitura

Uma página, o mesmo endereço a cada relatório. Conteúdo, nesta ordem:

1. Cabeçalho: data, período, vídeos considerados e excluídos, ciclo aberto e há
   quantos dias.
2. **Recomendação**, com os motivos.
3. O que mudou desde o relatório anterior.
4. O que funcionou / o que não funcionou / inconclusivo, cada achado com número
   de vídeos, relativo mediano e confiança; pistas marcadas como pistas.
5. Distorções do período, com o gráfico semanal do canal.
6. Experimentos: barra de progresso até o alvo, relativo até aqui, previsão.
7. Fatia de exploração: pretendida e atingida.
8. Sugestões de experimento.
9. Conhecimento atual: base, o que não funciona, pistas.

Tudo o que a página mostra está no YAML do relatório ou em `tuning/` (FR-041a).
A página não é fonte de nada: perdê-la não perde informação, e a skill a refaz
a partir do registro com `/prompt-tuning view AAAA-MM-DD`.

A página contém dados do canal do operador e é publicada como privada.
