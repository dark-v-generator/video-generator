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
            "content": {
                "description": "Conteúdo da história",
                "type": "string",
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
        
        - Nesses foruns é comum usar essas abreviações para identificação, subistitua elas:
        (ingles)"I M24" -> "Eu sou um homem de 24 anos"
        (ingles)"I F20" -> "Eu sou uma mulher de 20 anos"
        (portugues)"Eu H20" -> "Eu sou um homem de 20 anos"
        (portugues)"Eu M24" -> "Eu sou um homem de 24 anos"

        - Ao traduzir os textos do ingês para o português, algumas expressões podem ficar estranhas, portanto
        pode adaptar termos, expressões ou palavras para algo mais comum no brasil, como "academy" poderia ser
        traduzido para "escola" por exemplo, pois esse termo é mais comum

        - O texto será usado para narração e será publicado nas redes sociais portando adapte alguns termos 
        como "você que está lendo" para "você que está escutando", "podem perguntar" para "podem deixar um comentário"
        e outros termos que só fazem sentido no forum podem ser adaptados ou removidos, para a narração ser publicada

        - Corriga as pontuações do texto e adapte trechos para que a narração fique mais flúida e melhor de entender,
        caso seja necessário. Removendo excessos de pontuação, inserindo virgualas onde necessários 
        e corrigindo as pausas adequadamente.

        - Mantenha a história o mais fiel possível, não crie novos termos, não mude a história, apenas traduza (se 
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
    system_message = """
        Você é um assistente de revisão de histórias.
        Eu vou te passar uma história que foi postada em um fórum online, você deve traduzi-la e adapta-la para
        narração e dividila em partes, seguindo o seguinte:
        
        - Nesses foruns é comum usar essas abreviações para identificação, subistitua elas:
        (ingles)"I M24" -> "Eu sou um homem de 24 anos"
        (ingles)"I F20" -> "Eu sou uma mulher de 20 anos"
        (portugues)"Eu H20" -> "Eu sou um homem de 20 anos"
        (portugues)"Eu M24" -> "Eu sou um homem de 24 anos"

        - Ao traduzir os textos do ingês para o português, algumas expressões podem ficar estranhas, portanto
        pode adaptar termos, expressões ou palavras para algo mais comum no brasil, como "academy" poderia ser
        traduzido para "escola" por exemplo, pois esse termo é mais comum

        - O texto será usado para narração e será publicado nas redes sociais portando adapte alguns termos 
        como "você que está lendo" para "você que está escutando", "podem perguntar" para "podem deixar um comentário"
        e outros termos que só fazem sentido no forum podem ser adaptados ou removidos, para a narração ser publicada

        - Corriga as pontuações do texto e adapte trechos para que a narração fique mais flúida e melhor de entender,
        caso seja necessário. Removendo excessos de pontuação, inserindo virgualas onde necessários 
        e corrigindo as pausas adequadamente.

        - Mantenha a história o mais fiel possível, não crie novos termos, não mude a história, apenas traduza (se 
        necessário) e faça o que foi dito, fora isso tente manter o mais original possível com todo seu conteúdo.

        - A história deve ser dividida em algumas partes, o número exato será passado. As partes serão vídeos diferentes, 
        portanto de uma parte para outra tente finalizar em um ponto alto da história, despertando o interesse para 
        a próxima parte. Caso não seja possível, apenas divida a história.

        Aqui está a história:
        
    """

    schema = {
        "name": "multiple_part_history_schema",
        "schema": {
            "type": "object",
            "properties": {
                "title": {
                    "description": "Título da história",
                    "type": "string",
                },
                "parts": {
                    "description": f"Lista de partes da história, deve ter tamanho {number_of_parts}",
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

    user_message = """
        Essa história deve ter {number_of_parts} partes
        Título: {title}

        {content}
    """.format(
        title=reddit_post.title,
        content=reddit_post.content,
        number_of_parts=number_of_parts,
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
    raw_data = response.choices[0].message.content
    response = json.loads(raw_data)

    return MultiplePartHistory(
        **response,
        reddit_community=reddit_post.community,
        reddit_post_author=reddit_post.author,
        reddit_community_url_photo=reddit_post.community_url_photo,
    )


def enhance_captions(
    srt_content: str,
    history: History,
) -> str:
    schema = {
        "name": "captions_schema",
        "schema": {
            "type": "object",
            "properties": {
                "content": {
                    "description": "Conteúdo do arquivo srt de legenda",
                    "type": "string",
                },
            },
        },
    }

    system_message = """
        Você é um revisor e editor de legenda, eu vou te passar uma legenda e você
        deve remover dela o título da história e corrigi-la com base na história escrita
        originalmente, corrigindo qualquer erro ou palavras erradas. Após remover o título
        as demais legendas devem permanecer com o mesmo tempo.
        
        O resultado deve ser escrito em em formato SRT. 
    """
    user_message = """
        Aqui está a história original:

        Título: {title}

        {content}


        Aqui está o arquivo srt de legenda para ser editado.
        {srt_content}
    """.format(
        title=history.title,
        content=history.content,
        srt_content=srt_content,
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
    raw_data = response.choices[0].message.content
    response = json.loads(raw_data)

    return response["content"]
