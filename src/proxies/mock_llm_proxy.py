from typing import List

from .interfaces import ILLMProxy
from ..entities.language import Language
from ..services.tiktok_caption import normalize_hashtags

MOCK_SINGLE_STORY = {
    "title": "Minha ex reapareceu depois de 10 anos e me chamou de mentiroso quando viu que eu já tinha seguido em frente",
    "narrator_gender": "male",
    "script": (
        "Minha ex reapareceu depois de 10 anos e me chamou de mentiroso quando viu que "
        "eu já tinha seguido em frente. Não sei bem como começar essa história, "
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
        "um dia recebi uma ligação de um número desconhecido. Atendi o telefone e era a minha "
        "ex. Ela queria que a gente se encontrasse. Eu concordei, mas com uma condição: eu ia "
        "levar minha esposa. Ela ficou furiosa, me chamou de mentiroso e manipulador. Mas "
        "insistiu em me encontrar sem a minha esposa. Combinei de encontrar ela num shopping. "
        "Lá, ela me contou que tinha um filho de 4 anos e que tinha se separado do parceiro, "
        "que era marinheiro e cortou contato com ela, só mandava dinheiro pela mãe dele. Disse "
        "que tinha voltado pra nossa cidade por minha causa. E quando descobriu que eu era "
        "casado e tinha uma filha, ficou em choque, porque eu tinha prometido esperar por ela. "
        "Eu fiquei parado olhando pra ela sem acreditar na cara de pau. Enquanto ela gaguejava "
        "tentando segurar o choro, eu a interrompi e disse, com os dentes cerrados, que ela "
        "não podia simplesmente sumir da minha vida por 10 anos, ter filho com outro, outros "
        "relacionamentos, e agora voltar quando tudo deu errado esperando que eu cumprisse "
        "uma promessa de 10 anos atrás que ela mesma quebrou primeiro. Disse pra ela nunca "
        "mais entrar em contato comigo. Levantei, saí de lá com os olhos vermelhos e fui "
        "encontrar minha esposa e minha filha em outro restaurante. Minha esposa perguntou "
        "como foi e eu disse que contava em casa porque eu tava muito nervoso. Cheguei em "
        "casa, contei tudo, e ela me abraçou. Sou muito grato por tudo que tenho agora. "
        "Minha ex pode ter sido meu primeiro amor, mas minha esposa é o maior de todos. "
        "E vocês, acham que eu fiz a coisa certa? Curta, me siga e deixe nos comentários."
    ),
}


MOCK_EVALUATION = {
    "resumo": (
        "Um homem estava tendo um péssimo dia quando uma garota estacionou ao lado dele "
        "e bateu a porta do carro dela na dele. Em vez de pedir desculpas, ela deu um "
        "sorrisinho de deboche. Tomado pela fúria, ele chutou sua própria porta contra "
        "o carro novinho dela, causando um estrondo enorme. A garota congelou em choque "
        "enquanto ele acendia um cigarro tranquilamente."
    ),
    "notas": {
        "retencao": {
            "nota": 88,
            "justificativa": "A história prende desde o início com a situação de estacionamento e escala rapidamente pro conflito.",
        },
        "qualidade": {
            "nota": 92,
            "justificativa": "Narrativa perfeita de karma instantâneo com setup, conflito e resolução satisfatória.",
        },
        "viralizacao": {
            "nota": 85,
            "justificativa": "Karma instantâneo contra pessoa arrogante é um tema universalmente compartilhável.",
        },
        "adequacao_tiktok": {
            "nota": 80,
            "justificativa": "Tamanho ideal pra TikTok, conteúdo family-friendly e funciona bem como narração.",
        },
        "gancho": {
            "nota": 90,
            "justificativa": "O contraste entre o carro velho e o carro novo cria curiosidade imediata.",
        },
    },
    "nota_geral": 87.0,
    "veredito": "Excelente",
}


class MockLLMProxy(ILLMProxy):
    """Returns a fixed story, evaluation and hashtags without calling any model."""

    async def generate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        return dict(MOCK_SINGLE_STORY)

    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        return dict(MOCK_EVALUATION)

    async def generate_hashtags(
        self, title: str, summary: str, target_language: Language
    ) -> list[str]:
        return normalize_hashtags(["viral"])

    async def enhance_transcription(
        self, base_text: str, raw_transcription: List[dict]
    ) -> List[dict]:
        return raw_transcription
