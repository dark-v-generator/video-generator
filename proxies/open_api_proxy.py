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
Corrija a pontuação (vírgulas, pontos finais, exclamações, interrogações) e substitua abreviações por palavras completas ex:
 - "Eu H20" -> "Eu sou um homem de 20 anos"
 - "Eu M24" -> "Eu sou um homem de 24 anos"
 - "vc" -> "você"
 - "pq" -> "porque"
 - "tbm" -> 'também'

Requisitos:

Não altere o conteúdo, o tom ou a estrutura da história.

Mantenha a informalidade ou formalidade original do texto.

Adicione ao final, em um novo parágrafo, com uma frase de interação que se encaixe com o texto, exemplo:
"O que você faria nessa situação? Curta, me siga e deixe nos comentários!"

Proibições:

Não reescreva frases, nem adicione emojis, hashtags ou opiniões pessoais.

Não modifique o contexto, gírias regionais ou expressões características do autor.

Evite paráfrases ou mudanças no estilo narrativo.
"""

DIVIDE_HISTORY_PROMPT = """
    Eu vou te passar uma história grande e você deve dividila em partes, sem alterar o conteúdo, mantendo o conteúdo original.
    As partes serão publicadas nas redes sociais, portanto divida em um momento chave da história para que a atenção do ouvinte
    seja atraída, e insira ao final trechos para interação como "Curta e me siga para parte 2".
"""

ENHANCE_CAPTIONS_PROMPT = """
Instrucoes:
Eu vou te passar uma lista de legenda de uma narracao, contendo uma palavra por segmento. Faca o seguinte:

1. Remova os seguimentos que nao estiverem no texto original, sem alterar os tempos da legenda (sao trechos narrados, mas não legendados).

2. Corrija os textos das legendas para corresponderem exatamente ao conteúdo original, mantendo:
    - O sentido original e tom do texto.
    - Os tempos (start e end) inalterados, exceto se precisar mesclar segmentos quebrados (ex: duas legendas separadas para uma única palavra).

Proibições:
- Não adicione, ou modifique legendas que já estejam corretas.
- Não altere a ordem das legendas ou o contexto do conteúdo.
- Nao ajuste ou altere os tempos das legendas, a nao ser em casos de mesclagem de legendas.
- Nao mescle legendas sem necessidade, o formato deve continuar uma palavra por segmento.
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
    response = json.loads(raw_data).get("histories")
    return [History(**res) for res in response]


def enhance_captions(captions: Captions, history: History) -> Captions:
    user_prompt = """
        Conteudo: 
        {content}

        Legendas geradas:
        {captions}
    """.format(
        title=history.title,
        content=history.content,
        captions=captions.model_dump().get("segments"),
    )
    print(ENHANCE_CAPTIONS_PROMPT)
    print(user_prompt)
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
