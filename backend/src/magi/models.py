from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CoreId = Literal["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"]
CORE_ORDER: tuple[CoreId, ...] = (
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
)
ActKind = Literal[
    "POSITION",
    "CHALLENGE",
    "RESPONSE",
    "CONCEDE",
    "PROPOSE_CONDITION",
    "CLARIFY",
    "READY",
    "PASS",
]
Vote = Literal["AGREE", "DISAGREE", "CONDITIONAL"]
DecisionPolicy = Literal["majority", "unanimous", "human_confirm"]
Recommendation = Literal[
    "APPROVED",
    "APPROVED_WITH_CONDITIONS",
    "REJECTED",
    "INCOMPLETE",
]
DecisionOutcome = Literal[
    "APPROVED",
    "APPROVED_WITH_CONDITIONS",
    "REJECTED",
    "HUMAN_CONFIRMATION_REQUIRED",
    "INCOMPLETE",
]
CoreStatus = Literal[
    "LISTENING",
    "THINKING",
    "SPEAKING",
    "READY",
    "BUDGET_EXHAUSTED",
    "FAILED",
]


class _PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Motion(_PublicModel):
    question: str = Field(min_length=3, max_length=2_000)
    context: str = Field(default="", max_length=8_000)
    quorum: DecisionPolicy = "majority"


class Act(_PublicModel):
    core: CoreId
    kind: ActKind
    content: str = Field(min_length=1, max_length=2_000)
    reply_to: int | None = None


class Ballot(_PublicModel):
    core: CoreId
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=2_000)
    conditions: list[str] = Field(default_factory=list, max_length=8)


class PhaseEvent(_PublicModel):
    type: Literal["phase"] = "phase"
    phase: Literal["OPENING", "DISCUSSION", "BALLOTING"]
    active_cores: list[CoreId]


class ActEvent(_PublicModel):
    type: Literal["act"] = "act"
    id: int = Field(ge=1)
    seen_through_event_id: int = Field(ge=0)
    act: Act


class CoreStatusEvent(_PublicModel):
    type: Literal["core_status"] = "core_status"
    core: CoreId
    status: CoreStatus
    reviewed_through_event_id: int = Field(ge=0)


class BallotsLockedEvent(_PublicModel):
    type: Literal["ballots_locked"] = "ballots_locked"


class ResultEvent(_PublicModel):
    type: Literal["result"] = "result"
    quorum: DecisionPolicy
    recommendation: Recommendation
    outcome: DecisionOutcome
    requires_human_confirmation: bool
    ballots: list[Ballot]
    conditions: list[str]
    disclaimer: str


class ErrorEvent(_PublicModel):
    type: Literal["error"] = "error"
    message: str


StreamEvent = (
    PhaseEvent
    | ActEvent
    | CoreStatusEvent
    | BallotsLockedEvent
    | ResultEvent
    | ErrorEvent
)
