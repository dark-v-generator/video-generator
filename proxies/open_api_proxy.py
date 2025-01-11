import json
from entities.history import History
from entities.reddit import RedditPost
from openai import OpenAI

HISTORY_SCHEMA = {
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
}


def __chat_history_teller(input, schema):
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Você é um contador de histórias"},
            {"role": "user", "content": input},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
    raw_data = response.choices[0].message.content
    return json.loads(raw_data)


def generate_history(prompt: str) -> History:
    response = __chat_history_teller(prompt, HISTORY_SCHEMA)
    return History(**response)


def convert_reddit_post_to_history(reddit_post: RedditPost) -> History:
    prompt = """
        Você vai corrigir e se precisar traduzir uma história que foi postada em um fórum online. Corriga os 
        erros de escrita e concordância mais graves, mas mantenha ao máximo a estrutura original da história.
        Aqui está a história que você deve corrigir e traduzir:
        {title}

        {content}
    """.format(
        title=reddit_post.title,
        content=reddit_post.content,
    )
    response = __chat_history_teller(prompt, HISTORY_SCHEMA)
    return History(**response)
