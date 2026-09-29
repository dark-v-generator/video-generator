# Achados, limites e a recomendação

Como transformar o pacote de dados em achados e em uma recomendação de manter
ou fechar o ciclo. Cada regra vem com o motivo: quando um caso não couber nela,
decida pelo motivo.

O canal tem um operador, três vídeos por dia e um mês de dados rende cerca de
80 vídeos. Com amostras desse tamanho, o risco dominante não é deixar de ver um
padrão: é ver padrão onde há ruído e mudar os prompts por causa dele. Quase
todas as regras abaixo protegem contra isso.

## De onde vêm os números

Todo número de um achado sai do pacote (`just tuning-data`) ou de
`scripts/group.py` rodado sobre ele. Nenhum é estimado lendo as linhas.

O pacote compara cada vídeo com os 10 publicados mais perto dele no tempo
(`relative`): 2,0 é o dobro das views das vizinhas. Isso desconta o que muda o
canal inteiro de uma semana para outra (alcance em queda, um feriado) e deixa o
que é da história. Por isso os achados usam o relativo e nunca as views
absolutas: em setembro a mediana semanal caiu de 1 065 para 430, e comparar
views cruas diria que tudo o que foi feito no fim do mês é pior.

Só vídeos assentados entram (FR-013): um vídeo com menos de 7 dias entre a
publicação e a coleta ainda está ganhando views, e o relativo dele mudaria no
relatório seguinte.

## Limites padrão

| Limite | Valor | Por quê |
|---|---|---|
| Período | 30 dias | cerca de 80 vídeos: o bastante para grupos de 10, curto o bastante para o canal não ter mudado por baixo |
| Vídeos assentados para haver achados | 30 | abaixo disso nenhum grupo chega a 10; o pacote recusa, e a skill não inventa achado |
| Idade máxima da última coleta | 3 dias | dados mais velhos perdem os vídeos da semana e deixam os recentes sem assentar |
| Dias para assentar | 7 | a maior parte das views de um vídeo chega na primeira semana (91% no primeiro dia, no vídeo que a sonda abriu) |
| Evidência para a base ou para "não funciona" | 10 vídeos | com menos, um vídeo viral ou um fracasso decide a mediana sozinho |
| Reteste de uma crença da base | 90 dias | a audiência e o algoritmo mudam; uma crença sem teste recente vira hábito (SC-010) |
| Vídeos de base assentados por ciclo para comparar ciclos | 20 | o pacote marca `verdict_possible: false` abaixo disso |

Os três primeiros são argumentos de `just tuning-data`. Se o operador pedir
outro período, passe `--days N` ou `--since`; não relaxe `--min-settled` para
fazer um relatório caber: a recusa é a resposta certa quando há pouco dado.

## Confiança

| Confiança | Quando |
|---|---|
| `low` | menos de 10 vídeos, ou um só período, ou o grupo depende de 1 ou 2 vídeos muito acima dos outros |
| `medium` | 10 ou mais vídeos, e a direção se mantém quando se tira o maior e o menor |
| `high` | 10 ou mais vídeos em ao menos dois relatórios com vídeos diferentes, ou confirmado por experimento |

Para ver se o grupo depende de poucos vídeos, compare `at_least_1_5` e
`at_most_0_8` do `group.py`: um grupo com mediana 2,0 e 8 de 10 acima de 1,5×
é outra coisa que um com mediana 1,6 e 3 de 10.

## Pista não muda a base

Achado com menos de 10 vídeos tem `is_lead: true` (o validador recusa o
contrário). Uma pista:

- aparece no relatório, na coluna de pistas;
- pode virar sugestão de experimento, que é o jeito de juntar os vídeos que
  faltam sem mudar a base;
- **não** justifica mudança de prompt de base e **não** entra na base.

Por quê: a mudança de prompt afeta todos os vídeos do ciclo seguinte. Se ela
vier de uma pista de 7 vídeos e estiver errada, o canal gasta um ciclo inteiro
produzindo na direção errada, e a comparação entre ciclos leva semanas para
mostrar. O experimento gasta só a fatia de exploração para responder a mesma
pergunta.

Uma pista pode ser escrita no prompt se for mudança de exploração (entra pelo
`looks_like` de um experimento), nunca pela redação dos prompts editoriais.

## O que é um achado

Um achado diz algo que ajuda a escolher, escrever, titular ou postar a próxima
história. Cubra ao menos (FR-009):

- **tipo de história**: `--by kind`, `--by kind --by narrator_acts`;
- **título e abertura**: `--by title_promise`, `--by title_length`;
- **condições de postagem**: `--by weekday`;
- **retenção**: `--by watch` (é o sinal que mais acompanha as views; um grupo
  com relativo alto e watch baixo é suspeito).

Coloque em `works` o que vai claramente acima de 1,0 (mediana ≥ 1,3 com
maioria acima de 1,0), em `does_not` o que vai claramente abaixo (≤ 0,8), e em
`inconclusive` o resto que valha registrar, inclusive grupos grandes que ficam
na média: saber que casal é 1,0× em 22 vídeos é informação. Esses cortes são um
ponto de partida; o que decide é se o operador faria algo diferente por causa
do achado.

Todo achado leva os `record_id`, `median_relative` e `confidence`. Ligue-o à
crença que ele reforça ou contraria (`belief`).

## Distorções do período

Leia `channel.weekly`, `channel.lost_uploads`, `videos.excluded`,
`cycle_comparison.also_changed` e `prompt_drift`, e escreva em `distortions`
cada condição que atrapalha a leitura, dizendo em `affects` quais achados ela
toca (FR-012):

| Condição | Onde aparece | O que afeta |
|---|---|---|
| alcance caindo ou subindo | `channel.weekly` | comparações em views absolutas; o relativo desconta, mas diga |
| uploads perdidos | `lost_uploads` | a vizinhança fica esparsa e irregular; achados de dia da semana |
| muitos não assentados | `excluded.unsettled` | a última semana não entra; achados que dependem de vídeos recentes |
| mais de uma coisa mudou | `also_changed` | a comparação entre ciclos não é atribuível só ao prompt |
| prompt mudou fora da rotina | `prompt_drift`, `outside_changes` | vídeos antes e depois misturados no mesmo ciclo |
| categoria de rótulo nova | `new_label` | achados de tipo de história comparados com relatórios anteriores |

Uma distorção que atinge um achado rebaixa a confiança dele ou o manda para
`inconclusive`; diga qual.

## O que mudou desde o relatório anterior

Um achado com os mesmos vídeos do relatório anterior não é confirmação: é o
mesmo dado lido duas vezes. Compare os `videos` de cada achado com os do achado
equivalente no relatório anterior (mesma crença ou mesmo agrupamento):

- mesmos vídeos: `unchanged_since: <id do anterior>`, e a página diz "sem
  dado novo";
- vídeos novos: conte quantos em `since_previous.changed_findings` ("sogros
  passou de 7 para 9 vídeos") e só então fale em reforço ou enfraquecimento.

`since_previous.new_videos` conta os vídeos assentados agora que ainda não
estavam assentados na leitura anterior: os publicados depois de
`data_as_of` do relatório anterior menos 7 dias. Conte com
`group.py PACK --by goal --published-after <essa data>`.

## Recomendação: fechar ou manter

Recomende **fechar** quando ao menos uma vale:

- um experimento atingiu o alvo e o veredito muda uma crença da base: a base
  que os prompts carregam está desatualizada;
- há achado com 10 ou mais vídeos e confiança `medium` ou `high` que pediria
  mudar um prompt: esperar mais produz vídeos com um prompt que já se sabe
  pior;
- `cycle_comparison` mostra, com `verdict_possible: true`, que a mudança que
  abriu o ciclo piorou: cada dia a mais é produção pior;
- houve mudança de prompt fora da rotina: o ciclo mistura vídeos de dois
  prompts, e fechar separa os dois a partir daqui.

Mesmo com um desses motivos, um ciclo com menos de 20 vídeos de base
assentados tem um custo ao fechar com mudança de prompt: a mudança seguinte só
é comparada com este ciclo, e fica sem veredito. Diga o número junto da
recomendação.

Recomende **manter** quando:

- os experimentos estão abaixo do alvo: fechar agora daria vereditos sem
  amostra;
- `verdict_possible: false`: a mudança do ciclo ainda não pode ser julgada, e
  mudar de novo apagaria a chance de julgá-la;
- nada do que foi achado justifica mudar um prompt.

Ciclo aberto há muito tempo (mais de 60 dias) sem experimento perto do alvo e
sem achado novo também é motivo para fechar, dito como tal: um ciclo que não
ensina nada só adia a próxima pergunta. Nesse caso o fechamento pode não mudar
prompt nenhum e abrir o ciclo seguinte só com experimentos novos.

Cada motivo em `recommendation.reasons` cita o número que o sustenta ("o ciclo
1 tem 0 vídeos de base assentados; o mínimo para comparar é 20").

A decisão do operador vale mesmo contra a recomendação. O relatório grava as
duas (`recommendation` e `decision`), e ninguém precisa justificar a
divergência além de uma nota curta, se o operador quiser dar.

## Experimentos

Para cada experimento aberto, a partir de `exploration.experiments` do pacote:

- progresso: `settled` de `target`, `median_relative` até aqui, `videos`;
- previsão: `days_to_target` (vazio se ainda não produziu nada);
- recomendação: manter, mudar (fechar e abrir um que o substitui) ou fechar.

Quando `target_reached` é verdadeiro, o experimento recebe o veredito neste
relatório (FR-035), contra a `decision_rule` escrita quando foi aberto, nunca
contra uma regra pensada agora: `confirmed`, `refuted` ou `inconclusive`, com
os vídeos. Julgar pela regra antiga é o que impede de ajustar a pergunta ao
resultado.

**Quantos manter abertos.** Com a fatia padrão (0,25 de 3 vídeos por dia),
entram cerca de 5 vídeos de exploração por semana, e vão para o primeiro
experimento da lista que tenha história adequada. Um experimento de alvo 10
leva umas duas semanas sozinho; três abertos com alvo 10 levam mais de um
mês, e o último da fila talvez nunca receba vaga. Recomende a ordem e quantos
cabem, diga quanto tempo cada um leva nessa ordem e avise quando o conjunto
não conclui em um prazo razoável (dois ciclos). A escolha do operador vale.

## Sugestões de experimento

Ao menos duas por relatório, ao menos uma de território novo (`unexplored`) ou
que desafie uma crença (`challenge`) (FR-027, SC-006). Tire-as de:

- pistas com poucos vídeos (a sugestão é juntar os que faltam);
- crenças de base com `last_tested` há mais de 90 dias (reteste);
- crenças `does_not_work` apoiadas em poucos vídeos ou em vídeos sem a
  condição que talvez as salvasse (em setembro, nenhuma das histórias com
  desconhecidos tinha reação do narrador);
- o que o canal nunca tentou (a matriz de `kind` × `narrator_acts` mostra os
  cruzamentos sem nenhum vídeo).

Só repetir o que já funciona não ensina nada novo: a base só cresce se alguém
pergunta fora dela.

Cada sugestão aberta precisa de todos os campos antes de ir para
`exploration.yaml` com `status: open` (FR-025); se o operador quer abrir mas
falta algum, ela vai para `backlog` com `question` e `motivation`.

## Crenças

- Veredito `confirmed` em experimento de crença `lead`: a crença pode entrar
  na base se a evidência somar 10 vídeos; entrada `confirmed` no histórico.
- Veredito `refuted` em crença da base: sai da base (`contested` ou
  `retired`), entrada `overturned`, e o trecho do prompt que dependia dela é
  proposto para mudança no fechamento (FR-038).
- Achado que vai contra uma crença sem experimento: entrada `weakened`, e a
  crença vira candidata a desafio.
- O operador pode manter uma crença contra a evidência: entrada
  `kept_against_evidence`, com a nota dele.

## Mudança de prompt

Só no fechamento, só a partir de achado com evidência de base, crença da base
ou veredito de experimento. Escreva a razão pela qual a audiência responde, de
modo que o modelo aplique a histórias que o achado nunca viu (FR-019,
Princípio III):

- em vez de "quando a história for de trabalho, termine com o troco", escreva
  por que o troco segura: quem assiste espera ver a injustiça respondida, e a
  história que entrega isso recompensa a espera;
- se o achado só sustenta uma regra casuística ("títulos com 'Só esqueceram
  que' vão bem"), ele ainda é pista: falta entender por que, e um experimento
  pode responder;
- sem CAPS para dar ênfase.
