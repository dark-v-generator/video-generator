import argparse
import asyncio

from src.entities.language import Language
from src.core.container import container


CRITERIA_LABELS = {
    "retencao": "Potencial de Retenção",
    "qualidade": "Qualidade da História",
    "viralizacao": "Potencial de Viralização",
    "adequacao_tiktok": "Adequação pra TikTok",
    "gancho": "Força do Gancho",
}


def _grade_bar(nota: int, width: int = 20) -> str:
    filled = round(nota / 100 * width)
    return "█" * filled + "░" * (width - filled)


def print_evaluation(evaluation: dict) -> None:
    print("\n" + "=" * 60)
    print("  AVALIAÇÃO DA HISTÓRIA")
    print("=" * 60)

    print(f"\n📝 Resumo:\n{evaluation['resumo']}\n")

    print("-" * 60)
    notas = evaluation["notas"]
    for key, label in CRITERIA_LABELS.items():
        entry = notas.get(key, {})
        nota = entry.get("nota", 0)
        justificativa = entry.get("justificativa", "")
        bar = _grade_bar(nota)
        print(f"  {label}")
        print(f"    {bar} {nota}/100")
        print(f"    {justificativa}")
        print()

    print("-" * 60)
    nota_geral = evaluation["nota_geral"]
    veredito = evaluation["veredito"]
    bar = _grade_bar(int(nota_geral))
    print(f"  NOTA GERAL: {bar} {nota_geral}/100  [{veredito}]")
    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a Reddit post's potential as a TikTok narrated video"
    )
    parser.add_argument("post_url", type=str, help="Reddit post URL")
    parser.add_argument(
        "--language",
        type=str,
        choices=[lang.value for lang in Language],
        default=Language.PORTUGUESE.value,
        help="Language for the evaluation output",
    )

    args = parser.parse_args()

    container.wire(modules=[__name__])

    reddit_proxy = container.reddit_proxy()
    llm_proxy = container.evaluation_llm_proxy() or container.llm_proxy()

    print(f"Scraping post: {args.post_url}")
    post = reddit_proxy.get_reddit_post(args.post_url)
    print(f"Post: {post.title} (r/{post.community})\n")

    print("Evaluating...")
    lang_enum = Language(args.language)
    evaluation = await llm_proxy.evaluate_story(
        title=post.title,
        content=post.content,
        target_language=lang_enum,
    )

    print_evaluation(evaluation)


if __name__ == "__main__":
    asyncio.run(main())
