import json
from entities.history import History
from openai import OpenAI

def generate_history(prompt:str) -> History:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {
                "role": "system", 
                "content": """
                    Você é um contador de histórias, e deve contar histórias em uma linguagem
                    simples e fácil de entender. As histórias contadas devem usar temas que despertem
                    o interesse do público como brigas de família, injustiças, traições, amores proibidos,
                    entre outros. As histórias devem ser curtas e objetivas, com no máximo 500 palavras.
                """
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "history_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "description": "Título da história",
                            "type": "string"
                        },
                        "description": {
                            "description": "Breve descrição da história",
                            "type": "string"
                        },
                        "content": {
                            "description": "Conteúdo da história",
                            "type": "string"
                        },
                        "hashtags": {
                            "description": "Lista de hashtags para as redes sociais",
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    )
    raw_data = response.choices[0].message.content
    data = json.loads(raw_data)
    return History(**data)