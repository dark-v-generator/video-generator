import json
from entities.history import History, MultiplePartHistory
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
            "gender": {
                "description": "Gênero de quem conta a história, pode ser 'male' quando homem e 'female' quando mulher",
                "type": "string",
            },
        },
    },
}

MULTIPLE_PART_HISTORY_SCHEMA = {
    "name": "multiple_part_history_schema",
    "schema": {
        "type": "object",
        "properties": {
            "title": {
                "description": "Título da história",
                "type": "string",
            },
            "parts": {
                "description": "Lista de partes da história",
                "type": "array",
                "items": {"type": "string"},
            },
            "file_name": {
                "description": "Nome do arquivo da história sem extensão",
                "type": "string",
            },
            "gender": {
                "description": "Gênero de quem conta a história, pode ser 'male' quando homem e 'female' quando mulher",
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
        Eu vou te passar uma história que foi postada em um fórum online, você deve traduzi-la e adapta-la para
        narração. Pode substituir abreviações em ingles e português como as seguintes:
        (ingles)"I M24" -> "Eu sou um homem de 24 anos"
        (ingles)"I F20" -> "Eu sou uma mulher de 20 anos"
        (portugues)"Eu H20" -> "Eu sou um homem de 20 anos"
        (portugues)"Eu M24" -> "Eu sou um homem de 24 anos"

        Faça isso com o título e a história, se estiver em ingês traduza mantendo o mais fiel possível, 
        substituindo apenas as abreviações.
        Os demais campos, além de title e content podem ser gerados.
        Aqui está a história que você deve corrigir e traduzir:
        
        Título: {title}

        {content}
    """.format(
        title=reddit_post.title,
        content=reddit_post.content,
    )
    response = __chat_history_teller(prompt, HISTORY_SCHEMA)
    return History(
        **response,
        reddit_community=reddit_post.community,
        reddit_post_author=reddit_post.author,
        reddit_community_url_photo=reddit_post.community_url_photo,
    )


def convert_reddit_post_to_multiple_part_history(
    reddit_post: RedditPost,
    number_of_parts: int,
) -> MultiplePartHistory:
    prompt = """
        Eu vou te passar uma história que foi postada em um fórum online, você deve traduzi-la e adapta-la para
        narração, substituindo abreviações em ingles e português como as seguintes:
        "I M24" -> "Eu sou um homem de 24 anos"
        "I F20" -> "Eu sou uma mulher de 20 anos"
        "Eu H20" -> "Eu sou um homem de 20 anos"
        "Eu M24" -> "Eu sou um homem de 24 anos"

        Além disso, você deve dividir a história completa em {number_of_parts} partes, mantendo a ordem original. 

        Se estiver em ingês traduza mantendo o mais fiel possível, não mude nem adapte a história, apenas 
        substitua as abreviações listadas acima e traduza a história se preciso.
        Os demais campos, além de title e parts podem ser gerados.
        Aqui está a história que você deve adaptar, traduzir e dividir em {number_of_parts} partes:
        
        Título: {title}

        {content}
    """.format(
        title=reddit_post.title,
        content=reddit_post.content,
        number_of_parts=number_of_parts,
    )
    response = __chat_history_teller(prompt, MULTIPLE_PART_HISTORY_SCHEMA)
    return MultiplePartHistory(
        **response,
        reddit_community=reddit_post.community,
        reddit_post_author=reddit_post.author,
        reddit_community_url_photo=reddit_post.community_url_photo,
    )
