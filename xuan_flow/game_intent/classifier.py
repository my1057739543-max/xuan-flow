"""Local MacBERT intent classifier for single-player puzzle-game routing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_MODEL_DIR = Path("models/game_intent_classifier")


@dataclass(frozen=True)
class IntentPrediction:
    """One ranked intent prediction."""

    intent: str
    confidence: float
    route_to: str | None = None
    spoiler_level: str | None = None
    needs_game_context: bool | None = None
    domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "route_to": self.route_to,
            "spoiler_level": self.spoiler_level,
            "needs_game_context": self.needs_game_context,
            "domain": self.domain,
        }


class GameIntentClassifier:
    """Loads the fine-tuned classifier and returns top-k intent predictions.

    The heavy ML dependencies are imported lazily so the rest of Xuan-Flow can
    start without torch/transformers when the game-intent router is unused.
    """

    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        *,
        device: str | None = None,
        max_length: int = 64,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.max_length = max_length
        self._torch = None
        self._tokenizer = None
        self._model = None
        self._device = None
        self._device_override = device
        self._metadata = self._load_metadata()

    @property
    def label_meta(self) -> dict[str, dict[str, Any]]:
        return self._metadata.get("label_meta", {})

    def predict(self, text: str, *, top_k: int = 3) -> list[IntentPrediction]:
        """Predict ranked intents for a user query."""
        if not text or not text.strip():
            raise ValueError("text must be a non-empty string")

        self._ensure_loaded()
        torch = self._torch
        assert torch is not None
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._device is not None

        encoded = self._tokenizer(
            text.strip(),
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = self._model(**encoded).logits
            probs = torch.softmax(logits, dim=-1).squeeze(0)

        count = min(max(1, top_k), int(probs.numel()))
        scores, indices = torch.topk(probs, k=count)

        predictions: list[IntentPrediction] = []
        for score, index in zip(scores.tolist(), indices.tolist()):
            intent = self._model.config.id2label[int(index)]
            meta = self.label_meta.get(intent, {})
            predictions.append(
                IntentPrediction(
                    intent=intent,
                    confidence=float(score),
                    route_to=meta.get("route_to"),
                    spoiler_level=meta.get("spoiler_level"),
                    needs_game_context=meta.get("needs_game_context"),
                    domain=meta.get("domain"),
                )
            )
        return predictions

    def _load_metadata(self) -> dict[str, Any]:
        path = self.model_dir / "intent_metadata.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"Game intent model not found: {self.model_dir}. "
                "Train it with scripts/train_game_intent_classifier.py first."
            )

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Game intent routing requires torch and transformers. "
                "Install them in the active environment before using this module."
            ) from exc

        if self._device_override:
            device = torch.device(self._device_override)
        else:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
        )
        model.to(device)
        model.eval()

        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        self._device = device


@lru_cache(maxsize=4)
def get_game_intent_classifier(
    model_dir: str = str(DEFAULT_MODEL_DIR),
    device: str | None = None,
    max_length: int = 64,
) -> GameIntentClassifier:
    """Return a cached classifier instance."""
    return GameIntentClassifier(model_dir=model_dir, device=device, max_length=max_length)
