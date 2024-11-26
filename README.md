# Nome do Projeto: Gerador de Vídeos Narrados

## Descrição

Esse projeto cria histórias com base em um comando enviado para o gemini, faz a narração e gera um vídeo de fundo, renderizando tudo para o formato de vídeo das vertical para as redes sociais.

## Como instalar

### Ambiente virtual (opicional)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Configurar credenciais

Para executar o projeto é preciso ter as seguintes variáveis de ambiente configuradas:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
GOOGLE_API_KEY=...
YOUTUBE_API_KEY=...
```

As variáveis de ambiente são para acessar a API do Google e AWS. 

### Executar

```bash
python main.py
```

Caso tenha dúvidas sobre os parâmetros, execute:

```bash
python main.py --help
```
