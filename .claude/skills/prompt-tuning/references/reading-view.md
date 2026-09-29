# A visão de leitura

Uma página para o operador ler o relatório em poucos minutos e decidir
(SC-001). Ela é descartável: tudo o que mostra está em
`tuning/reports/<id>.yaml` ou em outro arquivo de `tuning/` (FR-041a). Se a
página se perder, `/prompt-tuning view AAAA-MM-DD` a refaz a partir do
registro, sem perguntar nada ao operador (SC-014).

Por isso a regra de ouro: a página é escrita **a partir do YAML do relatório já
gravado**, não do pacote de dados nem da conversa. Um número que só existe no
pacote e não foi para o relatório não aparece na página; se ele importa para a
leitura, ele vai primeiro para o relatório.

## Um endereço só

A página é a mesma a cada relatório: o operador guarda um link e ele sempre
mostra o relatório mais recente. Para isso:

1. procure o `view_url` do relatório anterior mais recente que tenha um
   (`tuning/reports/*.yaml`, do mais novo para o mais velho);
2. se houver, leia a página com a ferramenta de Artifact (`action: read`,
   `url: <view_url>`) e publique a nova versão nesse `url`: publicar em um
   artifact que a conversa ainda não leu é recusado;
3. se não houver (primeiro relatório), publique um artifact novo, com ícone
   `chart`;
4. grave o endereço em `view_url` do relatório novo.

A página é privada (é o padrão do artifact): tem dados do canal do operador.
Não peça para compartilhar nem ofereça link público.

Antes de escrever o HTML, carregue o skill `artifact-design`, que é o contrato
de qualquer página publicada (título, tokens de cor, modo escuro, largura de
celular). O arquivo vai no scratchpad da sessão, não no repositório.

## Tratamento visual

O do Video Performance Report de setembro, para que as duas leituras pareçam
parte da mesma coisa:

| Papel | Valor |
|---|---|
| Títulos e números grandes | Fraunces 600 (Google Fonts) |
| Texto | IBM Plex Sans 400/500/600 |
| Rótulos, contagens, ids | IBM Plex Mono 400/500, rótulos em caixa alta com espaçamento |
| Fundo | `#F4F1EA`; cartões `#FFFFFF` com borda `#D9D3C7` |
| Texto / secundário | `#18181B` / `#4F4B45` |
| Acima das vizinhas | azul `#2A45B0` (forte), `#E4E9F8` (claro) |
| Na média | `#ECE8DF` |
| Abaixo das vizinhas | laranja `#A8410F` sobre `#F8E6DA` |

Azul e laranja diferem em claridade além do tom, então a leitura não depende
de enxergar cor. Defina essas cores como tokens em `:root` e os equivalentes
escuros no modo escuro, como o `artifact-design` pede.

Números com o multiplicador do relatório ("2,4×"), em vírgula decimal, porque o
operador lê em português. O relativo é a unidade da página inteira: toda
comparação diz "contra as vizinhas".

## Seções, nesta ordem

Cada seção diz de onde tira o conteúdo. `R` é o relatório, `C` o ciclo aberto
(`tuning/cycles/NNN.yaml`), `E` o `exploration.yaml`, `B` o `beliefs.yaml`.

1. **Cabeçalho.** Data do relatório (`R.id`), período (`R.period`), vídeos
   considerados e excluídos com o motivo (`R.videos`), data dos dados
   (`R.data_as_of`), ciclo aberto e há quantos dias (`R.cycle`, `C.opened`),
   versões dos prompts (`C.prompts`).
2. **Recomendação.** Manter ou fechar, grande, com os motivos
   (`R.recommendation`). É a primeira coisa depois do cabeçalho porque é o que
   o operador precisa decidir; o resto sustenta a decisão.
3. **O que mudou desde o relatório anterior** (`R.since_previous`): vídeos
   novos e achados que mudaram. Sem relatório anterior, diga que este é o
   primeiro.
4. **O que funcionou / o que não funcionou / inconclusivo** (`R.findings` por
   `direction`). Cada achado: a frase, o relativo mediano em destaque, o
   número de vídeos, a confiança. Pistas (`is_lead`) marcadas como pistas, com
   o aviso de que não mudam a base. Achado com `unchanged_since`: "sem dado
   novo desde <id>".
5. **Distorções do período** (`R.distortions`), com o que cada uma afeta. O
   gráfico semanal do canal entra aqui: barras da mediana de views por semana
   (`R.weekly_reach`), com o número de vídeos de cada semana. Uma semana com
   poucos vídeos (a última, em geral) aparece mais clara, porque a mediana
   dela ainda vai mudar.
6. **Experimentos** (`R.cycle_state.experiments`, com a pergunta de `E`):
   barra de progresso de `settled` até `target`, relativo mediano até aqui e a
   previsão (`days_to_target`). Sem experimento aberto, diga que não há, e
   que as vagas só existem na rodada depois do Milestone 5.
7. **Fatia de exploração** (`R.cycle_state`): pretendida contra atingida, e as
   vagas não preenchidas quando houver.
8. **Sugestões de experimento** (`R.suggestions`): pergunta, tipo, motivação e
   o que o operador decidiu (aberta, fila, descartada). Na primeira
   publicação, antes da decisão, mostre "a decidir".
9. **Conhecimento atual** (`B`): base, o que não funciona, pistas e
   contestadas, cada crença com a evidência (vídeos e relativo), a confiança e
   a data do último teste.

Um número que a página quer mostrar e que o relatório não tem é sinal de que
falta um campo no relatório, não de que a página pode buscá-lo no pacote:
página e relatório dizem a mesma coisa.

## Depois da decisão

A página é publicada antes da decisão do operador (passo 12 do fluxo). Depois
que ele decide (passo 13), republique no mesmo endereço com a decisão e as
mudanças de experimento, para que a página e o registro terminem iguais.

## Refazer: `/prompt-tuning view AAAA-MM-DD`

Leia `tuning/reports/AAAA-MM-DD.yaml`, o ciclo dele, `exploration.yaml` e
`beliefs.yaml`, e monte a página com as mesmas seções. A seção 9 mostra o
conhecimento de hoje, não o do dia do relatório, e diz isso. Publique no
`view_url` do relatório se ele ainda abrir; senão, em um artifact novo, e diga
ao operador o endereço novo (o relatório não é reescrito para guardá-lo).
