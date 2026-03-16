from typing import List

from .interfaces import ILLMProxy
from ..entities.image_story import ImageStory, StoryImage
from ..entities.language import Language

MOCK_STORY = {
    "title": "Minha ex reapareceu depois de 10 anos e me chamou de mentiroso quando viu que eu já tinha seguido em frente",
    "narrator_gender": "male",
    "part1": (
        "Minha ex reapareceu depois de 10 anos e me chamou de mentiroso quando viu que "
        "eu já tinha seguido em frente. Parte 1. Não sei bem como começar essa história, "
        "mas ela aconteceu há alguns meses e tem um contexto de 10 anos. Quando eu tinha "
        "14 anos, me apaixonei por uma colega de classe. Ela era meio ingênua de um jeito "
        "fofo e ria muito das minhas piadas, mesmo quando eram sobre ela. Comecei a correr "
        "atrás dela e ela ficou na dúvida no começo porque a gente era muito amigo. Mas me "
        "disse que ia me dar uma chance porque gostava de estar perto de mim. Depois de uns "
        "3 a 4 meses, ela disse sim e a gente começou a namorar. A gente se apaixonou de "
        "verdade e namorou até o fim do ensino médio. Depois da formatura, nas férias, ela "
        "me disse que precisava ir morar com a irmã na capital pra fazer faculdade. Eu disse "
        "que tudo bem, que a gente ia fazer o relacionamento à distância funcionar. Eu fiquei "
        "estudando numa universidade da nossa cidade e ela foi pra capital com a irmã. Nos "
        "primeiros meses a gente se falava bastante. No nosso quarto aniversário, ela me "
        "ligou e disse que não importava o que acontecesse, eu tinha que esperar por ela. Só "
        "que, alguns meses depois, ela simplesmente sumiu. O celular não chamava mais, as "
        "redes sociais ficaram inativas. Quando tentei falar com ela e fui ignorado, me "
        "destruiu. Ela virou alguém que eu costumava conhecer. Uma amiga dela estudava no "
        "mesmo campus que eu, e um dia a gente se encontrou e tomou um café. Ela me entregou "
        "uma carta que minha ex tinha mandado. A carta dizia que ela não conseguia manter um "
        "namoro à distância e queria seguir em frente. Doeu demais, mas eu decidi respeitar "
        "a decisão dela e seguir em frente também. Um ano depois, conheci uma garota num "
        "workshop. A gente virou amigo, e quase um ano depois começamos a namorar. Hoje a "
        "gente é formado, tem uma filha linda, está junto há 8 anos e casado há 2. Até que "
        "um dia recebi uma ligação de um número desconhecido. Curta e me siga para a parte 2."
    ),
    "part2": (
        "Minha ex reapareceu depois de 10 anos e me chamou de mentiroso quando viu que "
        "eu já tinha seguido em frente. Parte 2. Atendi o telefone e era a minha ex. Ela "
        "queria que a gente se encontrasse. Eu concordei, mas com uma condição: eu ia levar "
        "minha esposa. Ela ficou furiosa, me chamou de mentiroso e manipulador. Mas insistiu "
        "em me encontrar sem a minha esposa. Combinei de encontrar ela num shopping. Lá, ela "
        "me contou que tinha um filho de 4 anos e que tinha se separado do parceiro, que era "
        "marinheiro e cortou contato com ela, só mandava dinheiro pela mãe dele. Disse que "
        "tinha voltado pra nossa cidade por minha causa. E quando descobriu que eu era casado "
        "e tinha uma filha, ficou em choque, porque eu tinha prometido esperar por ela. Eu "
        "fiquei parado olhando pra ela sem acreditar na cara de pau. Enquanto ela gaguejava "
        "tentando segurar o choro, eu a interrompi e disse, com os dentes cerrados, que ela "
        "não podia simplesmente sumir da minha vida por 10 anos, ter filho com outro, outros "
        "relacionamentos, e agora voltar quando tudo deu errado esperando que eu cumprisse "
        "uma promessa de 10 anos atrás que ela mesma quebrou primeiro. Disse pra ela nunca "
        "mais entrar em contato comigo. Levantei, saí de lá com os olhos vermelhos e fui "
        "encontrar minha esposa e minha filha em outro restaurante. Minha esposa perguntou "
        "como foi e eu disse que contava em casa porque eu tava muito nervoso. Cheguei em "
        "casa, contei tudo, e ela me abraçou. Sou muito grato por tudo que tenho agora. "
        "Minha ex pode ter sido meu primeiro amor, mas minha esposa é o maior de todos. E "
        "você, o que achou? Curta, me siga e conta nos comentários."
    ),
}

MOCK_IMAGE_STORY = ImageStory(
    introduction_end_time=5.0,
    call_to_action_start_time=95.0,
    images=[
        StoryImage(
            start_time=0.0,
            description="Adolescente apaixonado olhando para colega de classe na escola",
            prompt="Teenage boy looking at a girl classmate in a school hallway, warm nostalgic lighting, first love atmosphere",
        ),
        StoryImage(
            start_time=12.0,
            description="Casal jovem adolescente namorando feliz no ensino médio",
            prompt="Young teenage couple holding hands at school, happy high school romance, golden hour, youthful love",
        ),
        StoryImage(
            start_time=25.0,
            description="Mulher partindo com malas para a cidade grande, homem ficando para trás",
            prompt="Woman leaving with suitcases to the big city, man staying behind waving goodbye, bittersweet separation, dramatic lighting",
        ),
        StoryImage(
            start_time=38.0,
            description="Homem sozinho tentando ligar sem sucesso, tela do celular sem resposta",
            prompt="Man alone desperately calling on phone with no answer, dark room, blue phone screen glow, loneliness and heartbreak",
        ),
        StoryImage(
            start_time=50.0,
            description="Homem lendo carta triste num café, expressão de dor",
            prompt="Man reading a sad letter in a cafe, painful expression, tears forming, warm ambient lighting, emotional scene",
        ),
        StoryImage(
            start_time=60.0,
            description="Homem conhecendo nova garota num workshop, sorrindo juntos",
            prompt="Man meeting a new woman at a workshop, both smiling, fresh start, bright hopeful lighting, natural chemistry",
        ),
        StoryImage(
            start_time=75.0,
            description="Família feliz, casal com filha pequena em casa",
            prompt="Happy married couple with cute toddler daughter at home, warm cozy family portrait, loving atmosphere",
        ),
        StoryImage(
            start_time=85.0,
            description="Homem atendendo ligação misteriosa com expressão surpresa",
            prompt="Man answering mysterious phone call with surprised expression, dramatic lighting, suspenseful mood, unknown caller",
        ),
    ],
)


class MockLLMProxy(ILLMProxy):
    """Returns a fixed example story from two_part_story.yaml examples."""

    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        return dict(MOCK_STORY)

    async def enhance_transcription(
        self, base_text: str, raw_transcription: List[dict]
    ) -> List[dict]:
        return raw_transcription

    async def generate_image_story(
        self, story_text: str, transcription: List[dict]
    ) -> ImageStory:
        return MOCK_IMAGE_STORY.model_copy(deep=True)
