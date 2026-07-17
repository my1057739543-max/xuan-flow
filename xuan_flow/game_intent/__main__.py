"""Command line entry for game intent routing."""

from __future__ import annotations

import argparse
import json

from xuan_flow.game_intent.router import route_game_intent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route a single-player puzzle-game query.")
    parser.add_argument("text", help="User query to classify and route.")
    parser.add_argument("--model-dir", default="models/game_intent_classifier")
    parser.add_argument("--device", default=None, help="Optional torch device, e.g. cpu or cuda.")
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    route = route_game_intent(
        args.text,
        model_dir=args.model_dir,
        device=args.device,
        top_k=args.top_k,
    )
    print(json.dumps(route.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
