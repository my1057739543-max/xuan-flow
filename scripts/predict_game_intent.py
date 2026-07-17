"""Predict game intent for one user query."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--model-dir", default="models/game_intent_classifier")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = Path(args.model_dir)
    metadata_path = model_dir / "intent_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    label_meta = metadata.get("label_meta", {})

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model.to(device)
    model.eval()

    encoded = tokenizer(
        args.text,
        truncation=True,
        max_length=args.max_length,
        padding="max_length",
        return_tensors="pt",
    )
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        probs = torch.softmax(model(**encoded).logits, dim=-1).squeeze(0)

    top_k = min(args.top_k, probs.numel())
    scores, indices = torch.topk(probs, k=top_k)
    predictions = []
    for score, idx in zip(scores.tolist(), indices.tolist()):
        intent = model.config.id2label[int(idx)]
        meta = label_meta.get(intent, {})
        predictions.append(
            {
                "intent": intent,
                "confidence": round(float(score), 4),
                "route_to": meta.get("route_to"),
                "spoiler_level": meta.get("spoiler_level"),
                "needs_game_context": meta.get("needs_game_context"),
            }
        )

    print(json.dumps({"text": args.text, "predictions": predictions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
