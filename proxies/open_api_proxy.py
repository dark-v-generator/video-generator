import json
from entities.history import History
from openai import OpenAI


def generate_history(prompt: str) -> History:
    response_schema = (
        {
            "name": "history_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "description": "Título da história",
                        "type": "string",
                    },
                    "subtitle": {
                        "description": "Subtítulo da história",
                        "type": "string",
                    },
                    "description": {
                        "description": "Breve descrição da história",
                        "type": "string",
                    },
                    "content": {
                        "description": "Conteúdo da história",
                        "type": "string",
                    },
                    "hashtags": {
                        "description": "Lista de hashtags para as redes sociais",
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "file_name": {
                        "description": "Nome do arquivo da história sem extensão",
                        "type": "string",
                    },
                },
            },
        },
    )
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Você é um contador de histórias"},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": response_schema,
        },
    )
    raw_data = response.choices[0].message.content
    data = json.loads(raw_data)
    return History(**data)
