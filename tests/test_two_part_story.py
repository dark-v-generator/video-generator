import argparse
import asyncio
import os
from src.proxies.factories import LLMProxyFactory, RedditProxyFactory
from src.entities.configs.proxies.reddit import BS4RedditConfig
from src.entities.configs.proxies.llm import DSPyLLMConfig, PromptLLMConfig, LLMProviderConfig
from src.entities.language import Language


async def main():
    parser = argparse.ArgumentParser(description="Test 2-part story generation")
    parser.add_argument(
        "--type",
        type=str,
        choices=["dspy", "prompt"],
        default="prompt",
        help="Type of LLM Proxy to use",
    )
    args = parser.parse_args()

    reddit_url = "https://www.reddit.com/r/pettyrevenge/comments/1hwrsky/i_discovered_ex_bf_was_cheating_so_i_exposed_him/"

    # 1. Fetch Reddit Post
    print(f"Fetching Reddit post: {reddit_url}")
    reddit_proxy = RedditProxyFactory.create(BS4RedditConfig())
    post = reddit_proxy.get_reddit_post(reddit_url)
    print(f"Original Title: {post.title}")

    # 2. Configure LLM Proxy
    print(f"Using proxy type: {args.type.upper()} with local ollama (gemma3:12b)")
    provider_config = LLMProviderConfig(
        provider="ollama", model="gemma3:12b", temperature=0.7, max_tokens=2000
    )

    if args.type == "dspy":
        config = DSPyLLMConfig(provider_config=provider_config)
    else:
        config = PromptLLMConfig(provider_config=provider_config)

    llm_proxy = LLMProxyFactory.create(config)

    # 3. Generate the 2-part story
    print("Generating 2-part story...\n")
    story_parts = await llm_proxy.generate_two_part_story(
        title=post.title, content=post.content, target_language=Language.PORTUGUESE
    )

    # 4. Save to markdown file in tests/data
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)

    file_path = os.path.join(output_dir, f"generated_story_{args.type}.md")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# TITLE: {story_parts['title']}\n\n")
        f.write("## PART 1\n")
        f.write(f"{story_parts['part1']}\n\n")
        f.write("## PART 2\n")
        f.write(f"{story_parts['part2']}\n")

    print(f"Successfully saved generated story to: {file_path}")


if __name__ == "__main__":
    asyncio.run(main())
