---
name: prepare-story
description: Conduz a preparação local de uma história do Reddit para o pipeline diário — descobrir candidatas, escrever o roteiro seguindo o prompt editorial do servidor e validar o pacote. Use quando o operador pedir para preparar, escolher, roteirizar ou revisar uma história, com ou sem uma URL do Reddit em mãos.
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
aprova o roteiro e autoriza o envio. Essas três decisões são dele porque o custo de
errar é um vídeo publicado no canal dele; as suas são reversíveis com um comando.

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

### 3. Escrever o roteiro

```bash
just story-prompt N
```

A saída é, byte a byte, o prompt que o servidor enviaria ao modelo de roteiro, já com o
post embutido. Siga-o como se fosse você o modelo e responda no JSON que ele pede
(`title`, `narrator_gender`, `script`).

Depois monte o pacote completo em `output/prepared/<post_id>.json`, onde `<post_id>` é
o id que aparece na URL do post depois de `/comments/`. O esquema, com um exemplo
mínimo válido, está em `specs/003-local-story-prep/contracts/prepared_story_package.md`.
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

## Depois daqui

Ouvir a narração (`just story-preview`) e enfileirar o pacote no servidor
(`just story-ship`, `just story-queue`) chegam no Milestone 2 desta feature. Por
enquanto o fluxo termina no pacote validado, e o envio é manual.
