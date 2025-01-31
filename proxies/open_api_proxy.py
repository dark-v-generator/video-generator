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
        narração seguindo o seguinte:
        
        1. Nesses foruns é comum usar essas abreviações para identificação, subistitua elas:
        (ingles)"I M24" -> "Eu sou um homem de 24 anos"
        (ingles)"I F20" -> "Eu sou uma mulher de 20 anos"
        (portugues)"Eu H20" -> "Eu sou um homem de 20 anos"
        (portugues)"Eu M24" -> "Eu sou um homem de 24 anos"

        2. Ao traduzir os textos do ingês para o português, algumas expressões podem ficar estranhas, portanto
        pode adaptar termos, expressões ou palavras para algo mais comum no brasil, como "academy" poderia ser
        traduzido para "escola" por exemplo, pois esse termo é mais comum

        3. Corriga as pontuações do texto e adapte trechos para que a leitura fique mais flúida e com sentido. 
        Removendo excessos de pontuação, inserindo virgualas onde necessários e corrigindo as pausas adequadamente.

        4. Mantenha a história o mais fiel possível, não crie nada a mais, não mude a história, apenas traduza (se 
        necessário) e faça o que foi dito, fora isso tente manter o mais original possível com todo seu conteúdo.

        Aqui está a história:
        
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
        narração seguindo o seguinte:
        
        1. Nesses foruns é comum usar essas abreviações para identificação, subistitua elas:
        (ingles)"I M24" -> "Eu sou um homem de 24 anos"
        (ingles)"I F20" -> "Eu sou uma mulher de 20 anos"
        (portugues)"Eu H20" -> "Eu sou um homem de 20 anos"
        (portugues)"Eu M24" -> "Eu sou um homem de 24 anos"

        2. Ao traduzir os textos do ingês para o português, algumas expressões podem ficar estranhas, portanto
        pode adaptar termos, expressões ou palavras para algo mais comum no brasil, como "academy" poderia ser
        traduzido para "escola" por exemplo, pois esse termo é mais comum

        3. Corriga as pontuações do texto e adapte trechos para que a leitura fique mais flúida e com sentido. 
        Removendo excessos de pontuação, inserindo virgualas onde necessários e corrigindo as pausas adequadamente.

        4. Divida a história em exatamente {number_of_parts} partes, onde cada parte deve terminar em um momento 
        que disperte a curiosidade do leitor para a próxima parte.

        5. Mantenha a história o mais fiel possível, não crie nada a mais, não mude a história, apenas traduza (se 
        necessário) e faça o que foi dito, fora isso tente manter o mais original possível com todo seu conteúdo.

        Aqui está a história:
        
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
