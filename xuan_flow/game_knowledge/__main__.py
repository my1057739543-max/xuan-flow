"""CLI for the local game knowledge catalog."""

from __future__ import annotations

import argparse
import json

from xuan_flow.game_knowledge.search import (
    get_game_by_id,
    list_supported_games,
    search_game_catalog,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect local game knowledge catalog.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    get_parser = sub.add_parser("get")
    get_parser.add_argument("game_id")
    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "list":
        payload = list_supported_games()
    elif args.command == "get":
        payload = get_game_by_id(args.game_id)
    else:
        payload = search_game_catalog(args.query, limit=args.limit)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
