"""Strict football reasoning that cannot produce an official TruGrade score."""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from backend.football.observations import FootballObservation
from .provider import AIProvider


SYSTEM_RULE = """You are an observation and football reasoning layer.
You do not determine the player's official TruGrade score.
Only identify evidence-supported football traits and outcomes.
Return unknown when evidence is insufficient. Never guess.
Every non-unknown observation must cite an evidence_timestamp inside one of the
structured source observation's evidence timestamp ranges and explain its evidence.
Never invent a timestamp. An unknown observation may use a null evidence_timestamp."""


class ReasonedTrait(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trait: str
    value: str
    confidence: float = Field(ge=0, le=1)
    evidence_timestamp: float | None = Field(default=None, ge=0)
    reason: str


class FootballReasoningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ReasonedTrait]
    provider_note: str | None = None


class EvidenceIntegrityError(ValueError):
    """Raised when a scoring claim is not linked to source evidence."""


def evidence_for_timestamp(observation: FootballObservation, timestamp: float | None):
    """Return the source evidence containing ``timestamp``, if one exists."""
    if timestamp is None:
        return None
    return next((record for record in observation.evidence
                 if record.timestamp_start <= timestamp <= record.timestamp_end), None)


def validate_reasoning_evidence(
    observation: FootballObservation,
    reasoning: FootballReasoningResult,
) -> None:
    """Reject non-unknown claims that cannot point back to the supplied film."""
    for item in reasoning.observations:
        if item.value == "unknown":
            continue
        if item.evidence_timestamp is None:
            raise EvidenceIntegrityError(
                f"Non-unknown trait {item.trait!r} requires an evidence timestamp"
            )
        if evidence_for_timestamp(observation, item.evidence_timestamp) is None:
            raise EvidenceIntegrityError(
                f"Evidence timestamp {item.evidence_timestamp} for trait {item.trait!r} "
                "is outside the source observation's evidence ranges"
            )


class FootballReasoner:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def reason(self, observation: FootballObservation,
                     allowed_traits: list[str] | None = None) -> FootballReasoningResult:
        trait_rule = ""
        if allowed_traits:
            trait_rule = ("\nUse only these official position traits: "
                          + ", ".join(allowed_traits)
                          + ". Do not rename them or invent display-category traits.")
        prompt = (SYSTEM_RULE + trait_rule + "\nStructured source observation:\n"
                  + json.dumps(observation.model_dump(mode="json")))
        raw = await self.provider.generate_json(prompt, FootballReasoningResult.model_json_schema())
        result = FootballReasoningResult.model_validate(raw)
        validate_reasoning_evidence(observation, result)
        return result
