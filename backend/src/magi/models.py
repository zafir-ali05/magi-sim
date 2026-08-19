from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
]
ReviewAction = Literal["READY", "PASS", "PUBLISH"]
ReviewPublicationKind = Literal[
    "CHALLENGE",
    "RESPONSE",
    "CONCEDE",
    "PROPOSE_CONDITION",
    "CLARIFY",
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


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TokenUsage:
    # reasoning text gets dropped, but its token count still matters for the budget
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class Generation(Generic[T]):
    value: T
    usage: TokenUsage


class _PublicModel(BaseModel):
    # reject extra fields from both the API and the model
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


class ReviewDecision(_PublicModel):
    core: CoreId
    action: ReviewAction
    kind: ReviewPublicationKind | None = None
    content: str | None = Field(default=None, min_length=1, max_length=2_000)
    reply_to: int | None = None

    @model_validator(mode="after")
    def validate_action_shape(self) -> ReviewDecision:
        # PUBLISH is public, READY and PASS are only worker controls
        if self.action == "PUBLISH":
            if self.kind is None or self.content is None:
                raise ValueError("PUBLISH requires kind and content")
        elif (
            self.kind is not None
            or self.content is not None
            or self.reply_to is not None
        ):
            raise ValueError("READY and PASS cannot contain public act fields")
        return self


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
