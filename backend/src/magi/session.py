from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import CORE_ORDER, CoreId, CoreStatus


SessionPhase = Literal[
    "CREATED",
    "OPENING",
    "DISCUSSING",
    "DISCUSSION_CLOSED",
    "BALLOTING",
    "REVEALING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]
ClosureReason = Literal["natural", "budget", "timeout", "failure"]

TERMINAL_PHASES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
CLOSURE_REASONS = frozenset({"natural", "budget", "timeout", "failure"})


@dataclass
class CoreRuntimeState:
    reviewed_through_event_id: int = 0
    ready: bool = False
    in_flight: bool = False
    inbox_depth: int = 0
    status: CoreStatus = "LISTENING"
    ballot_eligible: bool = True


class MagiSession:
    def __init__(self) -> None:
        self.cores: tuple[CoreId, ...] = CORE_ORDER
        self.phase: SessionPhase = "CREATED"
        self.closure_reason: ClosureReason | None = None
        self._cores = {core: CoreRuntimeState() for core in self.cores}

    def core(self, core: CoreId) -> CoreRuntimeState:
        try:
            return self._cores[core]
        except KeyError:
            raise ValueError(f"Unknown MAGI core: {core}") from None

    def _require_phase(self, expected: SessionPhase) -> None:
        if self.phase in TERMINAL_PHASES:
            raise RuntimeError(f"Session is terminal in phase {self.phase}")
        if self.phase != expected:
            raise RuntimeError(f"Operation requires phase {expected}; current phase is {self.phase}")

    def _require_discussing(self) -> None:
        self._require_phase("DISCUSSING")

    def begin_opening(self) -> None:
        self._require_phase("CREATED")
        self.phase = "OPENING"

    def begin_discussion(self, *, latest_event_id: int) -> None:
        self._require_phase("OPENING")
        if latest_event_id < 0:
            raise ValueError("Latest event id must be non-negative")
        self.phase = "DISCUSSING"

    def mark_in_flight(self, core: CoreId, in_flight: bool) -> None:
        self._require_discussing()
        state = self.core(core)
        if in_flight and state.in_flight:
            raise RuntimeError(f"{core} request is already in flight")

        state.in_flight = in_flight
        if in_flight:
            state.status = "THINKING"
        elif state.status == "THINKING":
            state.status = "READY" if state.ready else "LISTENING"

    def mark_reviewed(self, core: CoreId, event_id: int) -> None:
        self._require_discussing()
        if event_id < 0:
            raise ValueError("Reviewed event id must be non-negative")
        state = self.core(core)
        if event_id < state.reviewed_through_event_id:
            raise ValueError("Reviewed event id cannot move backwards")
        state.reviewed_through_event_id = event_id

    def mark_ready(self, core: CoreId) -> None:
        self._require_discussing()
        state = self.core(core)
        if not state.ballot_eligible:
            raise RuntimeError(f"{core} is unavailable")
        state.ready = True
        state.status = "READY"

    def mark_budget_exhausted(self, core: CoreId) -> None:
        self._require_discussing()
        state = self.core(core)
        state.ready = False
        state.in_flight = False
        state.status = "BUDGET_EXHAUSTED"

    def mark_failed(self, core: CoreId) -> None:
        self._require_discussing()
        state = self.core(core)
        state.ready = False
        state.in_flight = False
        state.status = "FAILED"
        state.ballot_eligible = False

    def note_enqueued(self, core: CoreId) -> None:
        self._require_discussing()
        self.core(core).inbox_depth += 1

    def note_dequeued(self, core: CoreId) -> None:
        self._require_discussing()
        state = self.core(core)
        if state.inbox_depth == 0:
            raise ValueError(f"{core} inbox is already empty")
        state.inbox_depth -= 1

    def revoke_peer_readiness(self, *, sender: CoreId) -> None:
        self._require_discussing()
        self.core(sender)
        for core, state in self._cores.items():
            if core == sender or not state.ready:
                continue
            state.ready = False
            state.status = "LISTENING"

    def can_close_naturally(self, *, latest_event_id: int) -> bool:
        if self.phase != "DISCUSSING" or latest_event_id < 0:
            return False
        return all(
            state.ready
            and state.reviewed_through_event_id >= latest_event_id
            and not state.in_flight
            and state.inbox_depth == 0
            for state in self._cores.values()
        )

    def close_discussion(self, *, reason: ClosureReason) -> None:
        self._require_discussing()
        if reason not in CLOSURE_REASONS:
            raise ValueError(f"Unsupported closure reason: {reason}")
        self.closure_reason = reason
        self.phase = "DISCUSSION_CLOSED"

    def can_start_ballots(self) -> bool:
        return self.phase == "DISCUSSION_CLOSED" and all(
            state.ballot_eligible for state in self._cores.values()
        )

    def begin_balloting(self) -> None:
        self._require_phase("DISCUSSION_CLOSED")
        if not self.can_start_ballots():
            raise RuntimeError("All MAGI cores must be ballot eligible")
        self.phase = "BALLOTING"

    def begin_revealing(self) -> None:
        self._require_phase("BALLOTING")
        self.phase = "REVEALING"

    def complete(self) -> None:
        self._require_phase("REVEALING")
        self.phase = "COMPLETED"

    def fail(self) -> None:
        self._enter_terminal("FAILED")

    def cancel(self) -> None:
        self._enter_terminal("CANCELLED")

    def _enter_terminal(self, phase: Literal["FAILED", "CANCELLED"]) -> None:
        if self.phase in TERMINAL_PHASES:
            raise RuntimeError(f"Session is already terminal in phase {self.phase}")
        self.phase = phase
