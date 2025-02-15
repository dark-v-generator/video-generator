import json
from typing import List
from entities.captions import CaptionSegment, Captions
from entities.history import History
from openai import OpenAI

HISTORY_SCHEMA = {
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
        "gender": {
            "description": "Gênero de quem conta a história, pode ser 'male' quando homem e 'female' quando mulher",
            "type": "string",
        },
    },
}

ENHANCE_HISTORY_PROMPT = """
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
"""

DIVIDE_HISTORY_PROMPT = """
    Eu vou te passar uma história grande e você deve dividila em partes, sem alterar o conteúdo, mantendo o conteúdo original.
    As partes serão publicadas nas redes sociais, portanto divida em um momento chave da história para que a atenção do ouvinte
    seja atraída, e insira ao final trechos para interação como "Curta e me siga para parte 2".
"""

ENHANCE_CAPTIONS_PROMPT = """
    Vou te passar uma lista de legendas geradas automaticamente 
    e o texto original. Ajuste a legenda, corrigindo erros nas palavras, e apenas nas palavras.
    Não altere os tempos das legendas, nem o número de palavras em cada legenda
    não altere nada, apenas palavras incorretas, de acordo com o texto passado.
"""


CAPTION_SEGMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {
            "description": "Início da legenda",
            "type": "number",
        },
        "end": {
            "description": "Fim da legenda",
            "type": "string",
        },
        "text": {
            "description": "Conteúdo da legenda",
            "type": "string",
        },
    },
}


def enhance_history(title: str, content: str) -> History:
    user_prompt = """
        Título: {title}

        {content}
    """.format(
        title=title,
        content=content,
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ENHANCE_HISTORY_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "history_schema",
                "schema": HISTORY_SCHEMA,
            },
        },
    )
    raw_data = response.choices[0].message.content
    response = json.loads(raw_data)
    return History(
        **response,
    )


def divide_history(history: History, number_of_parts: int) -> List[History]:
    user_message = """
        Divida essa história em {number_of_parts} partes:
        {history_dump}
    """.format(
        history_dump=history.model_dump(),
        number_of_parts=number_of_parts,
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": DIVIDE_HISTORY_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "multiple_part_history_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "histories": {
                            "type": "array",
                            "items": HISTORY_SCHEMA,
                        },
                    },
                },
            },
        },
    )
    raw_data = response.choices[0].message.content
    response = json.loads(raw_data).get('histories')
    return [History(**res) for res in response]


def enhance_captions(captions: Captions, text: str) -> Captions:
    user_prompt = """
        Aqui está o texto original:
        {text}

        E aqui estão as legendas geradas:
        {captions}
    """.format(
        text=text,
        captions=captions.model_dump().get("segments"),
    )
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ENHANCE_CAPTIONS_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "captions_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "segments": {
                            "type": "array",
                            "items": CAPTION_SEGMENT_SCHEMA,
                        },
                    },
                },
            },
        },
    )
    raw_data = response.choices[0].message.content
    response: List[dict] = json.loads(raw_data).get("segments")
    segments = [
        CaptionSegment(
            start=float(seg.get("start")),
            end=float(seg.get("end")),
            text=seg.get("text"),
        )
        for seg in response
    ]
    return Captions(segments=segments)
