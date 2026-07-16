"""Fine-tune a Chinese MacBERT intent classifier for puzzle-game agent routing."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


@dataclass
class IntentExample:
    text: str
    label: int


class IntentDataset(Dataset):
    def __init__(self, examples: list[IntentExample], tokenizer, max_length: int) -> None:
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        item = self.examples[idx]
        encoded = self.tokenizer(
            item.text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": encoded["input_ids"].squeeze(0),
            "attention_mask": encoded["attention_mask"].squeeze(0),
            "labels": torch.tensor(item.label, dtype=torch.long),
        }


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_label_maps(*splits: list[dict]) -> tuple[dict[str, int], dict[int, str]]:
    labels = sorted({row["intent"] for split in splits for row in split})
    label2id = {label: idx for idx, label in enumerate(labels)}
    id2label = {idx: label for label, idx in label2id.items()}
    return label2id, id2label


def to_examples(rows: list[dict], label2id: dict[str, int]) -> list[IntentExample]:
    return [IntentExample(text=row["text"], label=label2id[row["intent"]]) for row in rows]


def evaluate(model, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    total = 0
    correct = 0
    total_loss = 0.0

    with torch.no_grad():
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            total_loss += float(outputs.loss.item()) * batch["labels"].size(0)
            preds = outputs.logits.argmax(dim=-1)
            correct += int((preds == batch["labels"]).sum().item())
            total += int(batch["labels"].size(0))

    return {
        "loss": total_loss / max(total, 1),
        "accuracy": correct / max(total, 1),
    }


def save_metadata(output_dir: Path, label2id: dict[str, int], id2label: dict[int, str], labels_path: Path) -> None:
    metadata = {
        "label2id": label2id,
        "id2label": {str(k): v for k, v in id2label.items()},
    }
    if labels_path.exists():
        metadata["label_meta"] = json.loads(labels_path.read_text(encoding="utf-8"))
    (output_dir / "intent_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/game_intent")
    parser.add_argument("--model-path", default="models/chinese-macbert-base")
    parser.add_argument("--output-dir", default="models/game_intent_classifier")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    data_dir = Path(args.data_dir)
    model_path = Path(args.model_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_rows = read_jsonl(data_dir / "train.jsonl")
    valid_rows = read_jsonl(data_dir / "valid.jsonl")
    test_rows = read_jsonl(data_dir / "test.jsonl")
    label2id, id2label = build_label_maps(train_rows, valid_rows, test_rows)

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path),
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
        local_files_only=True,
    )

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model.to(device)

    train_dataset = IntentDataset(to_examples(train_rows, label2id), tokenizer, args.max_length)
    valid_dataset = IntentDataset(to_examples(valid_rows, label2id), tokenizer, args.max_length)
    test_dataset = IntentDataset(to_examples(test_rows, label2id), tokenizer, args.max_length)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    valid_loader = DataLoader(valid_dataset, batch_size=args.batch_size)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    use_amp = device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    best_valid_acc = -1.0
    history: list[dict] = []

    print(f"Device: {device}")
    print(f"Labels: {len(label2id)}")
    print(f"Train/valid/test: {len(train_dataset)}/{len(valid_dataset)}/{len(test_dataset)}")

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        seen = 0

        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)

            with torch.cuda.amp.autocast(enabled=use_amp):
                outputs = model(**batch)
                loss = outputs.loss

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            train_loss += float(loss.item()) * batch["labels"].size(0)
            seen += int(batch["labels"].size(0))

        valid_metrics = evaluate(model, valid_loader, device)
        epoch_metrics = {
            "epoch": epoch,
            "train_loss": train_loss / max(seen, 1),
            "valid_loss": valid_metrics["loss"],
            "valid_accuracy": valid_metrics["accuracy"],
        }
        history.append(epoch_metrics)
        print(
            f"epoch={epoch} train_loss={epoch_metrics['train_loss']:.4f} "
            f"valid_loss={epoch_metrics['valid_loss']:.4f} "
            f"valid_acc={epoch_metrics['valid_accuracy']:.4f}"
        )

        if valid_metrics["accuracy"] > best_valid_acc:
            best_valid_acc = valid_metrics["accuracy"]
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            save_metadata(output_dir, label2id, id2label, data_dir / "labels.json")

    best_model = AutoModelForSequenceClassification.from_pretrained(str(output_dir), local_files_only=True)
    best_model.to(device)
    test_metrics = evaluate(best_model, test_loader, device)
    print(f"test_loss={test_metrics['loss']:.4f} test_acc={test_metrics['accuracy']:.4f}")

    (output_dir / "training_metrics.json").write_text(
        json.dumps({"history": history, "test": test_metrics}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
