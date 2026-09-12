"""Translate validated AI observations into deterministic grading events."""
from __future__ import annotations

import json
from pathlib import Path

from backend.ai.football_reasoner import (
    EvidenceIntegrityError,
    FootballReasoningResult,
    evidence_for_timestamp,
)
from backend.football.observations import FootballObservation
from .models import GradingEvent, ObservationValue
from .rules_loader import load_position_rules


SCORING_RULES_PATH = Path(__file__).with_name("rules") / "scoring_events.json"


def load_scoring_events() -> dict[str, float]:
    payload = json.loads(SCORING_RULES_PATH.read_text(encoding="utf-8"))
    return {name: float(value) for name, value in payload["events"].items()}


def reasoning_to_events(source: FootballObservation, reasoning: FootballReasoningResult) -> list[GradingEvent]:
    allowed_traits = load_position_rules(source.position).traits
    values = load_scoring_events()
    events = []
    for index, item in enumerate(reasoning.observations, 1):
        if item.trait not in allowed_traits:
            raise ValueError(f"Trait {item.trait!r} is not an official {source.position} trait")
        try:
            observation = ObservationValue(item.value)
        except ValueError as exc:
            raise ValueError(f"Unsupported grading event: {item.value}") from exc
        # UNKNOWN is absence of a gradeable conclusion, not a zero-value event.
        if observation == ObservationValue.UNKNOWN:
            continue
        evidence = evidence_for_timestamp(source, item.evidence_timestamp)
        if item.evidence_timestamp is None or evidence is None:
            if item.evidence_timestamp is None:
                raise EvidenceIntegrityError(
                    f"Non-unknown trait {item.trait!r} requires an evidence timestamp"
                )
            raise EvidenceIntegrityError(
                f"Evidence timestamp {item.evidence_timestamp} for trait {item.trait!r} "
                "is outside the source observation's evidence ranges"
            )
        value = values[observation.value]
        events.append(GradingEvent(
            rule_id=f"{source.position.upper()}_{item.trait.upper()}_{index:03d}",
            trait=item.trait, value=value, confidence=item.confidence,
            timestamp=item.evidence_timestamp, play_id=source.play_id,
            reason=item.reason, observation=observation, evidence=evidence,
        ))
    return events
