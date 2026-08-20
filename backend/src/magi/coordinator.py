from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Literal, TypeVar, cast

from .budgets import BudgetLedger, DiscussionLimits
from .models import (
    CORE_ORDER,
    Act,
    Ballot,
    CoreId,
    CoreStatusEvent,
    Generation,
    Motion,
    PhaseEvent,
    ResultEvent,
    ReviewDecision,
    StreamEvent,
)
from .policy import reduce_ballots
from .prompts import ballot_messages, opening_messages, reaction_messages
from .session import MagiSession
from .transcript import Transcript

DISCLAIMER = "Decision support only; this simulation does not make decisions or take real-world actions."
BALLOT_REQUEST_ROUNDS = 2

T = TypeVar("T", Act, ReviewDecision, Ballot)
Ask = Callable[
    [CoreId, list[dict[str, str]], type[T], Literal["high", "max"], int],
    Awaitable[Generation[T]],
]


class CoordinatorFailure(Exception):
    """Sanitized internal marker for provider or public-model failures."""


class ReactiveCoordinator:
    def __init__(
        self,
        ask: Ask,
        *,
        limits: DiscussionLimits | None = None,
        review_debounce_seconds: float = 0.15,
    ) -> None:
        if review_debounce_seconds < 0:
            raise ValueError("review_debounce_seconds must be non-negative")
        self.ask = ask
        self.limits = limits or DiscussionLimits()
        self.review_debounce_seconds = review_debounce_seconds
        self.transcript = Transcript()
        self.session = MagiSession()
        self.budgets: BudgetLedger | None = None
        self.inboxes = {core: asyncio.Queue[int]() for core in CORE_ORDER}
        self._output: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self._changed = asyncio.Event()
        self._stop = asyncio.Event()
        self._workers: list[asyncio.Task[None]] = []
        self._deadline_task: asyncio.Task[None] | None = None
        self._timed_out = False
        self._motion: Motion | None = None
        self._started = False

    async def run(self, motion: Motion) -> AsyncIterator[StreamEvent]:
        if self._started:
            raise RuntimeError("ReactiveCoordinator instances can run only once")
        self._started = True
        self._motion = motion

        try:
            self.session.begin_opening()
            yield PhaseEvent(phase="OPENING", active_cores=list(CORE_ORDER))
            for core in CORE_ORDER:
                yield CoreStatusEvent(
                    core=core,
                    status="THINKING",
                    reviewed_through_event_id=0,
                )
            openings = await self._openings(motion)

            # get all three openings first so nobody gets to react early
            self.budgets = BudgetLedger(self.limits)
            for generation in openings:
                self.budgets.record_usage(generation.usage)
            staged_transcript = Transcript()
            try:
                opening_events = [
                    staged_transcript.append(
                        generation.value,
                        seen_through_event_id=0,
                    )
                    for generation in openings
                ]
            except ValueError:
                raise CoordinatorFailure from None
            self.transcript = staged_transcript
            for event in opening_events:
                yield CoreStatusEvent(
                    core=event.act.core,
                    status="LISTENING",
                    reviewed_through_event_id=0,
                )
                yield event

            self.session.begin_discussion()
            yield PhaseEvent(phase="DISCUSSION", active_cores=list(CORE_ORDER))
            self._deadline_task = asyncio.create_task(self._discussion_deadline())

            if not self.budgets.discussion_expired():
                self._workers = [
                    asyncio.create_task(self._worker(core), name=f"magi-review-{core}")
                    for core in CORE_ORDER
                ]
                for core in CORE_ORDER:
                    self._notify(core, self.transcript.version)

            reason = None
            while reason is None:
                while not self._output.empty():
                    event = self._output.get_nowait()
                    self._output.task_done()
                    yield event
                reason = self._closure_reason()
                if reason is not None:
                    break
                self._changed.clear()
                if not self._output.empty() or self._closure_reason() is not None:
                    continue
                await self._changed.wait()

            self._stop.set()
            self._changed.set()
            await asyncio.gather(*self._workers, return_exceptions=True)
            while not self._output.empty():
                event = self._output.get_nowait()
                self._output.task_done()
                yield event

            if any(not self.session.core(core).ballot_eligible for core in CORE_ORDER):
                reason = "failure"
            self.session.close_discussion(reason=reason)

            if not self.session.can_start_ballots():
                self.session.fail()
                yield self._incomplete_result()
                return

            self.session.begin_balloting()
            yield PhaseEvent(phase="BALLOTING", active_cores=list(CORE_ORDER))
            frozen = self.transcript.freeze()
            ballots_by_core: dict[CoreId, Generation[Ballot]] = {}
            pending_cores = list(CORE_ORDER)
            # failed ballots get one full retry round
            for _ in range(BALLOT_REQUEST_ROUNDS):
                round_results = await asyncio.gather(
                    *(
                        self.ask(
                            core,
                            ballot_messages(core, motion, frozen.events),
                            Ballot,
                            "max",
                            8192,
                        )
                        for core in pending_cores
                    ),
                    return_exceptions=True,
                )
                failed_cores: list[CoreId] = []
                for core, result in zip(pending_cores, round_results, strict=True):
                    if isinstance(result, Generation):
                        ballots_by_core[core] = cast(Generation[Ballot], result)
                    else:
                        failed_cores.append(core)
                pending_cores = failed_cores
                if not pending_cores:
                    break

            for generation in ballots_by_core.values():
                self.budgets.record_usage(generation.usage)

            if len(ballots_by_core) != len(CORE_ORDER):
                self.session.fail()
                yield self._incomplete_result()
                return

            ballots = [ballots_by_core[core].value for core in CORE_ORDER]
            decision = reduce_ballots(ballots)
            self.session.begin_revealing()
            yield ResultEvent(
                outcome=decision.outcome,
                ballots=ballots,
                conditions=list(decision.conditions),
                disclaimer=DISCLAIMER,
            )
            self.session.complete()
        except asyncio.CancelledError:
            if self.session.phase not in {"COMPLETED", "FAILED", "CANCELLED"}:
                self.session.cancel()
            raise
        except Exception:
            if self.session.phase not in {"COMPLETED", "FAILED", "CANCELLED"}:
                self.session.fail()
            raise
        finally:
            self._stop.set()
            if self._deadline_task is not None:
                self._deadline_task.cancel()
                await asyncio.gather(self._deadline_task, return_exceptions=True)
            for task in self._workers:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)

    async def _openings(self, motion: Motion) -> list[Generation[Act]]:
        tasks = [
            asyncio.create_task(
                self.ask(
                    core,
                    opening_messages(core, motion),
                    Act,
                    "high",
                    4096,
                )
            )
            for core in CORE_ORDER
        ]
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            if any(task.exception() is not None for task in done):
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise CoordinatorFailure
            await asyncio.gather(*pending)
            return [task.result() for task in tasks]
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _discussion_deadline(self) -> None:
        await asyncio.sleep(self.limits.timeout_seconds)
        self._timed_out = True
        self._changed.set()

    def _closure_reason(
        self,
    ) -> Literal["natural", "budget", "timeout", "failure"] | None:
        assert self.budgets is not None
        if any(not self.session.core(core).ballot_eligible for core in CORE_ORDER):
            return "failure"
        if self.session.can_close_naturally(latest_event_id=self.transcript.version):
            return "natural"
        if self._timed_out:
            return "timeout"
        if self.budgets.total_tokens >= self.limits.max_total_tokens:
            return "budget"
        settled = all(
            state.status in {"READY", "BUDGET_EXHAUSTED"}
            and not state.in_flight
            and state.inbox_depth == 0
            for state in (self.session.core(core) for core in CORE_ORDER)
        )
        return "budget" if settled else None

    async def _worker(self, core: CoreId) -> None:
        retry_current = False
        while not self._stop.is_set():
            consumed = 0
            versions: list[int] = []
            try:
                if retry_current:
                    await asyncio.sleep(self.review_debounce_seconds)
                    while not self.inboxes[core].empty():
                        versions.append(self.inboxes[core].get_nowait())
                        consumed += 1
                else:
                    first = await self._next_notification(core)
                    if first is None:
                        return
                    versions.append(first)
                    consumed = 1
                    # fold quick transcript updates into one review call
                    await asyncio.sleep(self.review_debounce_seconds)
                    while not self.inboxes[core].empty():
                        versions.append(self.inboxes[core].get_nowait())
                        consumed += 1

                if self._stop.is_set():
                    return
                state = self.session.core(core)
                if (
                    versions
                    and max(versions) <= state.reviewed_through_event_id
                    and not retry_current
                ):
                    retry_current = False
                    continue
                assert self.budgets is not None
                if not self.budgets.can_evaluate(core):
                    self._mark_budget_exhausted(core)
                    return

                snapshot = self.transcript.snapshot()
                last_reviewed = state.reviewed_through_event_id
                self.session.mark_in_flight(core, True)
                self._emit_status(core, "THINKING")
                self._changed.set()
                try:
                    generation = await self.ask(
                        core,
                        reaction_messages(
                            core,
                            cast(Motion, self._motion),
                            snapshot,
                            last_reviewed,
                            self.budgets.remaining_contributions(core),
                            self.budgets.remaining_evaluations(core),
                            state.ready,
                            requires_public_contribution=not self.budgets.has_contributed(
                                core
                            ),
                        ),
                        ReviewDecision,
                        "high",
                        4096,
                    )
                    self.budgets.record_evaluation(core, generation.usage)
                    self.session.mark_reviewed(core, snapshot.version)
                    retry_current = self._apply_reaction(
                        core,
                        generation.value,
                        snapshot.version,
                    )
                finally:
                    if self.session.core(core).in_flight:
                        self.session.mark_in_flight(core, False)
                self._changed.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                if (
                    self.session.phase == "DISCUSSING"
                    and self.session.core(core).ballot_eligible
                ):
                    self.session.mark_failed(core)
                    self._emit_status(core, "FAILED")
                return
            finally:
                for _ in range(consumed):
                    self.inboxes[core].task_done()
                    self.session.note_dequeued(core)
                if consumed:
                    self._changed.set()

    async def _next_notification(self, core: CoreId) -> int | None:
        get_task = asyncio.create_task(self.inboxes[core].get())
        stop_task = asyncio.create_task(self._stop.wait())
        done, pending = await asyncio.wait(
            {get_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if get_task in done:
            return get_task.result()
        return None

    def _apply_reaction(
        self,
        core: CoreId,
        decision: ReviewDecision,
        seen_version: int,
    ) -> bool:
        assert self.budgets is not None
        if not self.budgets.has_contributed(core) and decision.action != "PUBLISH":
            self._emit_status(core, "LISTENING")
            if not self.budgets.can_evaluate(core):
                self._mark_budget_exhausted(core)
                return False
            return True

        if decision.action == "PASS":
            self._emit_status(core, "LISTENING")
        elif decision.action == "READY":
            self.session.mark_ready(core)
            self._emit_status(core, "READY")
            return False
        elif self.budgets.remaining_contributions(core) > 0:
            assert decision.kind is not None
            assert decision.content is not None
            act = Act(
                core=core,
                kind=decision.kind,
                content=decision.content,
                reply_to=decision.reply_to,
            )
            self.budgets.record_contribution(core)
            event = self.transcript.append(act, seen_through_event_id=seen_version)
            if event.id == seen_version + 1:
                self.session.mark_reviewed(core, event.id)
            self._emit_status(core, "LISTENING")
            self._emit(event)
            # a new public act makes the old READY states stale
            self.session.revoke_peer_readiness(sender=core)
            for peer in CORE_ORDER:
                if peer != core:
                    self._notify(peer, event.id)
        else:
            self._mark_budget_exhausted(core)
            return False

        if not self.budgets.can_evaluate(core):
            self._mark_budget_exhausted(core)
            return False
        return True

    def _notify(self, core: CoreId, version: int) -> None:
        assert self.budgets is not None
        state = self.session.core(core)
        if (
            self._stop.is_set()
            or not state.ballot_eligible
            or state.status == "BUDGET_EXHAUSTED"
            or not self.budgets.can_evaluate(core)
        ):
            return
        self.inboxes[core].put_nowait(version)
        self.session.note_enqueued(core)
        self._changed.set()

    def _mark_budget_exhausted(self, core: CoreId) -> None:
        assert self.budgets is not None
        if not self.budgets.has_contributed(core):
            self.session.mark_failed(core)
            self._emit_status(core, "FAILED")
            return
        if self.session.core(core).status == "BUDGET_EXHAUSTED":
            return
        self.session.mark_budget_exhausted(core)
        self._emit_status(core, "BUDGET_EXHAUSTED")

    def _emit_status(
        self,
        core: CoreId,
        status: Literal[
            "LISTENING",
            "THINKING",
            "READY",
            "BUDGET_EXHAUSTED",
            "FAILED",
        ],
    ) -> None:
        self._emit(
            CoreStatusEvent(
                core=core,
                status=status,
                reviewed_through_event_id=self.session.core(
                    core
                ).reviewed_through_event_id,
            )
        )

    def _emit(self, event: StreamEvent) -> None:
        self._output.put_nowait(event)
        self._changed.set()

    def _incomplete_result(self) -> ResultEvent:
        return ResultEvent(
            outcome="INCOMPLETE",
            ballots=[],
            conditions=[],
            disclaimer=DISCLAIMER,
        )
