"""Evaluate the fine-tuned game intent classifier on a JSONL split."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="models/game_intent_classifier")
    parser.add_argument("--data-file", default="data/game_intent/test.jsonl")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir)
    rows = read_jsonl(Path(args.data_file))

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model.to(device)
    model.eval()

    correct = 0
    confusion: dict[str, Counter] = defaultdict(Counter)

    with torch.no_grad():
        for row in rows:
            encoded = tokenizer(
                row["text"],
                truncation=True,
                max_length=args.max_length,
                padding="max_length",
                return_tensors="pt",
            )
            encoded = {k: v.to(device) for k, v in encoded.items()}
            logits = model(**encoded).logits
            pred_id = int(logits.argmax(dim=-1).item())
            pred = model.config.id2label[pred_id]
            gold = row["intent"]
            correct += int(pred == gold)
            confusion[gold][pred] += 1

    print(f"accuracy={correct / max(len(rows), 1):.4f} ({correct}/{len(rows)})")
    print("confusion:")
    for gold in sorted(confusion):
        print(f"  {gold}: {dict(confusion[gold])}")


if __name__ == "__main__":
    main()
