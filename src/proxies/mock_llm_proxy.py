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

STYLE_SUFFIX = (
    "digital illustration, soft watercolor anime style, cinematic lighting, "
    "warm color palette with teal and amber tones, detailed background"
)

CHAR_LUCAS = (
    "a 24-year-old Brazilian man with short brown wavy hair, light stubble, "
    "brown eyes, wearing a navy blue hoodie and jeans"
)
CHAR_LUCAS_TEEN = (
    "a 14-year-old Brazilian boy with short brown wavy hair, brown eyes, "
    "wearing a white school uniform shirt and dark pants"
)
CHAR_ANA = (
    "a 14-year-old Brazilian girl with long black hair in a ponytail, "
    "bright dark eyes, wearing a white school uniform shirt and plaid skirt"
)
CHAR_WIFE = (
    "a 23-year-old Brazilian woman with shoulder-length curly dark hair, "
    "warm smile, wearing a yellow sundress"
)

MOCK_IMAGE_SCENES = [
    StoryImage(
        start_time=0.0,
        description="Corredor de escola com luz dourada, clima nostálgico",
        prompt=f"Empty school hallway bathed in golden afternoon light, lockers on both sides, nostalgic atmosphere, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Adolescente apaixonado olhando para colega de classe",
        prompt=f"{CHAR_LUCAS_TEEN} looking shyly at {CHAR_ANA} across a school classroom, desks and chalkboard, warm nostalgic light, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Garota rindo das piadas do garoto na escola",
        prompt=f"{CHAR_ANA} laughing while {CHAR_LUCAS_TEEN} tells a joke, school courtyard, cherry blossom trees, joyful mood, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Casal adolescente de mãos dadas comemorando namoro",
        prompt=f"{CHAR_LUCAS_TEEN} and {CHAR_ANA} holding hands walking through school hallway, happy high school romance, golden hour, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Formatura do ensino médio, casal feliz",
        prompt=f"{CHAR_LUCAS_TEEN} and {CHAR_ANA} in graduation caps and gowns, hugging and smiling, school auditorium, confetti falling, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Mulher partindo com malas para a capital",
        prompt=f"{CHAR_ANA} walking away pulling a suitcase toward a bus, {CHAR_LUCAS} standing behind waving goodbye, rainy bus station, bittersweet mood, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Homem estudando sozinho na universidade local",
        prompt=f"{CHAR_LUCAS} studying alone at a university library desk, books piled up, empty seat next to him, melancholic atmosphere, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Casal conversando por videochamada à distância",
        prompt=f"{CHAR_LUCAS} on a video call on his laptop, {CHAR_ANA}'s face on the screen smiling, small apartment room, late night, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="No aniversário de namoro, ela pede pra ele esperar",
        prompt=f"Close-up of a phone screen showing a long call timer, {CHAR_LUCAS} pressing the phone to his ear with a serious expression, bedroom at night, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Meses depois, celular não chama mais",
        prompt=f"{CHAR_LUCAS} sitting alone in a dark room staring at phone screen showing 'no answer', blue phone glow on his face, loneliness, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Redes sociais inativas, homem devastado",
        prompt=f"{CHAR_LUCAS} scrolling through empty social media profiles on phone, slumped on a couch, dim room, devastated expression, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Ser ignorado o destruiu por dentro",
        prompt=f"{CHAR_LUCAS} sitting on a park bench alone in the rain, head in his hands, puddles reflecting streetlights, raw grief, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Ela virou alguém que ele costumava conhecer",
        prompt=f"{CHAR_LUCAS} standing alone at a window looking out at rain, faded photo of {CHAR_ANA} on the desk behind him, melancholic blue tones, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Amiga entrega carta da ex num café",
        prompt=f"A young woman handing a sealed envelope to {CHAR_LUCAS} across a cafe table, two coffee cups, awkward atmosphere, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Homem lendo carta de despedida, expressão de dor",
        prompt=f"{CHAR_LUCAS} reading a handwritten letter in a cozy cafe, painful expression, a coffee cup beside him, warm ambient lighting, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Homem decidindo seguir em frente, andando ao pôr do sol",
        prompt=f"{CHAR_LUCAS} walking alone down a long road at sunset, determined expression, leaving the past behind, golden and orange sky, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Homem conhecendo nova garota num workshop",
        prompt=f"{CHAR_LUCAS} meeting {CHAR_WIFE} at a workshop table, both smiling at each other, bright classroom, hopeful fresh-start mood, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Casal começando a namorar, passeando de mãos dadas",
        prompt=f"{CHAR_LUCAS} and {CHAR_WIFE} walking together in a park at golden hour, holding hands, autumn leaves, romantic and peaceful, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Casamento feliz, casal na cerimônia",
        prompt=f"{CHAR_LUCAS} in a dark suit and {CHAR_WIFE} in a white wedding dress exchanging vows, small chapel, flower arrangements, tears of joy, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Homem atendendo ligação misteriosa com expressão surpresa",
        prompt=f"{CHAR_LUCAS} answering a phone call with wide surprised eyes, standing in kitchen, dramatic side lighting, suspenseful mood, {STYLE_SUFFIX}",
    ),
    StoryImage(
        start_time=0.0,
        description="Família feliz, casal com filha pequena em casa",
        prompt=f"{CHAR_LUCAS} and {CHAR_WIFE} sitting on a couch with a cute toddler daughter, cozy living room, family portrait feel, warm lamplight, {STYLE_SUFFIX}",
    ),
]


def _find_sentence_boundaries(transcription: List[dict]) -> List[float]:
    """Find `end` timestamps of words that end sentences (period, !, ?)."""
    boundaries = []
    for w in transcription:
        text = w.get("word", "").strip()
        if text and text[-1] in ".!?":
            boundaries.append(w["end"])
    return boundaries


MAX_IMAGE_DURATION = 8.0


MIN_IMAGE_DURATION = 4.0


def _build_mock_image_story(transcription: List[dict]) -> ImageStory:
    """Build an ImageStory with start_times aligned to sentence boundaries.

    Guarantees: first image at 0.0 (blurred intro background), second image
    starts a few sentences AFTER intro_end so the first image is visible
    unblurred, each image lasts 4-8 seconds.
    """
    boundaries = _find_sentence_boundaries(transcription)
    if not boundaries:
        total = transcription[-1]["end"] if transcription else 60.0
        step = total / (len(MOCK_IMAGE_SCENES) + 2)
        boundaries = [step * i for i in range(1, len(MOCK_IMAGE_SCENES) + 2)]

    intro_end = boundaries[0] if boundaries else 5.0

    cta_boundary = boundaries[-1] if boundaries else 90.0
    for b in reversed(boundaries):
        cta_boundary = b
        if b < boundaries[-1]:
            break

    story_boundaries = [b for b in boundaries if intro_end < b < cta_boundary]
    if not story_boundaries:
        story_boundaries = [intro_end + 5.0]

    # Greedily pick every boundary that's >= MIN_IMAGE_DURATION from the last
    picked: List[float] = []
    last_time = 0.0
    for b in story_boundaries:
        if b - last_time >= MIN_IMAGE_DURATION:
            picked.append(b)
            last_time = b

    # Also ensure the last image doesn't stretch too long to CTA
    if picked and cta_boundary - picked[-1] > MAX_IMAGE_DURATION:
        tail_candidates = [b for b in story_boundaries if b > picked[-1]]
        while tail_candidates and cta_boundary - picked[-1] > MAX_IMAGE_DURATION:
            picked.append(tail_candidates.pop(0))

    # Cap to available scene count minus 1 (first scene is always at 0.0).
    # When trimming, remove the pick that causes the smallest duration increase.
    max_picks = len(MOCK_IMAGE_SCENES) - 1
    while len(picked) > max_picks:
        best_idx = -1
        best_cost = float("inf")
        for i in range(len(picked)):
            prev_t = 0.0 if i == 0 else picked[i - 1]
            next_t = cta_boundary if i == len(picked) - 1 else picked[i + 1]
            merged_gap = next_t - prev_t
            if merged_gap < best_cost:
                best_cost = merged_gap
                best_idx = i
        picked.pop(best_idx)

    images = []
    for i, scene in enumerate(MOCK_IMAGE_SCENES[: len(picked) + 1]):
        t = 0.0 if i == 0 else picked[i - 1]
        images.append(scene.model_copy(update={"start_time": t}))

    return ImageStory(
        introduction_end_time=intro_end,
        call_to_action_start_time=cta_boundary,
        images=images,
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
        self,
        story_text: str,
        transcription: List[dict],
        style_context: str | None = None,
    ) -> ImageStory:
        return _build_mock_image_story(transcription)
