import json
from entities.history import History
import google.generativeai as genai
import os


def __chat(input):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(input)
    return response.text


def generate_history(prompt: str) -> History:
    initial_context = """
        Você é um contador de histórias, e deve contar histórias em uma linguagem
        simples e fácil de entender. As histórias contadas devem usar temas que despertem
        o interesse do público como brigas de família, injustiças, traições, amores proibidos,
        entre outros. As histórias devem ser curtas e objetivas, com no máximo 500 palavras.
    """
    json_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "content": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
    }
    full_message = f"${initial_context}\n ${prompt}\nO resultado deve ser um único objeto JSON que siga o seguinte esquema:\n\n${json_schema}"
    response = __chat(full_message)
    data = json.loads(response)
    return History(**data)
