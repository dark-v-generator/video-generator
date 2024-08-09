# Nome do Projeto: Gerador de Vídeos Narrados

## Descrição

Este projeto é uma aplicação gráfica construída com Tkinter que permite gerar vídeos narrados. A aplicação aceita um áudio, uma capa e um vídeo de fundo fornecidos pelo usuário. Além disso, é possível adicionar uma imagem final e uma marca d'água aos vídeos.

## Estrutura do Projeto

O projeto possui a seguinte estrutura de diretórios e arquivos:

```
.
├── interface
│   ├── combo_select.py
│   ├── configuration.py
│   ├── configuration_window.py
│   ├── file_dialog.py
│   ├── main_app.py
│   └── task_frame_with_progress.py
├── editor
│   ├── audio.py
│   ├── background_video.py
│   ├── image_clip_helper.py
│   └── video_generator.py
└── main.py
```

### Arquivos e Diretórios

- `interface/`: Este diretório contém todos os módulos relacionados à interface do usuário.
  - `combo_select.py`: Módulo para o combobox de seleção.
  - `configuration.py`: Módulo de configuração da aplicação.
  - `configuration_window.py`: Janela de configurações.
  - `file_dialog.py`: Diálogo para seleção de arquivos.
  - `main_app.py`: Classe principal que gerencia a interface do usuário.
  - `task_frame_with_progress.py`: Frame para mostrar o progresso das tarefas.

- `editor/`: Este diretório contém os módulos para a edição e geração de vídeos.
  - `audio.py`: Módulo para manipular áudio.
  - `background_video.py`: Módulo para manipular o vídeo de fundo.
  - `image_clip_helper.py`: Módulo auxiliar para manipulação de imagens.
  - `video_generator.py`: Módulo para gerar um vídeo com base nos parâmetros fornecidos.

- `main.py`: Este é o ponto de entrada do programa e é responsável por iniciar a aplicação.

## Como Executar o Projeto

1. Certifique-se de ter Python 3.x instalado.
2. Instale todas as dependências necessárias
3. Execute o script `main.py` para iniciar o aplicativo:
    ```
    python main.py
    ```

## Gerando um Executável

### Usando PyInstaller

1. Instale o PyInstaller:
    ```
    pip install pyinstaller
    ```
2. Gere o arquivo executável:
    ```
    pyinstaller --onefile --hidden-import=moviepy main.py
    ```
3. O arquivo executável será gerado no diretório `dist`.

## Contribuição

Sinta-se à vontade para contribuir para este projeto. Faça um fork do repositório, crie uma nova branch e envie suas alterações como um pull request.