# Nome do Projeto: Gerador de Vídeos Narrados

## Descrição

Esse projeto cria histórias com base em um comando enviado para o gemini, faz a narração e gera um vídeo de fundo, renderizando tudo para o formato de vídeo das vertical para as redes sociais.

## Como instalar

### Pré-requisitos

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/) - um gerenciador de pacotes Python rápido:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Ou via pip
pip install uv
```

### Instalar dependências

```bash
# Instalar todas as dependências
uv sync

# Ou instalar com dependências de desenvolvimento
uv sync --extra dev
```

### Usando o Makefile (recomendado)

```bash
# Instalar tudo (frontend + backend)
make install

# Instalar apenas dependências de desenvolvimento
make install-dev
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
# Usando uv (recomendado)
uv run python main.py

# Ou usando o Makefile
make run

# Para o servidor de desenvolvimento
uv run python -m uvicorn src.main_fastapi:app --reload
```

Caso tenha dúvidas sobre os parâmetros, execute:

```bash
uv run python main.py --help
```

### Comandos úteis com uv

```bash
# Adicionar nova dependência
uv add package-name

# Adicionar dependência de desenvolvimento
uv add --dev package-name

# Atualizar dependências
uv lock --upgrade

# Executar testes
uv run pytest

# Executar scripts
uv run python script.py
```
