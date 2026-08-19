# Reactive Deliberation Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the lean MVP's synchronized reaction rounds with three bounded, event-driven MAGI workers that react to committed peer acts in causal completion order.

**Architecture:** Keep the existing FastAPI endpoint, NDJSON transport, DeepSeek adapter, refined identities, private ballots, quorum reducer, and React console. Add a validated append-only transcript, usage-aware budgets, a pure session aggregate, and one `asyncio.Queue` worker per core; the coordinator gates reactions until all independent openings finish, then fans each committed act to the other two workers and freezes one transcript for simultaneous ballots.

**Tech Stack:** Python 3.12, FastAPI, asyncio, Pydantic, OpenAI-compatible DeepSeek client, pytest/pytest-asyncio, React 19, Vite 7, Node test runner, NDJSON.

**Spec:** `docs/initial-planning.md` sections 3–6 and `docs/superpowers/plans/2026-08-17-magi-sim-mvp.md` Tasks 2–5. This migration deliberately retains NDJSON; replayable SSE remains a later long-term task.

## Global Constraints

- Keep the core IDs exactly `MELCHIOR-1`, `BALTHASAR-2`, and `CASPER-3`.
- All three openings must finish independently before any reaction worker starts.
- Peers receive only completed, validated public acts; partial JSON and provider `reasoning_content` never enter the transcript.
- DeepSeek opening/reaction calls use `deepseek-v4-flash`, thinking enabled, high reasoning, and 4,096 output tokens; ballots use max reasoning and 8,192 output tokens.
- A core may have at most one provider request in flight.
- Default limits are three public reactions and five reaction evaluations per core, plus the existing five-minute session timeout.
- `PASS` and `READY` consume an evaluation but do not become transcript acts or public contributions.
- A new peer act conservatively revokes readiness until that core reviews the new transcript version.
- Natural completion requires every core ready, every core reviewed through the latest event, every inbox empty, and no request in flight.
- Forced completion cancels discussion work, freezes the latest valid transcript, and proceeds to ballots without fabricating readiness.
- All ballots use the same frozen transcript, stay private until all three complete, and reveal atomically.
- The migration does not add Redis, WebSockets, SSE replay, durable storage, accounts, evidence retrieval, user interjections, Ireul mode, or external action execution.
- Preserve the current JavaScript frontend and do not convert it to TypeScript.
- Do not modify `.gitignore`.

## Progress

| Task | Deliverable | Status |
| --- | --- | --- |
| 0 | Stable lean-MVP checkpoint | Completed |
| 1 | Causal public event contract and transcript | Not started |
| 2 | Usage-aware provider result and bounded budget ledger | Not started |
| 3 | Pure MAGI session aggregate and completion predicate | Not started |
| 4 | Reactive inbox workers and coordinator | Not started |
| 5 | NDJSON status integration and frontend activity reducer | Not started |
| 6 | Deterministic reactive acceptance scenario and cleanup | Not started |

Update both the checkbox steps and this table whenever a task is completed.

---

### Task 0: Create a stable lean-MVP checkpoint

**Files:**
- Verify only: `backend/src/magi/prompts.py`
- Verify only: `backend/tests/test_deepseek.py`
- Verify only: `frontend/src/App.jsx`
- Verify only: `frontend/src/MagiCoreArray.jsx`
- Verify only: `frontend/src/magiVisualState.js`
- Verify only: `frontend/src/styles.css`
- Verify only: related frontend tests

**Interfaces:**
- Consumes: the current uncommitted agent-context and speaker-light work.
- Produces: one known-working commit before concurrency and protocol changes begin.

- [x] **Step 1: Inspect the exact pending scope**

Run:

```bash
git status --short
git diff -- backend/src/magi/prompts.py backend/tests/test_deepseek.py frontend/src
```

Expected: only the refined contexts, speaker-following UI, and their tests appear in this checkpoint; `.gitignore` has no diff.

- [x] **Step 2: Run the current backend acceptance suite**

Run:

```bash
cd backend
.venv/bin/pytest -q
```

Expected: all backend tests pass.

- [x] **Step 3: Run the current frontend acceptance suite and build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all frontend tests pass and Vite exits successfully. Remove the generated untracked `frontend/dist/` directory after recording the result.

- [x] **Step 4: Commit the checkpoint**

Run from the repository root:

```bash
git add backend/src/magi/prompts.py backend/tests/test_deepseek.py frontend/src/App.jsx frontend/src/MagiComponents.test.js frontend/src/MagiCoreArray.jsx frontend/src/magiVisualState.js frontend/src/magiVisualState.test.js frontend/src/styles.css
git add -f docs/superpowers/plans/2026-08-19-reactive-deliberation-upgrade.md
git commit -m "feat: refine MAGI identities and speaker states"
```

Expected: the reactive migration begins from a clean application-code worktree. Ignored documentation files are not part of this commit.

---

### Task 1: Add the causal event contract and append-only transcript

**Files:**
- Create: `backend/src/magi/transcript.py`
- Create: `backend/tests/test_transcript.py`
- Modify: `backend/src/magi/models.py`
- Modify: `backend/src/magi/deliberation.py`
- Modify: `backend/tests/test_deliberation.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/events.js`
- Modify: `frontend/src/events.test.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/CoreResponseDialog.jsx`
- Modify: `frontend/src/magiVisualState.js`
- Modify: `frontend/scripts/mock-discussion-server.mjs`
- Modify: `frontend/scripts/mock-discussion-server.test.js`

**Interfaces:**
- Produces: `Transcript.append(act: Act, seen_through_event_id: int) -> ActEvent`.
- Produces: `Transcript.snapshot() -> FrozenTranscript` and `Transcript.freeze() -> FrozenTranscript`.
- Produces: `FrozenTranscript.version: int` and `FrozenTranscript.events: tuple[ActEvent, ...]`.
- Produces: public `CoreStatusEvent` with `core`, `status`, and `reviewed_through_event_id`.
- Changes: `ActEvent.round` is replaced by `ActEvent.seen_through_event_id`.

- [ ] **Step 1: Write transcript integrity tests**

Create `backend/tests/test_transcript.py` with tests equivalent to:

```python
import pytest

from magi.models import Act
from magi.transcript import Transcript, TranscriptFrozenError


def test_transcript_assigns_contiguous_ids_and_preserves_seen_version():
    transcript = Transcript()
    first = transcript.append(
        Act(core="MELCHIOR-1", kind="POSITION", content="Initial claim."),
        seen_through_event_id=0,
    )
    second = transcript.append(
        Act(core="CASPER-3", kind="CHALLENGE", content="Challenge.", reply_to=1),
        seen_through_event_id=1,
    )

    assert (first.id, second.id) == (1, 2)
    assert second.seen_through_event_id == 1
    assert transcript.snapshot().version == 2


def test_transcript_rejects_missing_future_and_unseen_replies():
    transcript = Transcript()
    transcript.append(
        Act(core="MELCHIOR-1", kind="POSITION", content="Initial claim."),
        seen_through_event_id=0,
    )

    with pytest.raises(ValueError, match="reply_to"):
        transcript.append(
            Act(core="CASPER-3", kind="CHALLENGE", content="Invalid.", reply_to=1),
            seen_through_event_id=0,
        )


def test_frozen_transcript_rejects_new_events():
    transcript = Transcript()
    frozen = transcript.freeze()

    assert frozen.version == 0
    with pytest.raises(TranscriptFrozenError):
        transcript.append(
            Act(core="MELCHIOR-1", kind="POSITION", content="Too late."),
            seen_through_event_id=0,
        )
```

- [ ] **Step 2: Run the transcript tests and confirm the missing-module failure**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_transcript.py -q
```

Expected: collection fails because `magi.transcript` does not exist.

- [ ] **Step 3: Extend the public event models**

In `backend/src/magi/models.py`, define:

```python
CoreStatus = Literal[
    "LISTENING",
    "THINKING",
    "SPEAKING",
    "READY",
    "BUDGET_EXHAUSTED",
    "FAILED",
]


class CoreStatusEvent(_PublicModel):
    type: Literal["core_status"] = "core_status"
    core: CoreId
    status: CoreStatus
    reviewed_through_event_id: int = Field(ge=0)


class ActEvent(_PublicModel):
    type: Literal["act"] = "act"
    id: int = Field(ge=1)
    seen_through_event_id: int = Field(ge=0)
    act: Act
```

Add `CoreStatusEvent` to `StreamEvent` and remove `round` from every backend and frontend fixture. Opening acts use `seen_through_event_id=0`; a batch reaction temporarily uses the frozen transcript's latest event ID until Task 4 replaces batching.

- [ ] **Step 4: Implement the minimal transcript**

Create immutable `FrozenTranscript` and mutable `Transcript` in `backend/src/magi/transcript.py`. `append` must reject `PASS` and `READY`, reject `seen_through_event_id` above the current version, and require `reply_to <= seen_through_event_id` for replies.

```python
from dataclasses import dataclass

from .models import Act, ActEvent


class TranscriptFrozenError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenTranscript:
    version: int
    events: tuple[ActEvent, ...]


class Transcript:
    def __init__(self) -> None:
        self._events: list[ActEvent] = []
        self._frozen = False

    @property
    def version(self) -> int:
        return len(self._events)

    def snapshot(self) -> FrozenTranscript:
        return FrozenTranscript(self.version, tuple(self._events))

    def freeze(self) -> FrozenTranscript:
        self._frozen = True
        return self.snapshot()
```

Complete `append` according to the tests without adding storage or persistence.

- [ ] **Step 5: Update the current batch coordinator and public clients**

Use `Transcript` inside the existing `deliberation.py` so the application remains functional before Task 4. Update frontend validation to accept exactly:

```javascript
{
  type: "act",
  id: 2,
  seen_through_event_id: 1,
  act: {
    core: "CASPER-3",
    kind: "CHALLENGE",
    content: "Challenge.",
    reply_to: 1,
  },
}
```

Replace visible `R{round}` labels with `SEEN {seen_through_event_id}` and remove round counters from session state. Parse `core_status` strictly but do not render it until Task 5.

- [ ] **Step 6: Run backend and frontend protocol suites**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_transcript.py tests/test_deliberation.py tests/test_api.py -q
cd ../frontend
npm test
```

Expected: all selected backend tests and all frontend tests pass.

- [ ] **Step 7: Commit the causal protocol**

```bash
git add backend/src/magi/models.py backend/src/magi/transcript.py backend/src/magi/deliberation.py backend/tests/test_transcript.py backend/tests/test_deliberation.py backend/tests/test_api.py frontend/src/events.js frontend/src/events.test.js frontend/src/App.jsx frontend/src/CoreResponseDialog.jsx frontend/src/magiVisualState.js frontend/scripts/mock-discussion-server.mjs frontend/scripts/mock-discussion-server.test.js
git commit -m "feat: add causal MAGI transcript protocol"
```

---

### Task 2: Return provider usage and enforce discussion budgets

**Files:**
- Create: `backend/src/magi/budgets.py`
- Create: `backend/tests/test_budgets.py`
- Modify: `backend/src/magi/deepseek.py`
- Modify: `backend/tests/test_deepseek.py`
- Modify: `backend/src/magi/deliberation.py`
- Modify: `backend/tests/test_deliberation.py`

**Interfaces:**
- Produces: `TokenUsage(prompt_tokens, completion_tokens, reasoning_tokens, total_tokens)`.
- Produces: generic `Generation[T](value: T, usage: TokenUsage)` from `ask_deepseek`.
- Produces: `DiscussionLimits(max_contributions_per_core=3, max_evaluations_per_core=5, timeout_seconds=300, max_total_tokens=180_000)`.
- Produces: `BudgetLedger.can_evaluate(core)`, `can_contribute(core)`, `remaining_evaluations(core)`, `remaining_contributions(core)`, `record_evaluation(core, usage)`, and `record_contribution(core)`.

- [ ] **Step 1: Write failing provider-usage and budget tests**

Add a DeepSeek assertion:

```python
result = await ask_deepseek(
    "MELCHIOR-1",
    [{"role": "user", "content": "Return JSON."}],
    Probe,
    "high",
    4096,
)

assert result.value == Probe(core="MELCHIOR-1", content="ok")
assert result.usage.total_tokens == 28
assert result.usage.reasoning_tokens == 9
```

Create `backend/tests/test_budgets.py` with literal limits proving the fourth contribution and sixth evaluation are refused and total-token exhaustion ends discussion.

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
cd backend
.venv/bin/pytest tests/test_deepseek.py tests/test_budgets.py -q
```

Expected: failures show that `ask_deepseek` returns the raw model and `magi.budgets` is missing.

- [ ] **Step 3: Add usage value objects and return `Generation[T]`**

Use frozen dataclasses in `deepseek.py`:

```python
from dataclasses import dataclass
from typing import Generic


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class Generation(Generic[T]):
    value: T
    usage: TokenUsage
```

Continue discarding raw `reasoning_content`. Only aggregate integer counts leave the provider adapter.

- [ ] **Step 4: Implement `BudgetLedger`**

Store counts by exact `CoreId`, reject negative usage, use `time.monotonic()` for elapsed time, and expose a single `discussion_expired()` predicate. The ledger must not decide ballot outcomes or mutate session readiness.

- [ ] **Step 5: Adapt the temporary batch coordinator and fakes**

Update the `Ask` protocol and every fake provider to return `Generation(value, TokenUsage(0, 0, 0, 0))` when a test does not exercise accounting. Record usage after each successful opening, reaction, and ballot call; discussion budgets apply only to reactions, while the five-minute outer timeout still covers the entire request.

- [ ] **Step 6: Run the complete backend suite**

```bash
cd backend
.venv/bin/pytest -q
```

Expected: all backend tests pass and private reasoning remains absent from events and exceptions.

- [ ] **Step 7: Commit usage-aware budgets**

```bash
git add backend/src/magi/deepseek.py backend/src/magi/budgets.py backend/src/magi/deliberation.py backend/tests/test_deepseek.py backend/tests/test_budgets.py backend/tests/test_deliberation.py
git commit -m "feat: enforce MAGI discussion budgets"
```

---

### Task 3: Add the pure session aggregate and completion predicate

**Files:**
- Create: `backend/src/magi/session.py`
- Create: `backend/tests/test_session.py`

**Interfaces:**
- Consumes: `CoreId`, `CoreStatus`, `Transcript`, `BudgetLedger`.
- Produces: `CoreRuntimeState(reviewed_through_event_id, ready, in_flight, inbox_depth, status)`.
- Produces: `MagiSession.mark_in_flight`, `mark_reviewed`, `mark_ready`, `note_enqueued`, `note_dequeued`, `revoke_peer_readiness`, and `can_complete`.
- Produces: monotonic phase changes `CREATED → OPENING → DISCUSSING → BALLOTING → REVEALING → COMPLETED`, plus `FAILED` and `CANCELLED`.

- [ ] **Step 1: Write failing state-transition and completion tests**

Create tests that prove readiness is not consensus:

```python
from magi.session import MagiSession


def test_completion_requires_latest_review_empty_inboxes_and_no_in_flight_work():
    session = MagiSession()
    session.begin_opening()
    session.begin_discussion(latest_event_id=3)

    for core in session.cores:
        session.mark_reviewed(core, 3)
        session.mark_ready(core)

    assert session.can_complete(latest_event_id=3)

    session.note_enqueued("CASPER-3")
    assert not session.can_complete(latest_event_id=3)


def test_new_peer_event_revokes_ready_state():
    session = MagiSession()
    session.begin_opening()
    session.begin_discussion(latest_event_id=3)
    session.mark_reviewed("CASPER-3", 3)
    session.mark_ready("CASPER-3")

    session.revoke_peer_readiness(sender="MELCHIOR-1")

    assert not session.core("CASPER-3").ready
```

Also test forbidden backward transitions, events after terminal state, and monotonic `reviewed_through_event_id`.

- [ ] **Step 2: Run tests and confirm the missing-module failure**

```bash
cd backend
.venv/bin/pytest tests/test_session.py -q
```

Expected: collection fails because `magi.session` does not exist.

- [ ] **Step 3: Implement the session as a pure state owner**

Use dataclasses and explicit methods; do not place queues, provider calls, prompt building, or transcript mutation inside `MagiSession`.

```python
@dataclass
class CoreRuntimeState:
    reviewed_through_event_id: int = 0
    ready: bool = False
    in_flight: bool = False
    inbox_depth: int = 0
    status: CoreStatus = "LISTENING"
```

`can_complete(latest_event_id)` returns true only when every core is ready, reviewed through `latest_event_id`, not in flight, and has `inbox_depth == 0`.

- [ ] **Step 4: Run session and full backend tests**

```bash
cd backend
.venv/bin/pytest tests/test_session.py -q
.venv/bin/pytest -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit the session aggregate**

```bash
git add backend/src/magi/session.py backend/tests/test_session.py
git commit -m "feat: add MAGI session state machine"
```

---

### Task 4: Replace synchronized rounds with reactive inbox workers

**Files:**
- Create: `backend/src/magi/coordinator.py`
- Create: `backend/tests/test_coordinator.py`
- Modify: `backend/src/magi/deliberation.py`
- Modify: `backend/src/magi/prompts.py`
- Modify: `backend/tests/test_deepseek.py`
- Replace batch expectations in: `backend/tests/test_deliberation.py`

**Interfaces:**
- Consumes: `Transcript`, `BudgetLedger`, `MagiSession`, and usage-aware `Ask`.
- Produces: `ReactiveCoordinator.run(motion: Motion) -> AsyncIterator[StreamEvent]`.
- Produces: one `asyncio.Queue[int]` inbox and at most one worker task per core.
- Keeps: `deliberate(motion, ask=ask_deepseek) -> AsyncIterator[StreamEvent]` as the public API entry point.

- [ ] **Step 1: Write the parallel-opening gate test**

Use three `asyncio.Event` barriers in a fake provider. Assert all opening calls start, no reaction call starts before every opening is released, and opening `ActEvent`s commit in completion order rather than `CORE_ORDER`.

```python
assert fake.openings_started == set(CORE_ORDER)
assert fake.reactions_started_before_opening_gate == []
assert [event.act.core for event in opening_events] == [
    "CASPER-3",
    "MELCHIOR-1",
    "BALTHASAR-2",
]
```

- [ ] **Step 2: Write reactive causality and in-flight queueing tests**

Script this causal chain:

```text
MELCHIOR POSITION  → CASPER CHALLENGE
CASPER CHALLENGE   → MELCHIOR RESPONSE
MELCHIOR RESPONSE  → BALTHASAR PROPOSE_CONDITION
condition reviewed → all three READY
```

Assert every `reply_to` targets an event at or below `seen_through_event_id`, CASPER never has two requests in flight, and an event arriving during CASPER's request remains queued for its next evaluation.

- [ ] **Step 3: Write completion, budget, and failure tests**

Cover these terminal paths with deterministic fakes:

- all cores ready naturally;
- one core repeatedly returns `PASS` until its five evaluations are exhausted;
- one core uses three public reactions and cannot contribute a fourth;
- total-token exhaustion forces transcript freeze and ballots;
- cancellation stops every worker;
- permanent provider failure emits one sanitized error and no result.

- [ ] **Step 4: Run coordinator tests and verify they fail**

```bash
cd backend
.venv/bin/pytest tests/test_coordinator.py -q
```

Expected: collection fails because `magi.coordinator` does not exist.

- [ ] **Step 5: Update reaction prompts for unread events and budgets**

Change `reaction_messages` to accept:

```python
def reaction_messages(
    core: CoreId,
    motion: Motion,
    transcript: FrozenTranscript,
    unread_event_ids: tuple[int, ...],
    remaining_contributions: int,
    remaining_evaluations: int,
    currently_ready: bool,
) -> list[Message]:
```

The public response remains an `Act`. The coordinator supplies the snapshot version when it commits the response; the model must not choose or forge `seen_through_event_id`.

- [ ] **Step 6: Implement the opening gate and output queue**

`ReactiveCoordinator` owns a public output queue. Start openings concurrently, collect them with `asyncio.as_completed`, validate all three, commit them in completion order, then seed inboxes and start reaction workers. If any opening fails, cancel siblings and end with the existing sanitized failure.

- [ ] **Step 7: Implement one worker loop per core**

Each worker performs this bounded loop:

```python
while not stop_event.is_set():
    first_event_id = await inbox.get()
    unread = [first_event_id]
    await asyncio.sleep(0.15)
    while not inbox.empty():
        unread.append(inbox.get_nowait())

    snapshot = transcript.snapshot()
    session.mark_in_flight(core, True)
    messages = reaction_messages(
        core,
        motion,
        snapshot,
        tuple(unread),
        budgets.remaining_contributions(core),
        budgets.remaining_evaluations(core),
        session.core(core).ready,
    )
    generation = await ask(core, messages, Act, "high", 4096)
    session.mark_in_flight(core, False)
    session.mark_reviewed(core, snapshot.version)
    await apply_reaction(core, generation.value, snapshot.version)
```

The concrete implementation must use `try/finally` to clear in-flight state and `task_done()` for every dequeued notification.

- [ ] **Step 8: Implement reaction application and fan-out**

- `PASS`: record evaluation and emit `LISTENING`; append nothing.
- `READY`: record evaluation, mark ready, emit `READY`; append nothing.
- Public act with remaining contribution budget: append with `seen_through_event_id=snapshot.version`, emit it, revoke peer readiness, and enqueue the new event ID to both peers.
- Public act without contribution budget: emit `BUDGET_EXHAUSTED`, append nothing, and mark that core unable to evaluate further.

- [ ] **Step 9: Implement stable closure and private ballots**

When `session.can_complete(transcript.version)` or `budgets.discussion_expired()` becomes true, stop and join reaction workers, freeze once, launch all three ballot calls concurrently, record only completion status until all ballots finish, then reuse the existing reducer and condition deduplication.

- [ ] **Step 10: Run the complete backend suite**

```bash
cd backend
.venv/bin/pytest -q
```

Expected: all backend tests pass; no test asserts a fixed repeating core order or reaction round.

- [ ] **Step 11: Commit the reactive coordinator**

```bash
git add backend/src/magi/coordinator.py backend/src/magi/deliberation.py backend/src/magi/prompts.py backend/tests/test_coordinator.py backend/tests/test_deliberation.py backend/tests/test_deepseek.py
git commit -m "feat: add reactive MAGI deliberation workers"
```

---

### Task 5: Drive frontend core activity from backend status events

**Files:**
- Modify: `backend/src/magi/coordinator.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/events.js`
- Modify: `frontend/src/events.test.js`
- Modify: `frontend/src/session.js`
- Modify: `frontend/src/session.test.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/MagiCoreArray.jsx`
- Modify: `frontend/src/magiVisualState.js`
- Modify: `frontend/src/magiVisualState.test.js`
- Modify: `frontend/src/MagiComponents.test.js`
- Modify: `frontend/scripts/mock-discussion-server.mjs`

**Interfaces:**
- Consumes: strict `core_status` and causal `act` events.
- Produces: pure `applyStreamEvent(session, event) -> session` in `frontend/src/session.js`.
- Produces: `session.coreStatuses` keyed by exact core ID and `session.speakingCore` for presentation.
- Removes: the one-second delay from network parsing; incoming NDJSON must continue being parsed without artificial backpressure.

- [ ] **Step 1: Write failing frontend reducer tests**

Add literal event sequences proving:

```javascript
let session = createSession(1000);
session = applyStreamEvent(session, {
  type: "core_status",
  core: "CASPER-3",
  status: "THINKING",
  reviewed_through_event_id: 3,
});

assert.equal(session.coreStatuses["CASPER-3"].status, "THINKING");
assert.equal(session.coreStatuses["CASPER-3"].reviewedThroughEventId, 3);
```

Also assert an `act` temporarily selects its owning core for presentation without delaying parsing of the following event, and `result` atomically clears speaking state and reveals ballots.

- [ ] **Step 2: Run reducer tests and confirm the missing export**

```bash
cd frontend
node --test src/session.test.js
```

Expected: failure because `applyStreamEvent` is not exported.

- [ ] **Step 3: Move stream transitions out of `App.jsx`**

Implement `applyStreamEvent` as the sole pure session transition function. `App.jsx` retains fetching, cancellation, elapsed-time updates, modal selection, and a small presentation timer, but does not interpret status or result payloads itself.

- [ ] **Step 4: Remove artificial network backpressure**

Delete the awaited `SPEAKER_CUE_MS` pause from `processLine`. Append every event immediately. Use an effect or presentation queue driven only by committed `act` events so the visual one-second speaker cue cannot delay parsing, cancellation, ballot reveal, or subsequent core statuses.

- [ ] **Step 5: Map backend facts to visual states**

- `THINKING`: dark core with an analyzing label or restrained activity treatment.
- `SPEAKING`: cyan illuminated core while its committed act is presented.
- `LISTENING`: dark cyan-text core.
- `READY`: stable ready state without implying agreement.
- `BUDGET_EXHAUSTED`: stable bounded state.
- `FAILED`: existing error treatment.
- Revealed ballot: existing agree, conditional, or disagree treatment overrides discussion status.

Do not reintroduce random or synchronized flicker.

- [ ] **Step 6: Update the deterministic mock stream**

Interleave `core_status` and `act` events in a causal order that is not `MELCHIOR → BALTHASAR → CASPER`. Keep ballot values concealed until the final result.

- [ ] **Step 7: Run frontend, API, and build verification**

```bash
cd backend
.venv/bin/pytest tests/test_api.py -q
cd ../frontend
npm test
npm run build
```

Expected: all tests and the production build pass.

- [ ] **Step 8: Commit backend-driven activity states**

```bash
git add backend/src/magi/coordinator.py backend/tests/test_api.py frontend/src/events.js frontend/src/events.test.js frontend/src/session.js frontend/src/session.test.js frontend/src/App.jsx frontend/src/MagiCoreArray.jsx frontend/src/magiVisualState.js frontend/src/magiVisualState.test.js frontend/src/MagiComponents.test.js frontend/scripts/mock-discussion-server.mjs
git commit -m "feat: stream reactive MAGI core activity"
```

---

### Task 6: Verify the complete reactive experience and retire batch assumptions

**Files:**
- Modify: `backend/tests/test_deliberation.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/scripts/mock-discussion-server.test.js`
- Modify: `frontend/src/events.test.js`
- Modify: `frontend/src/session.test.js`
- Modify: `docs/superpowers/plans/2026-08-18-magi-sim-lean-mvp.md`
- Modify: `docs/initial-planning.md`

**Interfaces:**
- Consumes: the complete reactive coordinator and frontend reducer.
- Produces: one deterministic acceptance scenario and an updated project-status record.

- [ ] **Step 1: Encode the acceptance scenario**

The scripted sequence must prove:

```text
three independent openings
CASPER challenges MELCHIOR
MELCHIOR responds to CASPER
BALTHASAR proposes a condition after seeing both
CASPER reviews the condition and remains dissenting or concedes
all three become ready without forced agreement
ballots lock privately
one atomic mixed-result reveal
```

Assert the committed core order differs from the former repeating batch order.

- [ ] **Step 2: Verify privacy and causal integrity**

Across backend JSON, frontend parsed state, dialog models, console output fixtures, and error text, assert that API keys, `reasoning_content`, private ballots before reveal, future-event replies, and unvalidated provider content never appear.

- [ ] **Step 3: Run the entire project verification matrix**

```bash
cd backend
.venv/bin/pytest -q
cd ../frontend
npm test
npm run build
cd ..
git diff --check
```

Expected: every command exits zero. Remove generated `frontend/dist/` and Python test caches created by this verification before checking status.

- [ ] **Step 4: Perform browser verification with the deterministic mock API**

Verify at desktop and 390 px widths:

- no blank page, Vite overlay, console error, or horizontal document overflow;
- opening statuses appear before discussion;
- core illumination follows committed act order;
- multiple cores may be thinking, but only the presented speaker is illuminated;
- ready does not use an approval color;
- ballots remain concealed until reveal;
- final mixed ballot colors and modal content are correct;
- reduced-motion mode remains stable.

- [ ] **Step 5: Update planning status without changing ignore rules**

In the lean MVP plan, mark the round-based coordinator as superseded by the reactive upgrade. In `initial-planning.md`, record that Phase 2 live deliberation is implemented while SSE replay, persistent sessions, user interjections, and distributed workers remain deferred. Do not modify `.gitignore`.

- [ ] **Step 6: Commit final verification and status documentation**

```bash
git add backend/tests/test_deliberation.py backend/tests/test_api.py frontend/scripts/mock-discussion-server.test.js frontend/src/events.test.js frontend/src/session.test.js
git add -f docs/superpowers/plans/2026-08-18-magi-sim-lean-mvp.md docs/superpowers/plans/2026-08-19-reactive-deliberation-upgrade.md docs/initial-planning.md
git commit -m "test: verify reactive MAGI deliberation"
```

---

## Completion Criteria

- [ ] Openings are concurrent and independent, with a hard reaction gate until all three finish.
- [ ] Public acts commit in provider completion order rather than a fixed core cycle.
- [ ] Each core has one inbox, one worker, and at most one provider call in flight.
- [ ] Every response is causally tied to the transcript version it reviewed.
- [ ] Events arriving during generation remain unread for the next evaluation.
- [ ] `PASS` and `READY` consume bounded evaluations without entering the public transcript.
- [ ] Contribution, evaluation, token, timeout, cancellation, and failure paths terminate deterministically.
- [ ] Natural closure requires readiness, latest-version review, empty inboxes, and no in-flight work.
- [ ] Every ballot sees the same frozen transcript and remains private until atomic reveal.
- [ ] Backend status events drive frontend thinking, listening, speaking, and ready states.
- [ ] The frontend parser never sleeps to control presentation timing.
- [ ] The deterministic acceptance scenario proves a non-cyclic causal discussion.
- [ ] Backend tests, frontend tests, Vite build, browser checks, and `git diff --check` pass.

## Deferred After This Plan

- Replayable SSE sessions and reconnection
- Durable session storage and public replay URLs
- Quick and Extended mode controls in the UI
- User interjections during an active discussion
- Evidence retrieval and citations
- Multiple model providers
- Ireul and compromised-core simulations
- Distributed workers or an external message broker
