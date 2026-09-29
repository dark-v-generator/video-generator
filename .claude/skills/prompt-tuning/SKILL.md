---
name: prompt-tuning
description: "Relatório de acompanhamento do ciclo de ajuste dos prompts do canal: lê o histórico de desempenho, grava o relatório em tuning/reports/, publica a visão de leitura e recomenda manter ou fechar o ciclo; com close, fecha o ciclo e ajusta os prompts editoriais com o motivo registrado. Use quando o operador pedir relatório de desempenho, o que está funcionando no canal, ajuste dos prompts, experimentos ou fechamento de ciclo."
argument-hint: "[dias] | close | view AAAA-MM-DD"
user-invocable: true
---

# /prompt-tuning

O canal produz três vídeos por dia a partir de prompts editoriais
(`src/prompts/story.jinja2`, `evaluate_story.jinja2`, `generate_hashtags.jinja2`).
Esta rotina é como o canal aprende com o próprio desempenho sem se enganar:
mede cada vídeo contra os publicados em volta dele, separa o que tem evidência
do que é pista, e só muda os prompts quando o operador fecha um ciclo, com o
motivo de cada mudança gravado ao lado dela.

Fale com o operador em português. Ele tem pouco tempo: o relatório precisa ser
lido e decidido em menos de 10 minutos dele (SC-001), então o que aparece no
chat é curto e o detalhe fica na página e no registro.

## O que você lê antes

- `references/records.md`: o formato de cada arquivo de `tuning/`, os ids e as
  categorias de rótulo. Leia antes de escrever qualquer registro.
- `references/recommendation.md`: como um grupo de vídeos vira achado, os
  limites e o porquê de cada um, e quando recomendar fechar.
- `references/reading-view.md`: a página de leitura, seção por seção.
- `scripts/group.py`: agrupa o pacote de dados e dá a evidência de cada grupo.

## Invocação

```text
/prompt-tuning                 # relatório dos últimos 30 dias
/prompt-tuning 45              # relatório dos últimos 45 dias
/prompt-tuning close           # relatório e, em seguida, fechamento do ciclo
/prompt-tuning view AAAA-MM-DD # refaz a página de um relatório gravado
```

## O que esta skill nunca faz sozinha

Nada na rotina roda por conta própria, e nada muda sem a aprovação explícita do
operador (FR-006). Em particular:

- **Sem fechamento, `src/prompts/` não é tocado**, e nenhum ciclo é aberto ou
  fechado. No ciclo aberto, o relatório só acrescenta às listas `reports`,
  `experiment_changes` e `outside_changes` e preenche `deployed`. Mudar prompt
  no meio do ciclo misturaria, sob o mesmo número de ciclo, vídeos de dois
  prompts diferentes, e nenhuma comparação posterior conseguiria separá-los.
- **Não faz commit nem deploy.** Os dois são do operador: o commit é o que
  torna um relatório permanente, e o deploy é o que faz a mudança valer no
  servidor. Ao fim, diga o que precisa de cada um.
- **Não calcula de cabeça.** Todo número vem de `just tuning-data` ou de
  `scripts/group.py`. Um número estimado lendo linhas parece tão confiável
  quanto um calculado, e não é.
- **Não reescreve relatório commitado nem ciclo fechado.** Correção é um
  relatório novo com `corrects` (FR-041).

## Relatório

Sempre, com ou sem `close`. Cada passo diz o que protege.

### 1. Verificar os registros

```bash
just tuning-check
```

Raciocinar sobre registros quebrados produz conclusões quebradas. Se falhar em
algo que não seja a verificação 8, mostre as linhas que falharam, corrija com o
operador (em geral é um registro desta própria rotina escrito errado) e só
então siga. A verificação 8 é o passo 2.

Se o ciclo aberto está com `deployed: null`, pergunte ao operador se e quando
ele rodou `just deploy` depois de abrir o ciclo, e preencha a data. O pacote de
dados usa essa data para saber a que ciclo pertence cada vídeo feito antes do
registro de ciclo existir no histórico.

### 2. Mudança de prompt fora da rotina

Se a verificação 8 falhou, algum prompt mudou desde que o ciclo abriu. Mostre
o que mudou (`git log -p --since=<opened> -- src/prompts/<arquivo>`) e
pergunte ao operador por quê. Grave no ciclo aberto:

```yaml
outside_changes:
  - {detected: <hoje>, prompt: story, from: <registrado>, to: <em disco>, reason: "<o que o operador disse>"}
```

e rode o check de novo. Não desfaça a mudança: ela é do operador. O que
protege é a atribuição: os vídeos feitos depois da mudança estão no mesmo
ciclo que os de antes, e o relatório precisa saber disso para não creditar a
um prompt o que veio do outro. Uma mudança fora da rotina é motivo para
recomendar fechar o ciclo (passo 10) e é uma distorção do período (passo 6).

### 3. Dados

```bash
just sync-history
just tuning-data --json <scratchpad>/pack.json          # ou --days N
```

O pacote é a única fonte de números do relatório. Se o comando sair com código
2, ele recusou: poucos vídeos assentados, ou coleta velha. Mostre a linha que
ele imprimiu, proponha o que ela diz (ampliar com `--days`, ou coletar com
`just prod-collect-performance`, que roda no servidor e só com a confirmação do
operador, porque usa a mesma sessão do publicador) e **pare sem escrever
nada**. Um relatório sobre dados que não sustentam achados ensina coisas
falsas, e elas ficam gravadas.

### 4. Rotular as histórias novas

`unlabelled` lista os vídeos do período sem rótulo em `tuning/story_labels.csv`.
Classifique cada um pelo título e pelo resumo da linha do pacote, com as
categorias de `references/records.md`, e acrescente uma linha por vídeo com
`labelled_at` de hoje. Não reclassifique os que já têm rótulo: o rótulo gravado
é o que faz dois relatórios agruparem o mesmo vídeo do mesmo jeito, e um achado
só pode mudar porque um dado mudou.

Mostre ao operador só a contagem por categoria e, se houver, os poucos vídeos
em que você ficou em dúvida, com a sua escolha. Ele corrige se quiser.

### 5. Dados de novo, com os rótulos

Rode `just tuning-data` com os mesmos argumentos: agora as linhas trazem
`label`, e os agrupamentos por tipo de história funcionam.

### 6. Achados

Agrupe com `scripts/group.py` por tipo de história, pelo que o narrador faz,
pela promessa e pelo comprimento do título, pelo dia da semana e pelo tempo
assistido (veja `references/recommendation.md`), e escreva os achados em três
listas: o que funcionou, o que não funcionou e o inconclusivo. Cada achado leva
os `record_id`, o relativo mediano e a confiança; com menos de 10 vídeos,
`is_lead: true`. Ligue cada achado à crença que ele reforça ou contraria.

Pista tratada como conclusão é o erro que mais custa aqui: ela entra no prompt
e dirige um ciclo inteiro. Diga "pista" sempre que for.

Escreva também as distorções do período (queda de alcance, uploads perdidos,
vídeos não assentados, várias coisas mudadas ao mesmo tempo, mudança fora da
rotina) e ligue cada uma aos achados que ela afeta (FR-012). Copie
`channel.weekly` do pacote para `weekly_reach`.

### 7. Estado do ciclo

Do pacote: fatia pretendida e atingida, vagas não preenchidas (vazio até as
vagas existirem na rodada), relativo mediano dos vídeos de base do ciclo, e
cada experimento aberto com `settled`, `target`, `median_relative` e
`days_to_target`. A comparação com o ciclo anterior (`cycle_comparison`) diz se
já dá para julgar a mudança que abriu este ciclo; com `verdict_possible: false`,
diga que ainda não dá e por quê.

### 8. Desde o relatório anterior

Compare com o relatório mais recente de `tuning/reports/`: quantos vídeos
assentados são novos e quais achados mudaram. Achado com os mesmos vídeos do
anterior recebe `unchanged_since`. O mesmo dado lido duas vezes não é
confirmação, e o relatório não pode apresentá-lo como se fosse (FR-015).

### 9. Sugestões de experimento

Ao menos duas, ao menos uma de território novo ou de desafio a uma crença
(FR-027). Veja a seção Experimentos. Só repetir o que já funciona faz a base
parar de crescer.

### 10. Recomendação

Manter ou fechar o ciclo, com os motivos, cada um com o número que o sustenta.
Os critérios estão em `references/recommendation.md`. A recomendação existe
para que o operador não precise refazer a análise para decidir; ele pode
decidir o contrário, e isso fica gravado sem precisar de justificativa longa.

### 11. Gravar o relatório

Escreva `tuning/reports/AAAA-MM-DD.yaml` (o id e a numeração do segundo
relatório no mesmo dia estão em `references/records.md`), acrescente o id à
lista `reports` do ciclo aberto e rode `just tuning-check`. `decision` e
`view_url` ficam vazios até os passos 12 e 13.

O registro vem antes da página porque a página é feita a partir dele: o que
não estiver no registro não pode estar na página.

### 12. Publicar a visão de leitura

Siga `references/reading-view.md`: mesma página a cada relatório, privada,
escrita a partir do YAML gravado. Grave o endereço em `view_url`.

No chat, mostre o link, a recomendação e os motivos em poucas linhas, e os dois
ou três achados que mais mudam o que o operador faria. O resto está na página.

### 13. Decisão

Pergunte, de uma vez (com a ferramenta de perguntas, se houver):

- manter ou fechar o ciclo;
- o que fazer com cada experimento aberto (manter, mudar, fechar);
- o que fazer com cada sugestão (abrir, fila, descartar);
- se a fatia de exploração ou a ordem de prioridade mudam.

Grave `decision` no relatório, as sugestões com a decisão, e aplique as
mudanças de experimento (seção Experimentos). Republique a página no mesmo
endereço com a decisão. Rode `just tuning-check` e `just tuning-summary`.

Se o operador decidiu fechar, siga para o Fechamento. Se não, termine com o
lembrete da seção Ao terminar.

## Experimentos

Experimentos podem mudar em qualquer relatório, sem fechar o ciclo (FR-003a),
porque entram na rodada como dados e não mudam nenhum prompt editorial.

**Estado de cada aberto.** Progresso até o alvo, relativo mediano até aqui,
previsão (`days_to_target`) e uma recomendação: manter, mudar ou fechar.
Quando o experimento atingiu o alvo (`target_reached`), ele recebe o veredito
neste relatório (FR-035): `confirmed`, `refuted` ou `inconclusive`, julgado
contra a `decision_rule` escrita quando foi aberto, com os vídeos. Julgar pela
regra antiga é o que impede de ajustar a pergunta ao resultado. Grave o
`outcome`, `status: closed`, e atualize a crença que ele testava (seção
Crenças de `references/recommendation.md`).

**Quantos manter e em que ordem.** A ordem em `exploration.yaml` é a
prioridade: cada vaga do dia vai para o primeiro aberto que tiver história
adequada. Recomende quantos manter abertos e em que ordem, diga quanto tempo
cada um leva nessa ordem com a fatia atual, e avise quando o conjunto é grande
demais para algum concluir (FR-028). A escolha do operador vale.

**Gravar uma mudança.** Toda mudança vai para `exploration.yaml` e para
`experiment_changes` do ciclo aberto, com a data e o id do relatório:

- abrir: experimento novo com `status: open` e **todos** os campos (`kind`,
  `question`, `motivation`, `looks_like`, `sample_target`, `decision_rule`,
  `opened`; `belief` se for desafio). Os vídeos de um experimento só valem se a
  pergunta e a regra de decisão foram escritas antes deles (FR-025). Se o
  operador quer abrir mas falta algum campo, vai para `backlog` com
  `question` e `motivation`;
- mudar: fechar o antigo com `closed_without_verdict` e abrir outro com
  `replaces`. Um experimento aberto nunca é editado no lugar, para que os
  vídeos feitos para uma pergunta não sejam julgados por outra (FR-026);
- fechar antes do alvo: `closed_without_verdict`, com a contagem alcançada;
- mudar a fatia: `share` e `share_since` com a data de hoje, porque a fatia
  atingida é contada a partir dela;
- ideias não abertas vão para `backlog` com a motivação (FR-029).

**Vagas.** Enquanto a rodada diária não reservar vagas de exploração (isso
chega no Milestone 5 da feature 006), um experimento aberto não recebe vídeos:
diga isso ao operador ao abrir um, para que ele não espere progresso no
relatório seguinte.

Mudanças em `exploration.yaml` só valem no servidor depois de `just deploy`.

## Fechamento

Com `close`, ou quando o operador decide fechar no passo 13. A ordem é fixa
(FR-005): primeiro assentar o ciclo que termina, depois propor, depois aplicar.
Se o operador parar antes do passo 5, o ciclo continua aberto: os vereditos e
as crenças atualizadas valem, porque seguem a evidência, mas nada muda em
`src/prompts/` nem nos arquivos de ciclo.

### 1. Vereditos

Todo experimento que atingiu o alvo recebe o veredito (seção Experimentos). Os
que não atingiram aparecem com a contagem e o resultado até aqui, sem veredito
(FR-036), e o operador escolhe manter, mudar ou fechar cada um. Um experimento
mantido continua no ciclo seguinte com os seus vídeos (FR-026).

### 2. Avaliar o ciclo

A partir de `cycle_comparison`, preencha `evaluation`:

- `not_evaluated` quando `verdict_possible` é falso: com menos de 20 vídeos de
  base assentados de um lado, qualquer diferença é ruído;
- `unclear` quando `also_changed` não está vazio (o efeito não é atribuível só
  ao prompt) ou quando as medianas diferem menos de 0,2;
- `helped` ou `hurt` quando diferem 0,2 ou mais.

O relativo compara cada vídeo com os vizinhos no tempo, que em geral são do
mesmo ciclo: uma melhora que atinge todos os vídeos por igual quase não aparece
nele. Diga isso na `note` sempre que o resultado for `unclear` ou
`not_evaluated`, e olhe também `weekly_reach` antes e depois da mudança.

### 3. Crenças

Atualize `beliefs.yaml` a partir dos vereditos e dos achados com evidência de
base: status, evidência, confiança, `last_tested`, e sempre uma entrada nova em
`history` com o relatório ou experimento que causou a mudança (FR-043). Uma
crença só entra na base, ou em "não funciona", com 10 ou mais vídeos.

### 4. Propor mudanças nos prompts

Uma a uma, cada uma com:

- o trecho atual, copiado exatamente do arquivo em `src/prompts/`;
- o trecho proposto;
- a justificativa: o achado (pelo id do relatório), a crença ou o experimento
  que a sustenta, com o número de vídeos.

De onde vêm as propostas:

- achado com evidência de base e confiança ao menos `medium`;
- crença refutada: o trecho que dependia dela (FR-038);
- avaliação `hurt`: a reversão das mudanças que abriram o ciclo, com a
  evidência, gravada com `reverts: <número do ciclo>` (FR-039).

Pista não gera proposta. Se nada justifica mudar, diga que os prompts ficam
como estão e que o ciclo seguinte difere só nos experimentos.

**Como escrever a mudança.** O prompt é lido por um modelo que vai encontrar
histórias que nenhum achado viu. Escreva a razão pela qual a audiência
responde, para que ele aplique a razão (FR-019, Princípio III da constituição):
"quem assiste espera ver a injustiça respondida, e a história que entrega isso
recompensa a espera" generaliza; "em histórias de trabalho, termine com o
troco" não. Não proponha regra do tipo "quando o título tiver X, faça Y"; se o
achado só sustenta uma regra assim, ele ainda é pista. Sem CAPS para dar
ênfase. Leia o prompt inteiro antes de propor: a mudança tem de caber no tom e
na estrutura que já estão lá, e não pode contradizer outro trecho.

### 5. Aprovação

O operador aprova, modifica ou rejeita cada proposta (FR-020). Pergunte uma
por uma, ou em grupos pequenos, sempre com as três partes visíveis. Aplique em
`src/prompts/` só as aprovadas e as modificadas, na redação final. Rejeitada
fica gravada com o motivo que o operador der.

### 6. Fechar e abrir

No ciclo que termina: `closed` com a data de hoje, `evaluation`, `closing`
(`recommendation` do relatório, `decision: close`, nota).

Crie `tuning/cycles/<N+1>.yaml`:

- `opened`: hoje; `deployed: null`; `closed: null`;
- `prompts`: os fingerprints dos arquivos depois das mudanças, e `settings`
  como a receita os grava (os dois comandos estão em
  `references/records.md`);
- `changes`: todas as propostas, inclusive as rejeitadas, com `before`,
  `after`, `justification`, `decision` e `reason`. É isso que liga cada trecho
  de prompt ao ciclo e ao achado que o introduziram (FR-044);
- `experiment_changes`: o que foi aberto, fechado ou reordenado neste
  fechamento; `outside_changes: []`, `reports: []`, `evaluation: null`,
  `closing: null`.

### 7. Plano de exploração

`exploration.yaml`: `cycle` passa a ser o novo número; os experimentos abertos
nesta sessão levam `opened.cycle` do ciclo novo.

### 8. Verificar

```bash
just tuning-check
just tuning-summary
uv run pytest tests/prompts -q
```

O check confirma que os prompts em disco são os que o ciclo novo registra; o
teste confirma que os templates ainda renderizam.

### 9. Entregar

Mostre `git diff --stat` e diga ao operador:

- que o commit é dele, e que depois do commit o relatório e o ciclo fechado não
  mudam mais;
- que os prompts novos e o plano de exploração só valem no servidor depois de
  `just deploy`;
- que no próximo relatório você vai perguntar a data do deploy para preencher
  `deployed` do ciclo novo.

## Mudança de prompt fora da rotina

Coberta no passo 2 do relatório. Se o operador pedir para editar um prompt
fora de um fechamento, explique o custo (os vídeos do ciclo deixam de ser
comparáveis) e sugira fechar o ciclo com essa mudança como proposta. Se ele
quiser mesmo assim, a edição é dele; o relatório seguinte a registra.

## Primeiro uso

O ciclo 1 já existe (`tuning/cycles/001.yaml`), com os prompts de 29 de
setembro de 2026 como linha de base e as crenças do relatório de setembro como
pistas. O primeiro relatório é um relatório comum; ele vai dizer que o ciclo 1
ainda não tem vídeos de base assentados para comparar e que os vídeos
anteriores estão no ciclo 0.

Se não houver ciclo aberto nenhum, pare: a semente de `tuning/` faz parte do
repositório, e criar um ciclo por fora apagaria a linha de base.

## `/prompt-tuning view AAAA-MM-DD`

Refaz a página de um relatório gravado, sem perguntar nada ao operador e sem
rodar `tuning-data`: tudo sai de `tuning/`. Siga a última seção de
`references/reading-view.md`.

## Ao terminar

Sempre, com ou sem fechamento:

- o link da página;
- o que foi escrito em `tuning/` (e em `src/prompts/`, se houve fechamento);
- que o commit é do operador;
- se `exploration.yaml` ou os prompts mudaram, que só valem no servidor depois
  de `just deploy`.
