---
name: prepare-story
description: Conduz a preparação local de uma história do Reddit para o pipeline diário — descobrir candidatas, escrever o roteiro seguindo o prompt editorial do servidor, validar o pacote, ouvir a narração e enfileirá-lo no servidor. Use quando o operador pedir para preparar, escolher, roteirizar, revisar, ouvir ou enviar uma história, com ou sem uma URL do Reddit em mãos.
---

# Preparar uma história localmente

## Por que este fluxo existe

O servidor gasta dois modelos pagos por história: um avalia as candidatas do dia e
outro escreve o roteiro. Ambos os julgamentos são coisas que você já faz aqui, na
assinatura que o operador está pagando de qualquer forma. Este fluxo move essa metade
criativa para o laptop e entrega ao servidor um pacote pronto — a produção do vídeo
(voz, legendas, capa, publicação) continua exatamente como está.

Duas consequências práticas guiam tudo abaixo. A primeira é que nada aqui pode chamar
um modelo pago: os comandos só ranqueiam posts com métricas determinísticas e renderizam
templates. A segunda é que o servidor não muda de critério, então o roteiro precisa
sair das mesmas regras editoriais que ele usaria — por isso você lê o prompt renderizado
em vez de escrever por conta própria.

## O que é seu e o que é do operador

Você ranqueia, argumenta, redige e revisa. O operador escolhe qual história vira vídeo,
escolhe entre um vídeo e duas partes, aprova o roteiro e autoriza o envio. Essas quatro
decisões são dele porque o custo de errar é um vídeo publicado no canal dele; as suas
são reversíveis com um comando.

## Passos

### 1. Descobrir candidatas

Se o operador trouxe uma URL do Reddit, pule para o passo 2 com ela. Caso contrário:

```bash
just story-find
```

O comando ranqueia os posts do dia por engajamento, tamanho, qualidade textual e
frescor, grava `output/prepared/candidates.json` e já exclui o que você preparou antes.
Ele aceita os mesmos argumentos do script (`--sort`, `--time`, `--sub r/x`, `--top-per-sub`)
quando o operador quiser um recorte diferente.

### 2. Propor uma shortlist

Leia `output/prepared/candidates.json` e, se precisar do texto completo de alguma,
`just story-show N`. Com uma URL em mãos, use `just story-show --url <url>`: o post entra
no arquivo como o próximo rank, e os passos seguintes funcionam igual.

Escolha as 3 a 5 mais promissoras e defenda cada uma em uma linha. A lente para julgar
é a de `src/proxies/prompts/evaluate_story.jinja2`, que é o que o servidor usaria:
retenção nos primeiros segundos, qualidade do arco narrativo, potencial de gerar debate
e compartilhamento, adequação ao formato narrado com fundo satisfatório, e força do
gancho. Não são notas para preencher — são as perguntas que separam uma história que
prende de uma que o espectador rola para baixo. Diga também quando nenhuma candidata
convence; uma lista fraca é informação útil.

Pergunte qual delas o operador quer e espere a resposta.

### 3. Escolher o formato e escrever o roteiro

Antes do prompt, decida com o operador se a história vira um vídeo ou duas partes. Duas
partes valem a pena quando a história tem um gancho natural antes do desfecho — uma
revelação que dá para segurar — ou quando o roteiro único ficaria longo demais para
prender até o fim (na prática, quando a prévia passa de uns seis minutos). Sugira o
formato que você acha melhor e diga por quê, mas quem decide é o operador: duas partes
dobram o alcance quando o gancho funciona e desperdiçam os dois vídeos quando não.

Um vídeo:

```bash
just story-prompt N
```

Duas partes:

```bash
just story-prompt N --two-part
```

A saída é, byte a byte, o prompt que o servidor enviaria ao modelo de roteiro, já com o
post embutido. Siga-o como se fosse você o modelo e responda no JSON que ele pede —
`title`, `narrator_gender` e `script` no formato único; `title`, `narrator_gender`,
`part1` e `part2` no de duas partes.

Depois monte o pacote completo em `output/prepared/<post_id>.json`, onde `<post_id>` é
o id que aparece na URL do post depois de `/comments/`. O esquema das duas formas, com
um exemplo mínimo válido de cada, está em
`specs/003-local-story-prep/contracts/prepared_story_package.md`. Um pacote de duas
partes tem `"version": 2` e troca `script_text` por `part1_text` e `part2_text`; o
`story_title` é um só, sem sufixo — o servidor acrescenta ` - Parte 1` e ` - Parte 2`
nas capas. A parte 1 precisa terminar com a chamada que o prompt fixa
(`Curta e me siga para a parte 2.` em português), e a validação recusa o pacote se ela
faltar.

Dois campos não vêm do prompt e são seus:

- `summary`: 3 a 5 frases cobrindo os pontos principais da trama. O servidor usa isso no
  manifesto e como entrada das hashtags, então escreva para quem não leu a história.
- `hashtags`: lista sem o `#`. Preenchida, ela economiza mais uma chamada de modelo no
  servidor; omitida, ele gera as dele.

### 4. Validar

```bash
just story-validate output/prepared/<post_id>.json
```

A validação cobre o que o servidor recusaria depois — campo faltando, idioma diferente
do configurado, palavra que a censura de produção alteraria — e aponta o trecho exato.
Corrija e rode de novo até sair `✓`. Vale a pena conferir aqui e não lá: um pacote
recusado no servidor custa o vídeo do dia.

### 5. Revisar com o operador

Mostre o roteiro e escute. Enquanto a revisão não for aprovada, mantenha o arquivo
anterior no lugar — se o operador preferir a versão de antes, ela precisa existir.
Escreva a nova versão por cima só depois do aval dele, e valide de novo.

### 6. Ouvir a narração

```bash
just story-preview output/prepared/<post_id>.json
```

O mp3 sai em `output/prepared/<post_id>.preview.mp3`, com a voz do `resolved_gender` e
a velocidade de produção — é literalmente o áudio que o vídeo teria. Um pacote de duas
partes gera dois arquivos, `<post_id>.part1.preview.mp3` e `<post_id>.part2.preview.mp3`,
e o comando imprime a duração de cada um e o total.

Peça ao operador para ouvir. Um roteiro que lê bem nem sempre soa bem: frase longa
demais, nome difícil de pronunciar, sequência de números. Nas duas partes, o que se
ouve também é se a parte 1 realmente fecha num gancho e se cada metade tem duração que
se sustenta sozinha — se a parte 1 acabar sem tensão, é sinal de que a história era de
um vídeo só. Se ele pedir ajustes, volte ao passo 5 e gere a prévia de novo (os
arquivos são substituídos).

### 7. Enviar para a fila

Só depois de o operador dizer, com todas as letras, que quer enviar:

```bash
just story-ship output/prepared/<post_id>.json
```

O comando valida de novo, cria a `inbox` remota se faltar e copia o pacote. Ele
pergunta antes de substituir uma duplicata e nunca mexe no arquivo local: se a rede
cair no meio, nada se perde e basta repetir. Se o pacote não passar na validação, ele
recusa sem tocar na rede — volte ao passo 4.

Feche mostrando o que está esperando o próximo job diário:

```bash
just story-queue
```

A partir daqui o servidor assume: ele produz o vídeo com o roteiro verbatim e agenda a
publicação. Um pacote de duas partes vira dois vídeos, agendados em slots consecutivos
com as mesmas hashtags. Nada do que você escreveu é reinterpretado por outro modelo.
