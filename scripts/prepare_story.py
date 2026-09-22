"""Prepare Reddit stories locally, without calling any paid model.

The creative half of the daily pipeline runs here: discover candidates with
the deterministic ranking, render the exact editorial prompt the server would
send, and validate the resulting package before it is queued. Every subcommand
is offline as far as LLMs are concerned — the only network call is to Reddit.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from src.core.container import container
from src.entities.language import Language
from src.entities.prepared_story import PreparedStoryPackage
from src.entities.story_candidate import StoryCandidate
from src.proxies.prompts.render import render_story_prompt
from src.services.prepared_story_validation import validate_package
from src.services.story_finder_service import score_candidates

DEFAULT_OUT_DIR = "output/prepared"
CANDIDATES_FILENAME = "candidates.json"

EXIT_OK = 0
EXIT_INVALID = 1


def _parse_subreddits(values: Optional[List[str]]) -> Optional[List[str]]:
    if not values:
        return None

    subreddits = []
    for value in values:
        for item in value.split(","):
            name = item.strip().removeprefix("r/").strip("/")
            if name:
                subreddits.append(name)

    return subreddits or None


def _candidates_path(out_dir: Path) -> Path:
    return out_dir / CANDIDATES_FILENAME


def _package_paths(out_dir: Path) -> List[Path]:
    return [
        path
        for path in sorted(out_dir.glob("*.json"))
        if path.name != CANDIDATES_FILENAME
    ]


def _load_package(path: Path) -> PreparedStoryPackage:
    return PreparedStoryPackage.model_validate_json(path.read_text(encoding="utf-8"))


def _prepared_post_urls(out_dir: Path) -> set:
    """URLs already turned into a package, so `find` stops offering them again."""
    return {
        package.post.url
        for package in (_load_package(path) for path in _package_paths(out_dir))
        if package.post.url
    }


def _candidate_entry(rank: int, candidate: StoryCandidate) -> dict:
    return {
        "rank": rank,
        "deterministic_score": candidate.deterministic_score,
        "score_breakdown": candidate.score_breakdown,
        "post": candidate.post.model_dump(),
    }


def _write_candidates_file(
    out_dir: Path,
    candidates: List[StoryCandidate],
    *,
    sort: str,
    time_filter: str,
    subreddits: List[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sort": sort,
        "time_filter": time_filter,
        "subreddits": subreddits,
        "candidates": [
            _candidate_entry(rank, candidate)
            for rank, candidate in enumerate(candidates, 1)
        ],
    }
    _candidates_path(out_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_candidates_file(out_dir: Path) -> dict:
    path = _candidates_path(out_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} não existe. Rode `just story-find` antes de usar este comando."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _print_candidate(entry: dict) -> None:
    post = entry["post"]
    ratio = post.get("upvote_ratio")
    ratio_str = f"{ratio:.0%}" if ratio else "n/a"
    print(
        f"#{entry['rank']}  det={entry['deterministic_score']}  "
        f"{post['community']}  |  {post.get('score') or 0} pts ({ratio_str})  |  "
        f"{post.get('num_comments') or 0} comments  |  {len(post['content'])} chars"
    )
    print(f"    {post['title']}")
    if post.get("url"):
        print(f"    {post['url']}")


async def cmd_find(args) -> int:
    out_dir = Path(args.out)
    config = container.main_config()
    finder = container.story_finder_service()

    subreddits = _parse_subreddits(args.sub) or list(config.evaluation.subreddits)
    exclude_urls = _prepared_post_urls(out_dir) if out_dir.exists() else set()

    print(
        f"Buscando candidatas (sort={args.sort}, time={args.time}, "
        f"top_per_sub={args.top_per_sub}) em {len(subreddits)} comunidades...\n"
    )

    candidates = await finder.find_candidates(
        sort=args.sort,
        time_filter=args.time,
        posts_per_sub=args.per_sub,
        top_per_sub=args.top_per_sub,
        subreddits=subreddits,
        exclude_urls=exclude_urls,
    )

    _write_candidates_file(
        out_dir,
        candidates,
        sort=args.sort,
        time_filter=args.time,
        subreddits=subreddits,
    )

    if not candidates:
        print("Nenhuma candidata encontrada.")
        return EXIT_OK

    print(f"{len(candidates)} candidatas (ranqueadas sem nenhuma chamada de modelo):\n")
    for rank, candidate in enumerate(candidates, 1):
        _print_candidate(_candidate_entry(rank, candidate))
        print()

    print(f"Gravado em {_candidates_path(out_dir)}")
    return EXIT_OK


def _append_candidate_from_url(out_dir: Path, url: str) -> dict:
    post = container.reddit_proxy().get_reddit_post(url)
    candidate = score_candidates([post])[0]

    path = _candidates_path(out_dir)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sort": "url",
            "time_filter": "n/a",
            "subreddits": [],
            "candidates": [],
        }

    entry = _candidate_entry(len(data["candidates"]) + 1, candidate)
    data["candidates"].append(entry)

    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def _find_entry(out_dir: Path, rank: int) -> Optional[dict]:
    data = _read_candidates_file(out_dir)
    for entry in data["candidates"]:
        if entry["rank"] == rank:
            return entry
    return None


def cmd_show(args) -> int:
    out_dir = Path(args.out)

    if args.url:
        entry = _append_candidate_from_url(out_dir, args.url)
    else:
        if args.rank is None:
            print("Informe o rank do candidato ou --url.")
            return EXIT_INVALID
        entry = _find_entry(out_dir, args.rank)
        if entry is None:
            print(f"Candidato #{args.rank} não existe em {_candidates_path(out_dir)}.")
            return EXIT_INVALID

    _print_candidate(entry)
    print()
    print(entry["post"]["content"])
    return EXIT_OK


def cmd_prompt(args) -> int:
    out_dir = Path(args.out)
    config = container.main_config()

    entry = _find_entry(out_dir, args.rank)
    if entry is None:
        print(f"Candidato #{args.rank} não existe em {_candidates_path(out_dir)}.")
        return EXIT_INVALID

    language = Language(args.language) if args.language else config.language
    print(
        render_story_prompt(
            entry["post"]["title"], entry["post"]["content"], language
        )
    )
    return EXIT_OK


def cmd_validate(args) -> int:
    config = container.main_config()
    censor = container.text_censor()

    failed = False
    for raw_path in args.files:
        path = Path(raw_path)
        try:
            package = _load_package(path)
        except (ValidationError, ValueError) as exc:
            failed = True
            print(f"✗ {path.name}")
            print(f"  - pacote não pôde ser lido: {exc}")
            continue

        problems = validate_package(package, censor, config.language)
        if problems:
            failed = True
            print(f"✗ {path.name}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"✓ {path.name}")

    return EXIT_INVALID if failed else EXIT_OK


def cmd_list(args) -> int:
    out_dir = Path(args.out)
    paths = _package_paths(out_dir) if out_dir.exists() else []

    if not paths:
        print(f"Nenhum pacote em {out_dir}.")
        return EXIT_OK

    for path in paths:
        package = _load_package(path)
        preview = path.with_suffix(".preview.mp3")
        preview_note = "mp3 ok" if preview.exists() else "sem mp3"
        print(
            f"{package.post_id}  {package.created_at.isoformat(timespec='seconds')}  "
            f"[{preview_note}]  {package.story_title}"
        )

    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara histórias do Reddit localmente, sem chamar modelo pago."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_out(sub):
        sub.add_argument(
            "--out",
            default=DEFAULT_OUT_DIR,
            help=f"Diretório dos pacotes e do {CANDIDATES_FILENAME}",
        )

    find = subparsers.add_parser("find", help="Ranqueia candidatas sem LLM")
    find.add_argument("--sort", choices=["top", "new", "hot"], default="top")
    find.add_argument(
        "--time",
        choices=["hour", "day", "week", "month", "year", "all"],
        default="day",
    )
    find.add_argument("--per-sub", type=int, default=25)
    find.add_argument("--top-per-sub", type=int, default=5)
    find.add_argument("--sub", action="append")
    add_out(find)

    show = subparsers.add_parser("show", help="Mostra o texto original de um candidato")
    show.add_argument("rank", type=int, nargs="?")
    show.add_argument("--url", help="URL do Reddit; anexa o post como próximo rank")
    add_out(show)

    prompt = subparsers.add_parser(
        "prompt", help="Imprime o prompt editorial que o servidor enviaria"
    )
    prompt.add_argument("rank", type=int)
    prompt.add_argument("--language", help="Idioma alvo (default: config.language)")
    add_out(prompt)

    validate = subparsers.add_parser("validate", help="Valida pacotes prontos")
    validate.add_argument("files", nargs="+")

    listing = subparsers.add_parser("list", help="Lista os pacotes locais")
    add_out(listing)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "find":
        return asyncio.run(cmd_find(args))
    if args.command == "show":
        return cmd_show(args)
    if args.command == "prompt":
        return cmd_prompt(args)
    if args.command == "validate":
        return cmd_validate(args)
    return cmd_list(args)


if __name__ == "__main__":
    sys.exit(main())
