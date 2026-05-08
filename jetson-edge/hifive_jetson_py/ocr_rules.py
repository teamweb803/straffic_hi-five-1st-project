from __future__ import annotations

import re
from collections import defaultdict

from .models import OcrCandidate, PlateDecision, clamp01


PLATE_PATTERN = re.compile(r"^\d{2,3}[\uac00-\ud7a3]\d{4}$")


def valid_korean_plate(text: str) -> bool:
    return bool(PLATE_PATTERN.fullmatch(text or ""))


class OcrCandidateBuffer:
    def __init__(self, min_candidates: int = 2, confidence_threshold: float = 0.70) -> None:
        self.min_candidates = min_candidates
        self.confidence_threshold = confidence_threshold
        self._items: dict[str, list[OcrCandidate]] = defaultdict(list)

    def add(self, track_id: str, text: str, confidence: float) -> None:
        valid = valid_korean_plate(text)
        self._items[str(track_id)].append(
            OcrCandidate(
                text=text,
                confidence=clamp01(confidence),
                valid_pattern=valid,
                review_reason=None if valid else "pattern_mismatch",
            )
        )

    def decide(self, track_id: str) -> PlateDecision:
        items = self._items.get(str(track_id), [])
        if not items:
            return PlateDecision("", 0.0, False, True, "no_ocr_candidates", 0, 0.0)

        weights: dict[str, float] = defaultdict(float)
        for item in items:
            weights[item.text] += max(0.0, item.confidence)
        text = max(weights, key=weights.get)
        same = [item for item in items if item.text == text]
        confidence = clamp01(sum(item.confidence for item in same) / max(1, len(same)))
        agreement = len(same) / len(items)
        valid = valid_korean_plate(text)
        reason = self._review_reason(text, confidence, valid, len(items), agreement)
        return PlateDecision(
            text=text,
            confidence=confidence,
            valid_pattern=valid,
            needs_review=reason is not None,
            review_reason=reason or "",
            candidate_count=len(items),
            agreement_ratio=agreement,
            raw_candidates=[item.__dict__ for item in items],
        )

    def clear(self, track_id: str) -> None:
        self._items.pop(str(track_id), None)

    def _review_reason(
        self,
        text: str,
        confidence: float,
        valid: bool,
        count: int,
        agreement: float,
    ) -> str | None:
        if count < self.min_candidates:
            return "not_enough_ocr_candidates"
        if not text:
            return "empty_ocr_text"
        if not valid:
            return "pattern_mismatch"
        if confidence < self.confidence_threshold:
            return "low_ocr_confidence"
        if agreement < 0.50:
            return "candidate_disagreement"
        return None

