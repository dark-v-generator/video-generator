# Research: Ciclo de ajuste dos prompts

**Feature**: 006-prompt-tuning-cycle | **Date**: 2026-09-29

Decisões que a especificação deixou para o planejamento, mais as que o código
atual impõe. Nenhuma ficou em aberto.

## 1. Uma chamada ou duas para as duas notas

**Decision**: duas. A nota de base continua sendo a de `evaluate_story.jinja2`.
A nota de exploração vem de um prompt novo, `evaluate_exploration.jinja2`, que
recebe os experimentos abertos como variáveis do template.

**Rationale**: a especificação permite mudar experimentos em qualquer relatório
e congela os prompts até o fechamento do ciclo. Se os experimentos entrassem no
prompt de avaliação, cada mudança alteraria a nota de base de todas as
histórias e os vídeos de base de um mesmo ciclo deixariam de ser comparáveis.
Com os experimentos como dados, o fingerprint do template de exploração só
muda quando a redação do template muda.

**Custo**: uma chamada a mais por finalista. São no máximo 55 finalistas por
dia (11 subreddits × `top_per_sub=5`), no modelo de avaliação
(`deepseek/deepseek-v4-flash`), com entrada do mesmo tamanho da avaliação. Ou
seja, o custo de avaliação dobra, e ele é a menor parte do custo de um vídeo. O
valor em dinheiro não foi medido: o gasto atual de avaliação não está
registrado em lugar nenhum do projeto. Sem experimento aberto a chamada não
acontece.

**Alternatives considered**: (a) uma chamada com as duas notas: rejeitada pelo
motivo acima; (b) dar a nota de exploração só às histórias que a base rejeitou:
rejeitada porque uma história pode ser boa de base e servir a um experimento, e
a especificação pede as duas notas em todo registro (FR-032).

## 2. O que é a nota de base

**Decision**: a nota que já existe (`grade_overall`, 0 a 100, com as cinco
sub-notas). Nenhuma coluna nova para ela.

**Rationale**: "quão bem a história corresponde ao que a evidência sustenta" é
exatamente o que o prompt de avaliação passa a medir à medida que os ciclos o
ajustam. Criar uma terceira nota deixaria duas medindo a mesma coisa.

## 3. Onde e como guardar os registros

**Decision**: diretório `tuning/` na raiz, em YAML, um arquivo por coisa que se
consulta sozinha:

| Arquivo | Conteúdo | Quem escreve |
|---|---|---|
| `exploration.yaml` | ciclo aberto, fatia, `min_fit`, experimentos em ordem de prioridade (abertos, fechados, fila) | skill |
| `beliefs.yaml` | crenças com evidência acumulada e histórico | skill |
| `cycles/NNN.yaml` | um ciclo: datas, versões dos prompts, mudanças de prompt, decisões | skill |
| `reports/AAAA-MM-DD.yaml` | um relatório: período, achados, estado do ciclo, recomendação, decisão | skill |
| `story_labels.csv` | tipo de história e traços do título por `record_id` | skill |
| `README.md` | resumo do conhecimento atual | `just tuning-summary` |

**Rationale**: YAML é o formato que o projeto já valida com pydantic
(`BaseYAMLModel`), abre em qualquer editor e produz diff legível a cada
decisão. Um arquivo por relatório e por ciclo torna "nunca reescrito" (FR-041)
verificável: relatórios antigos não aparecem no diff. Os experimentos ficam em
um arquivo só, com `status`, para que a rodada e a skill leiam a mesma fonte e
a ordem no arquivo seja a prioridade.

**Alternatives considered**: (a) tabelas no SQLite: o banco vive no servidor e
o laptop o recebe por rsync, então qualquer escrita local seria sobrescrita, e
as decisões sairiam do controle de versão; (b) Markdown livre: bom de ler, mas
a rodada não pode depender de texto livre e o verificador não teria o que
verificar; (c) um arquivo único: todo relatório reescreveria o arquivo inteiro.

## 4. Visão de leitura

**Decision**: uma página publicada como Artifact, **a mesma a cada relatório**
(um link só, sempre com o relatório mais recente e o conhecimento atual). O
endereço fica no campo `view_url` do registro do relatório; a skill reusa o do
relatório anterior. PDF fica como impressão da página, sem gerador próprio.

**Rationale**: a visão é descartável por definição (FR-041a), então não há o
que preservar em páginas antigas: o que importa está em `tuning/reports/`. Um
link só é o que o operador consegue deixar aberto. A página segue o tratamento
visual do Video Performance Report, mas é uma página comum, não um canvas de
design: o conteúdo é relatório, e a página é refeita a cada vez a partir do
YAML.

**Alternatives considered**: (a) uma página nova por relatório: acumula links
que ninguém reabre; (b) gerar PDF com biblioteca: dependência nova para algo
que a impressão do navegador resolve; (c) atualizar o canvas existente: ele é o
relatório de setembro e continua sendo a referência de origem das crenças.

## 5. Desempenho relativo aos vizinhos

**Decision**: `relative = views / mediana(views dos 10 vídeos assentados
publicados mais perto no tempo)`, 5 antes e 5 depois quando existem, senão os
10 mais próximos de um lado só; o próprio vídeo fica fora. O horário é o
`scheduled_at` da última tentativa bem-sucedida. Com menos de 5 vizinhos o
relativo é vazio.

**Rationale**: é o método do relatório de setembro, e neutraliza a queda
semanal de alcance (mediana de 1 065 para 430 em setembro). A mediana resiste a
um vídeo viral na vizinhança. Os vizinhos incluem os vídeos de exploração: a
pergunta é "como este vídeo foi contra o que o canal publicava naquela hora".

**Assentado**: publicado pelo menos 7 dias antes da coleta usada, não antes de
hoje. Um vídeo de 8 dias cuja última coleta foi no dia 3 não está assentado.

## 6. Como a fatia fracionária vira vagas inteiras

**Decision**: conta acumulada desde que a fatia vale (`share_since`):

```text
due   = round(share × (total_desde + alvo_de_hoje)) − exploração_desde
slots = clamp(due, 0, max(1, ceil(share × alvo_de_hoje)))
```

Com alvo 3 e fatia 0,25 a sequência é 1, 1, 0, 1 vagas por dia: 3 em 12.

**Rationale**: 25% de 3 vídeos é 0,75 vaga; arredondar por dia daria 33% ou
0%. A conta acumulada converge para a fatia e se corrige sozinha depois de um
dia sem história adequada. O teto diário impede que vários dias vazios
transformem um dia inteiro em exploração. As contagens vêm do histórico
(`goal_counts(since)`), então não há estado novo para guardar.

**Alternatives considered**: sorteio por vaga com probabilidade igual à fatia:
não reproduzível em teste e com variância alta em amostras de 5 por semana.

## 7. Quem ocupa uma vaga de exploração

**Decision**: para cada vaga, o experimento aberto de maior prioridade (ordem
no arquivo) que tenha uma história com `fit ≥ min_fit` ainda não escolhida; a
história é a de maior `fit` para aquele experimento. As escolhidas vão para a
frente da lista de candidatas, com `goal` igual ao id do experimento; o resto
da lista é a ordem de base de hoje. Se a história de exploração falha na
escrita ou na renderização, a próxima da lista (de base) ocupa o lugar e a
vaga conta como não preenchida.

**Rationale**: mantém o laço da rodada como está (percorre a lista até atingir
o alvo). Repor a vaga com a segunda melhor história do experimento exigiria uma
fila com estado dentro do fluxo, para um caso pouco frequente (Princípio I).

**`min_fit`**: padrão 70, no arquivo, ajustável pela skill. A nota de
exploração mede se a história é um **teste justo** da pergunta: uma história
do tipo certo, mas mal contada ou sem desfecho, não testa a pergunta, e o
prompt explica isso em vez de exigir uma nota de base mínima.

## 8. Descoberta devolve mais do que as 10 de base

**Decision**: `find_best_stories(..., experiments=())`. Com experimentos,
devolve as histórias de base de hoje (Excelente/Boa, até 10) mais as que
atingem `min_fit`, sem duplicar. Sem experimentos, o comportamento é o atual.

**Rationale**: um experimento que desafia uma crença ("histórias com
desconhecidos não funcionam") procura justamente histórias que o prompt de
base, já ajustado, avalia baixo. Filtrar pela base antes eliminaria o
experimento.

## 9. A que ciclo um vídeo pertence

**Decision**: coluna `cycle` em `video_records`, copiada de
`exploration.yaml` na produção.

**Rationale**: um ciclo pode fechar sem mudar prompt (só os experimentos
mudam), então o fingerprint não basta; e a data de edição não é a data em que
a mudança passou a valer no servidor. O arquivo implantado é a única fonte que
o servidor tem.

## 10. Mudança de prompt fora da rotina

**Decision**: `cycles/NNN.yaml` do ciclo aberto guarda os fingerprints dos
quatro prompts (`story`, `evaluate_story`, `generate_hashtags`,
`evaluate_exploration`). `just tuning-check` compara com os arquivos em disco.
A skill roda o check primeiro e, se falhar, pergunta o motivo, registra no
relatório e recomenda fechar o ciclo.

**Rationale**: o fingerprint já existe (`prompts.fingerprint`) e já está em
cada registro de vídeo. Nenhum mecanismo novo.

## 11. Classificação do tipo de história

**Decision**: feita pela skill, a partir de título e resumo no pacote de dados,
e gravada em `story_labels.csv` (`record_id, kind, narrator_acts,
title_promise, labelled_at`). A skill só classifica os `record_id` que ainda
não estão no arquivo. As categorias são as do relatório de setembro, listadas
em `references/records.md`; uma categoria nova é registrada no relatório em
que aparece.

**Rationale**: consistência entre relatórios (FR-015). Classificar na produção
foi descartado: as categorias mudam com o aprendizado, e rotular depois permite
reclassificar o passado com uma categoria nova, em uma entrada nova.

## 12. Onde a skill mora

**Decision**: `.claude/skills/prompt-tuning/` no repositório. O `just deploy`
já exclui `.claude/` do rsync.

**Rationale**: a skill descreve a rotina deste projeto, referencia arquivos
dele e muda junto com eles. No diretório do usuário ela ficaria fora do
controle de versão.

## 13. Limites padrão

| Parâmetro | Padrão | Onde |
|---|---|---|
| Período do relatório | 30 dias | argumento de `tuning-data` |
| Vídeos assentados mínimos para haver achados | 30 | argumento de `tuning-data` |
| Idade máxima da última coleta | 3 dias | argumento de `tuning-data` |
| Dias para assentar | 7 | argumento de `tuning-data` |
| Evidência para entrar na base | 10 vídeos | `references/recommendation.md` |
| Fatia de exploração | 0,25 | `exploration.yaml` |
| `min_fit` | 70 | `exploration.yaml` |
| Reteste de crença | 90 dias | `references/recommendation.md` |

Os de código são argumentos com padrão; os de julgamento ficam na skill, com o
motivo de cada um.
