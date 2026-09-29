# Ajuste dos prompts

Como o canal aprende com o próprio desempenho e muda os prompts editoriais com
o motivo registrado. A rotina é manual: nada roda sozinho, e nada muda sem a
sua aprovação. Quem conduz é a skill `/prompt-tuning`, na sessão do assistente,
no laptop.

## Ciclo e relatório

Um **ciclo** é o período em que um conjunto de prompts editoriais está em vigor
(`story.jinja2`, `evaluate_story.jinja2`, `generate_hashtags.jinja2`). Só há um
ciclo aberto por vez, e ele não tem duração fixa: termina quando você decide
fechá-lo. Todo vídeo produzido pertence ao ciclo em que foi feito, e é isso que
permite dizer, depois, se uma mudança de prompt ajudou.

Um **relatório** é uma leitura do histórico, pedida quando você quiser. Ele
diz o que funcionou, o que não funcionou e o que é inconclusivo, como estão os
experimentos, e termina com uma recomendação: manter o ciclo aberto ou
fechá-lo. Pedir um relatório não muda nada no canal.

Cada vídeo é comparado com os 10 publicados em volta dele: "2,0×" quer dizer o
dobro das views das vizinhas. Isso desconta o que mexe no canal inteiro (uma
semana de alcance ruim) e deixa o que é da história. Vídeos com menos de 7
dias não entram: ainda estão ganhando views.

## Quando pedir

- Depois de uma coleta de desempenho (`just prod-collect-performance`), para
  os números estarem frescos. O relatório recusa dados com mais de 3 dias.
- Uma vez por semana é um bom ritmo; mais que isso quase só repete o anterior,
  e o relatório vai dizer que não há vídeo novo.
- Quando um experimento deve ter atingido o alvo.

```text
/prompt-tuning           # últimos 30 dias
/prompt-tuning 45        # últimos 45 dias
/prompt-tuning close     # relatório e fechamento do ciclo
/prompt-tuning view 2026-10-06   # refaz a página de um relatório gravado
```

Com menos de 30 vídeos assentados no período, o relatório recusa e diz quantos
achou, em vez de inventar achados. Amplie o período ou colete de novo.

## O que você decide

A cada relatório:

1. **Manter ou fechar o ciclo.** A recomendação vem com os motivos; a decisão é
   sua, e as duas ficam gravadas.
2. **Experimentos.** Manter, mudar ou fechar cada um aberto; abrir, deixar na
   fila ou descartar cada sugestão; mudar a fatia de produção reservada para
   explorar (padrão: 25%) ou a ordem de prioridade.

Ao fechar um ciclo:

3. **Cada mudança de prompt proposta**: aprovar, modificar ou rejeitar. Cada
   uma vem com o trecho atual, o proposto e o achado que a justifica. Só as
   aprovadas são aplicadas.

Um achado com menos de 10 vídeos é uma **pista**: aparece no relatório, pode
virar experimento, mas não muda prompt. É assim que o canal evita mudar tudo
por causa de três vídeos que foram bem por acaso.

Um **experimento** é uma pergunta feita à audiência com uma parte da produção:
"histórias com desconhecidos funcionam quando o narrador reage?". Ele é escrito
antes dos vídeos, com o número de vídeos de que precisa e o resultado que
confirma ou refuta, e recebe o veredito quando atinge o alvo.

## Como as vagas de exploração são distribuídas

A rodada diária lê `tuning/exploration.yaml` a cada busca. Com experimento
aberto, cada história avaliada recebe uma segunda nota: se é um teste justo de
algum experimento, e qual. Com ela, a rodada reserva vagas:

- **Quantas.** A fatia é contada desde `share_since`, não dia a dia: com 25% e
  3 vídeos por dia, as vagas saem 1, 1, 0, 1 e, em 12 dias, 9 dos 36 vídeos são
  de exploração. Um dia sem história adequada é compensado nos seguintes, com
  no máximo a fatia do dia (1 vaga, com 3 por dia), para que a produção nunca
  vire só exploração.
- **Para quem.** Cada vaga vai para o primeiro experimento aberto, na ordem do
  arquivo, que tenha uma história com nota a partir de `min_fit` (padrão 70); a
  história é a de maior nota para ele. Mudar a ordem no arquivo muda a
  prioridade.
- **O resto do dia** é de base, com as histórias "Excelente" e "Boa" de
  sempre. Uma história boa de base que também serve a um experimento ocupa só
  a vaga de exploração.

Uma **vaga não preenchida** é uma vaga reservada que terminou sem vídeo do
experimento: nenhuma história atingiu `min_fit` naquele dia, ou a escolhida
falhou no roteiro ou no vídeo e uma de base tomou o lugar. Cada rodada grava
em `run_summaries` as vagas reservadas (`exploration_slots`) e as preenchidas
(`exploration_filled`); o relatório mostra as duas desde `share_since`. Muitas
vagas vazias pedem um `looks_like` mais largo ou um `min_fit` menor.

Sem experimento aberto, ou com fatia 0, a rodada é a mesma de antes da rotina.

## O que exige commit e deploy

A skill escreve os arquivos e nunca faz commit nem deploy.

| O que mudou | Commit | `just deploy` |
|---|---|---|
| Relatório novo (`tuning/reports/`) | sim: depois do commit ele não muda mais | não |
| Experimentos, fatia, prioridade (`tuning/exploration.yaml`) | sim | sim: a rodada no servidor lê esse arquivo |
| Prompts (`src/prompts/`, só no fechamento) | sim | sim: os vídeos só usam o prompt novo depois do deploy |
| Crenças, rótulos, resumo | sim | não |

Depois de um deploy que leva um ciclo novo, o relatório seguinte pergunta a
data do deploy e a grava no ciclo: é a partir dela que os vídeos contam como
do ciclo novo.

## Onde fica cada coisa

Tudo em `tuning/`, versionado ao lado dos prompts, legível sem o assistente:

| Arquivo | O que tem |
|---|---|
| `README.md` | o resumo: ciclo aberto, base, o que não funciona, pistas, experimentos, fila, ciclos, relatórios. Comece por aqui. Gerado por `just tuning-summary`; não edite à mão |
| `beliefs.yaml` | o que o canal acredita sobre a audiência, com a evidência e o histórico de cada crença |
| `exploration.yaml` | fatia de exploração e experimentos, na ordem de prioridade |
| `cycles/NNN.yaml` | um ciclo: datas, versões dos prompts, mudanças que o abriram e por quê, avaliação |
| `reports/AAAA-MM-DD.yaml` | um relatório: achados, estado do ciclo, recomendação, decisão |
| `story_labels.csv` | o tipo de cada história, para todo relatório agrupar igual |

Para saber de onde veio uma frase de um prompt, procure-a em
`tuning/README.md`: cada mudança aparece com o trecho, o ciclo e o achado que a
justificou.

A página de leitura (link no fim de cada relatório) é só para ler: tudo o que
ela mostra está no relatório gravado, e ela pode ser refeita a qualquer hora.

## Comandos

```bash
just tuning-check        # os registros estão válidos e os prompts são os do ciclo aberto
just tuning-summary      # regenera tuning/README.md
just tuning-data --json /tmp/pack.json   # os números de um relatório, sem a skill
```

`just tuning-check` falha quando um prompt foi editado fora de um fechamento.
Isso não é erro seu a desfazer: o relatório seguinte pergunta o motivo, grava e
recomenda fechar o ciclo, porque os vídeos de antes e de depois da edição estão
misturados nele.
