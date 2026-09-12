import asyncio

import pytest

from backend.ai.football_reasoner import (
    EvidenceIntegrityError,
    FootballReasoner,
    FootballReasoningResult,
)
from backend.ai.provider import AIProvider
from backend.football.observations import FootballObservation
from backend.grading.event_mapper import reasoning_to_events
from backend.grading.models import Evidence
from backend.grading.service import calculate_official_grade


class StaticProvider(AIProvider):
    def __init__(self, response):
        self.response = response

    async def generate_json(self, prompt, schema):
        return self.response


def source(timestamp_start=1.0, timestamp_end=2.0):
    return FootballObservation(
        observation_id="O1",
        play_id="P1",
        player_id="19",
        position="LB",
        evidence=[Evidence(
            video_id="V1",
            play_id="P1",
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            description="Verified film range",
        )],
    )


def reasoning(value="positive_execution", evidence_timestamp=1.5):
    return FootballReasoningResult(observations=[{
        "trait": "read_react",
        "value": value,
        "confidence": .8,
        "evidence_timestamp": evidence_timestamp,
        "reason": "Observed on verified film.",
    }])


@pytest.mark.parametrize("evidence_timestamp", [None, 2.1])
def test_reasoner_rejects_unlinked_non_unknown_claims(evidence_timestamp):
    provider = StaticProvider(reasoning(evidence_timestamp=evidence_timestamp).model_dump())

    with pytest.raises(EvidenceIntegrityError):
        asyncio.run(FootballReasoner(provider).reason(source()))


@pytest.mark.parametrize("evidence_timestamp", [None, 2.1])
def test_mapper_rejects_unlinked_non_unknown_claims(evidence_timestamp):
    with pytest.raises(EvidenceIntegrityError):
        reasoning_to_events(source(), reasoning(evidence_timestamp=evidence_timestamp))


def test_unknown_without_evidence_remains_non_scoring_and_is_not_timestamped_at_zero():
    observation = FootballObservation(
        observation_id="O1", play_id="P1", player_id="19", position="LB"
    )

    grade, events = calculate_official_grade(
        "LB", [(observation, reasoning(value="unknown", evidence_timestamp=None))]
    )

    assert events == []
    assert grade.grade is None
    assert grade.confidence == 0


def test_real_zero_timestamp_is_retained_when_backed_by_evidence():
    events = reasoning_to_events(source(timestamp_start=0, timestamp_end=.5),
                                 reasoning(evidence_timestamp=0))

    assert events[0].timestamp == 0
    assert events[0].evidence == source(timestamp_start=0, timestamp_end=.5).evidence[0]
