# Histórias preparadas no laptop

A metade criativa do pipeline diário — escolher a história e escrever o roteiro —
sai do servidor e passa a rodar no seu laptop, com o assistente da sua assinatura
do Claude Code no lugar dos modelos pagos por token. O servidor continua fazendo
o que já fazia: narrar, montar o vídeo e agendar no TikTok.

Por que existe: a avaliação e o roteiro eram as duas chamadas caras de cada run
diária, e eram justamente as duas em que você queria opinar. Preparando a história
localmente, você lê a shortlist, escolhe, revisa o roteiro e ouve a narração antes
que qualquer vídeo seja renderizado — e a run diária no servidor não gasta nenhum
token de LLM para as histórias que vieram da fila.

Com a fila vazia, o servidor se comporta exatamente como antes: busca, avalia e
escreve o roteiro sozinho. Nada do fluxo antigo foi removido.

## Os sete passos

O caminho inteiro cabe no skill `/prepare-story` do Claude Code, que conduz os
passos e chama as receitas abaixo. Você também pode rodá-las na mão.

### 1. Descobrir candidatas

```bash
just story-find
```

Ranqueia os posts das comunidades de `evaluation.subreddits` com o score
determinístico (upvotes relativos, comentários, tamanho, frescor) — sem nenhuma
chamada de LLM. Grava `output/prepared/candidates.json` e imprime a tabela com
rank, score, comunidade, pontos, comentários, tamanho, título e link.

Posts que já estão na sua pasta de pacotes não voltam a aparecer.

### 2. Ler a história

```bash
just story-show 1
```

Imprime o texto original completo do candidato pelo número do rank. Se você já tem
a URL de um post em mãos, pule a descoberta:

```bash
uv run python scripts/prepare_story.py show --url <url do Reddit>
```

O post entra em `candidates.json` como o próximo rank, e o resto do fluxo segue igual.

### 3. Pegar o prompt editorial

```bash
just story-prompt 1
```

Imprime, byte a byte, o mesmo prompt que o servidor enviaria ao modelo para esse
post e idioma — ele é renderizado do mesmo `src/proxies/prompts/story.jinja2`. É o
que garante que um roteiro escrito aqui siga as mesmas regras do roteiro automático:
existe uma fonte só de regras editoriais, e ela não foi copiada para lugar nenhum.

### 4. Escrever o pacote

O assistente escreve `output/prepared/<post_id>.json` seguindo
[o contrato do pacote](../specs/003-local-story-prep/contracts/prepared_story_package.md):
título de capa, roteiro, gênero do narrador, resumo de 3 a 5 frases e, se quiser,
as hashtags (sem `#`). Hashtags no pacote fazem o servidor pular a chamada de LLM
que as geraria.

### 5. Validar

```bash
just story-validate output/prepared/<post_id>.json
```

Acusa campo faltando, roteiro vazio, idioma diferente do `config.language` e cada
palavra que a censura de produção mudaria, com o contexto em volta. Sai com 1 se
algo falhar, `✓` e 0 quando passa. A mesma validação roda de novo no servidor, então
um pacote que passa aqui não é recusado lá por outro critério.

### 6. Ouvir

```bash
just story-preview output/prepared/<post_id>.json
```

Gera `<post_id>.preview.mp3` ao lado do pacote com a voz de `resolved_gender`, o
idioma do pacote e a velocidade de produção, e imprime a duração. Se você editar o
roteiro e rodar de novo, o mp3 é substituído. Ouvir antes de enviar é mais barato do
que descobrir o problema num vídeo já renderizado.

### 7. Enviar

```bash
just story-ship output/prepared/<post_id>.json
just story-queue
```

`ship` valida o pacote antes de tocar na rede, cria `inbox/` no destino e copia o
arquivo por `scp`. Se já existe um pacote com o mesmo `post_id` na fila, ele pergunta
antes de substituir (`--force` pula a pergunta). O arquivo local nunca é movido nem
alterado — a cópia em `output/prepared/` continua sendo a sua.

`queue` lista o que está esperando no servidor. No Telegram, `/prepared` mostra a
mesma coisa.

## O que o servidor faz com a fila

A raiz da fila é `bots.satisfying_bot.prepared_stories.inbox_dir` (default
`.storage/prepared`) e o estado de um pacote é o diretório em que ele está:

```text
.storage/prepared/
├── inbox/   <post_id>.json                          # esperando a próxima run
├── done/    <post_id>.json + <post_id>.outcome.json # produzido (e agendado)
└── failed/  <post_id>.json + <post_id>.error.txt    # recusado ou quebrou
```

Na run diária, o job consome a fila em ordem de chegada antes de procurar qualquer
coisa no Reddit. Para cada pacote da fila ele pula a avaliação e o roteiro, usa o
título e o texto exatamente como você escreveu, e manda para o mesmo caminho de
narração, vídeo e agendamento. O manifesto de cada vídeo em `output/daily/` ganha
`"source": "prepared"` ou `"source": "auto"`, então dá para saber de onde cada
vídeo veio depois.

Se a fila tiver menos pacotes do que a meta do dia, o job completa o restante por
descoberta automática, excluindo o que já está na fila, o que já foi produzido e o
que já está agendado no `tiktok_publish_log.csv`. Para publicar só o que você
preparou, desligue isso:

```yaml
bots:
  satisfying_bot:
    prepared_stories:
      fill_with_discovery: false
```

Com a fila vazia e essa opção ligada (o default), a run é idêntica à de antes desta
feature.

## Quando um pacote vai para `failed/`

Um pacote cai em `failed/` com um `<post_id>.error.txt` ao lado em quatro situações:

- o JSON não parseia ou tem uma `version` que o servidor não conhece;
- a validação recusa (idioma diferente, palavra censurada, gênero incoerente);
- a geração do vídeo falha;
- a publicação no TikTok falha.

Nos dois primeiros casos nenhum vídeo chega a ser renderizado, e a run segue para a
próxima história. Nos outros dois, o erro é o mesmo que aparece no Telegram.

Para reenviar um pacote depois de corrigi-lo, edite a cópia local em
`output/prepared/` e rode `just story-ship` de novo com `--force` — o pacote velho
continua em `failed/` como registro.

## Configuração

Os três campos ficam sob `bots.satisfying_bot.prepared_stories`; veja a tabela em
[configuration.md](./configuration.md).
