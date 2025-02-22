import json
from typing import List
from entities.captions import CaptionSegment, Captions
from entities.history import History
from openai import OpenAI

from entities.language import Language
from services.language_service import t

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

ENHANCE_CAPTIONS_PROMPT_KEY='enhance_captions_prompt'
ENHANCE_HISTORY_PROMPT_KEY='enhance_history_prompt'
DIVIDE_HISTORY_PROMPT_KEY='divide_history_prompt'



def enhance_history(title: str, content: str, language: Language = Language.PORTUGUESE) -> History:
    user_prompt = """
        Título: {title}

        {content}
    """.format(
        title=title,
        content=content,
    )
    system_prompt = t(language, ENHANCE_HISTORY_PROMPT_KEY)

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
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


def divide_history(history: History, number_of_parts: int, language: Language = Language.PORTUGUESE) -> List[History]:
    user_message = """
        Divida essa história em {number_of_parts} partes:
        {history_dump}
    """.format(
        history_dump=history.model_dump(),
        number_of_parts=number_of_parts,
    )
    system_prompt = t(language, DIVIDE_HISTORY_PROMPT_KEY)
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
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


def enhance_captions(captions: Captions, history: History, language: Language = Language.PORTUGUESE) -> Captions:
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
    system_prompt = t(language, ENHANCE_CAPTIONS_PROMPT_KEY)
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
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
