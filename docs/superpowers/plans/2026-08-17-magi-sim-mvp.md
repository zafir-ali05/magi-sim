# S.C. MAGI MVP Implementation Plan

> **Status:** Long-term plan. Start with the [lean MVP implementation plan](2026-08-18-magi-sim-lean-mvp.md); return here only when real use justifies the additional reliability, modes, packaging, and test infrastructure.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable web application where three AI cores conduct a bounded, genuinely reactive live discussion and reveal independent MAGI-style ballots.

**Architecture:** A FastAPI coordinator owns an in-memory session state machine, append-only transcript, per-core inboxes, budgets, and deterministic quorum reduction. A React/Vite client starts sessions and consumes an SSE event stream; peers react only to completed semantic messages while presentation deltas are display-only. The production adapter uses DeepSeek V4 Flash through its OpenAI-compatible Chat Completions API behind a provider protocol, while deterministic scripted clients make tests and local UI work independent of paid inference.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, `asyncio`, OpenAI Python SDK configured for DeepSeek's compatible API, DeepSeek V4 Flash, pytest, React, JavaScript, Vite, Tailwind CSS, shadcn/ui with Radix primitives, Motion for React, Vitest, React Testing Library, Playwright, Docker.

**Spec:** [`initial-planning.md`](../../initial-planning.md)

## Global Constraints

- The product is decision support and entertainment; it never executes an external action.
- The canonical core IDs are exactly `MELCHIOR-1`, `BALTHASAR-2`, and `CASPER-3`.
- Quick, Standard, and Extended allow at most 1, 3, and 4 reactive contributions per core respectively.
- Quick, Standard, and Extended use wall-clock limits of 120, 240, and 360 seconds and whole-session completion-token ceilings of 32,000, 80,000, and 96,000 respectively, including private reasoning tokens reported by the provider.
- Opening and reaction calls use `deepseek-v4-flash` with `reasoning_effort="high"` and `max_tokens=4096`; ballot calls use the same model with `reasoning_effort="max"` and `max_tokens=8192`.
- Contribution limits are ceilings, not quotas; `PASS` and early readiness are valid.
- Peers consume only committed messages, never partial output tokens or hidden chain-of-thought.
- All final ballots use one frozen transcript version and remain private until simultaneous reveal.
- Disagreement is a valid completed result; readiness to vote does not mean consensus.
- Ordinary motions may use majority; consequential motions default to human confirmation.
- A failed core never silently becomes a negative vote or disappears from the result.
- API keys remain server-side and must never enter frontend bundles, logs, fixtures, commits, or documentation examples.
- DeepSeek `reasoning_content` is private implementation data: discard it after usage accounting and never log, persist, stream, or place it in peer context.
- The public UI uses original visual assets rather than copied NERV logos, screenshots, character art, fonts, or music.
- Color never communicates state alone; keyboard operation, readable labels, reduced motion, and mute controls are required.

---

## 1. Repository and file map

```text
magi-sim/
├── backend/
│   ├── pyproject.toml
│   ├── src/magi/
│   │   ├── config.py                 # environment-backed settings
│   │   ├── domain/models.py          # shared Pydantic contracts and enums
│   │   ├── domain/policy.py          # deterministic quorum reduction
│   │   ├── agents/protocol.py        # model-client interface
│   │   ├── agents/prompts.py         # canonical facets and prompt construction
│   │   ├── agents/scripted.py        # deterministic development/test client
│   │   ├── agents/deepseek.py        # DeepSeek thinking and JSON-output adapter
│   │   ├── orchestration/transcript.py
│   │   ├── orchestration/budgets.py
│   │   ├── orchestration/session.py  # session aggregate and completion predicate
│   │   ├── orchestration/coordinator.py
│   │   ├── storage/sessions.py       # in-memory repository and event replay
│   │   ├── api/routes.py
│   │   ├── api/sse.py
│   │   └── main.py
│   └── tests/
│       ├── domain/
│       ├── agents/
│       ├── orchestration/
│       └── api/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── components.json
│   ├── src/
│   │   ├── api/client.js
│   │   ├── protocol/events.js
│   │   ├── protocol/schemas.js
│   │   ├── state/session-reducer.js
│   │   ├── components/MotionForm.jsx
│   │   ├── components/CorePanel.jsx
│   │   ├── components/DiagnosticTrace.jsx
│   │   ├── components/BallotReveal.jsx
│   │   ├── components/ResultSummary.jsx
│   │   ├── components/SessionControls.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   └── tests/
│       ├── session-reducer.test.js
│       └── app.test.jsx
├── e2e/
│   ├── playwright.config.js
│   └── magi-session.spec.js
├── .env.example
├── .gitignore
├── Dockerfile
├── compose.yaml
└── README.md
```

`domain` contains pure contracts and reduction rules. `agents` turns a frozen input into structured acts or ballots. `orchestration` owns concurrency and state transitions. `storage` owns lifecycle and replay. `api` translates HTTP/SSE without containing decision logic. The frontend mirrors the public protocol but never imports backend implementation details.

---

### Task 1: Scaffold both runtimes and define the public contracts

**Files:**
- Create: `.gitignore`, `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/src/magi/domain/models.py`
- Create: `backend/tests/domain/test_models.py`
- Create: `frontend/package.json`, `frontend/vite.config.js`
- Create: `frontend/src/protocol/events.js`, `frontend/src/protocol/schemas.js`

**Interfaces:**
- Produces: `Motion`, `DiscussionDepth`, `DiscussionEvent`, `AgentAct`, `Ballot`, `SessionResult`, `StreamEnvelope`.
- Produces: an identical JavaScript event catalog plus Zod runtime validation for public events.

- [ ] **Step 1: Create the Python package and tool configuration**

Configure `backend/pyproject.toml` with runtime dependencies `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, and `openai` (used as the client for DeepSeek's OpenAI-compatible endpoint); development dependencies `pytest`, `pytest-asyncio`, `httpx`, `ruff`, and `mypy`. Set Python to `>=3.12`, pytest asyncio mode to `auto`, Ruff line length to 100, and package discovery under `src`.

- [ ] **Step 2: Write failing contract tests**

```python
def test_high_stakes_motion_requires_human_confirmation():
    motion = Motion(question="Delete the production database", stakes="high")
    assert motion.quorum == Quorum.HUMAN_CONFIRM

def test_discussion_depth_limits():
    assert DiscussionDepth.QUICK.reaction_limit == 1
    assert DiscussionDepth.STANDARD.reaction_limit == 3
    assert DiscussionDepth.EXTENDED.reaction_limit == 4
```

Run: `cd backend && pytest tests/domain/test_models.py -q`

Expected: FAIL because the contracts do not exist.

- [ ] **Step 3: Implement strict domain contracts**

Use string enums for core IDs, depth, stakes, quorum, event kind, vote, session phase, and terminal result. Set `extra="forbid"` on public Pydantic models. Enforce question length `1..4000`, message content `1..1200`, confidence `0..1`, and immutable positive event sequence numbers. Model `reply_to` as `int | None`, conditions and risks as bounded lists, and timestamps as UTC datetimes. Define `EvidenceItem` with `id`, `label`, `content`, and `source_type="user_supplied"`; retrieval and URL fetching are outside this MVP.

- [ ] **Step 4: Mirror and runtime-validate the protocol in JavaScript**

Export frozen event-name constants from `events.js` and use a Zod discriminated union in `schemas.js`. `StreamEnvelope` must discriminate at least:

```js
export const STREAM_EVENT_TYPES = Object.freeze([
  "session.started",
  "core.status",
  "message.delta",
  "message.committed",
  "core.ready",
  "transcript.frozen",
  "ballot.committed",
  "ballots.revealed",
  "session.completed",
  "session.failed",
  "session.cancelled",
  "heartbeat",
]);
```

- [ ] **Step 5: Run contract checks**

Run: `cd backend && pytest tests/domain/test_models.py -q && ruff check src tests && mypy src`

Run: `cd frontend && npm test -- --run`

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example backend frontend
git commit -m "build: scaffold MAGI application contracts"
```

---

### Task 2: Implement transcript integrity, budgets, and quorum reduction

**Files:**
- Create: `backend/src/magi/orchestration/transcript.py`
- Create: `backend/src/magi/orchestration/budgets.py`
- Create: `backend/src/magi/domain/policy.py`
- Create: `backend/tests/orchestration/test_transcript.py`
- Create: `backend/tests/orchestration/test_budgets.py`
- Create: `backend/tests/domain/test_policy.py`

**Interfaces:**
- Produces: `Transcript.append(act) -> DiscussionEvent`, `Transcript.freeze() -> FrozenTranscript`.
- Produces: `BudgetLedger.can_contribute(core_id)`, `record_contribution(core_id)`, and `expired(now)`.
- Produces: `reduce_ballots(motion, ballots) -> SessionResult`.

- [ ] **Step 1: Test ordered append and immutable freeze**

Verify sequences start at 1, remain contiguous under concurrent append, reject invalid `reply_to` values, and raise `TranscriptFrozenError` after freeze. Verify a frozen snapshot preserves the exact sequence and message list used by ballots.

- [ ] **Step 2: Implement transcript mutation behind one `asyncio.Lock`**

Only committed `AgentAct` values become peer-visible transcript events. `message.delta` remains a transport-only UI event and never enters `Transcript`.

- [ ] **Step 3: Test budgets as ceilings**

Test Quick/Standard/Extended limits of 1/3/4 per core, independent per-core counts, total wall-clock expiry, and that `PASS`/`READY` do not consume contribution slots.

- [ ] **Step 4: Implement `BudgetLedger` using monotonic time**

Inject the clock into tests. Store `started_at`, `deadline`, depth, per-core contribution counts, provider-reported output-token usage, and a cancellation event. Enforce the exact time/token ceilings in Global Constraints. Never compare wall-clock timestamps to determine runtime expiry.

- [ ] **Step 5: Test quorum truth tables**

Cover all 27 three-ballot combinations. Required examples:

```python
assert reduce_ballots(majority_motion, [A, A, D]).status == "APPROVED"
assert reduce_ballots(majority_motion, [A, C, D]).status == "APPROVED_WITH_CONDITIONS"
assert reduce_ballots(unanimous_motion, [A, A, D]).status == "REJECTED"
assert reduce_ballots(human_motion, [A, A, A]).status == "HUMAN_CONFIRMATION_REQUIRED"
```

Define `CONDITIONAL` as affirmative only when all returned conditions remain attached to the result. Any invalid/missing ballot yields `INCOMPLETE`, not rejection.

- [ ] **Step 6: Run and commit**

Run: `cd backend && pytest tests/domain tests/orchestration/test_transcript.py tests/orchestration/test_budgets.py -q`

```bash
git add backend/src/magi/domain backend/src/magi/orchestration backend/tests
git commit -m "feat: add transcript budgets and quorum policy"
```

---

### Task 3: Define core prompts and a deterministic model-client protocol

**Files:**
- Create: `backend/src/magi/agents/protocol.py`
- Create: `backend/src/magi/agents/prompts.py`
- Create: `backend/src/magi/agents/scripted.py`
- Create: `backend/tests/agents/test_prompts.py`
- Create: `backend/tests/agents/test_scripted.py`

**Interfaces:**
- Produces: `ModelClient.opening`, `ModelClient.react`, and `ModelClient.ballot` async methods.
- Produces: `build_opening_input`, `build_reaction_input`, and `build_ballot_input` pure functions.

- [ ] **Step 1: Write prompt boundary tests**

Assert every prompt includes the motion, core facet, project lens, response schema, word limit, instruction not to reveal hidden reasoning, and instruction not to invent evidence. Reaction prompts include the frozen transcript snapshot and remaining contribution count. Ballot prompts include the transcript version.

- [ ] **Step 2: Define the provider protocol**

```python
class ModelClient(Protocol):
    async def opening(self, core: CoreId, motion: Motion) -> AgentAct: ...
    async def react(
        self, core: CoreId, motion: Motion, transcript: FrozenTranscript,
        remaining: int,
    ) -> AgentAct: ...
    async def ballot(
        self, core: CoreId, motion: Motion, transcript: FrozenTranscript,
    ) -> Ballot: ...
```

`AgentAct.kind` allows `POSITION`, `CHALLENGE`, `RESPONSE`, `CONCEDE`, `PROPOSE_CONDITION`, `CLARIFY`, `READY`, and `PASS`. A non-pass reaction must identify `reply_to` and contain at least one concise claim.

- [ ] **Step 3: Write the three system identities**

Keep the canonical labels and operational lenses from the spec. Shared rules require public statements under 120 words, direct references to disputed claims, explicit concessions, no theatrical roleplay filler, no false citations, and readiness without forced agreement.

- [ ] **Step 4: Implement `ScriptedModelClient`**

The fake client takes per-core queues of acts and ballots, optionally emits deterministic deltas, records every call, and raises configured errors. It is the default for tests, Playwright, and UI development without an API key.

- [ ] **Step 5: Run and commit**

Run: `cd backend && pytest tests/agents -q && ruff check src tests && mypy src`

```bash
git add backend/src/magi/agents backend/tests/agents
git commit -m "feat: define MAGI core prompts and model protocol"
```

---

### Task 4: Implement the session aggregate and completion predicate

**Files:**
- Create: `backend/src/magi/orchestration/session.py`
- Create: `backend/tests/orchestration/test_session.py`

**Interfaces:**
- Produces: `MagiSession.apply(event)`, `mark_ready(core, sequence)`, `can_complete()`.
- Produces: monotonic phase transitions from `CREATED` through one terminal state.

- [ ] **Step 1: Test allowed and forbidden transitions**

Allowed path: `CREATED → OPENING → DISCUSSING → BALLOTING → REVEALING → COMPLETED`. `FAILED` and `CANCELLED` may be entered from any non-terminal phase. Reject backward transitions and events after a terminal state.

- [ ] **Step 2: Test readiness without consensus**

Track `reviewed_through_sequence` per core. Completion is allowed only when all cores have reviewed the latest committed sequence, no generation is in flight, inboxes are empty, and all cores returned `READY` or exhausted the global discussion budget. Votes are irrelevant to this predicate.

- [ ] **Step 3: Implement session invariants**

Keep all mutation in the aggregate. Include per-core statuses, committed event buffer, private ballot map, current phase, failure details safe for clients, and a cancellation event.

- [ ] **Step 4: Run and commit**

Run: `cd backend && pytest tests/orchestration/test_session.py -q`

```bash
git add backend/src/magi/orchestration/session.py backend/tests/orchestration/test_session.py
git commit -m "feat: add MAGI session state machine"
```

---

### Task 5: Build the reactive coordinator

**Files:**
- Create: `backend/src/magi/orchestration/coordinator.py`
- Create: `backend/tests/orchestration/test_coordinator.py`

**Interfaces:**
- Consumes: `ModelClient`, `Transcript`, `BudgetLedger`, `MagiSession`.
- Produces: `MagiCoordinator.run(session) -> SessionResult` and `cancel(session_id)`.

- [ ] **Step 1: Write the parallel-opening test**

Use barriers in the fake client to prove all three opening calls begin before any is released. Assert openings are committed in completion order, assigned unique sequences, and broadcast only after completion.

- [ ] **Step 2: Write the reactive-causality test**

Configure CASPER to challenge MELCHIOR event 1 and BALTHASAR to propose a condition in response. Assert every emitted `reply_to` references an existing earlier event and every reaction call receives the latest immutable transcript snapshot available when scheduled.

- [ ] **Step 3: Implement worker scheduling**

Create one scoped task per core and one inbox per core. After an opening commits, broadcast its sequence to peers. Workers coalesce currently pending notifications, snapshot the transcript, and make at most one reaction call for that snapshot. A committed reaction wakes peers; `PASS` or `READY` updates review progress without adding a transcript message.

- [ ] **Step 4: Implement stable completion and forced ballot**

Finish naturally when all cores have reviewed the latest sequence, all are ready, and no work is pending. When wall-clock or total contribution budget expires, cancel discussion calls, freeze the transcript, and proceed to ballots. A provider error retries once; a second failure marks the session `FAILED` and cancels sibling tasks.

- [ ] **Step 5: Implement fair private ballots**

Freeze once, call all three ballots concurrently with that same `FrozenTranscript`, store each privately, emit only `ballot.committed` with core ID and no vote, then emit one `ballots.revealed` containing all ballots. Reduce the result afterward.

- [ ] **Step 6: Test termination paths**

Cover early readiness, Quick/Standard/Extended ceilings, repetitive `PASS`, timeout, cancellation, one retry success, permanent core failure, and a 2–1 completed disagreement.

- [ ] **Step 7: Run and commit**

Run: `cd backend && pytest tests/orchestration -q`

```bash
git add backend/src/magi/orchestration/coordinator.py backend/tests/orchestration/test_coordinator.py
git commit -m "feat: orchestrate bounded live MAGI discussion"
```

---

### Task 6: Add the DeepSeek V4 Flash adapter

**Files:**
- Create: `backend/src/magi/config.py`
- Create: `backend/src/magi/agents/deepseek.py`
- Create: `backend/tests/agents/test_deepseek.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `DeepSeekModelClient(ModelSettings)` implementing `ModelClient`.
- Consumes: `MAGI_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, reasoning efforts, timeouts, and output-token limits from server settings.

- [ ] **Step 1: Test request construction without network calls**

Mock the SDK transport and assert opening and reaction calls use `deepseek-v4-flash`, thinking enabled, `reasoning_effort="high"`, `max_tokens=4096`, and JSON Output. Assert ballot calls instead use `reasoning_effort="max"` and `max_tokens=8192`. Do not send `temperature`, `top_p`, `presence_penalty`, or `frequency_penalty` because DeepSeek ignores them in thinking mode. Assert the API key and `reasoning_content` never appear in emitted events or exception text.

Set `.env.example` deliberately to:

```dotenv
MAGI_PROVIDER=scripted
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_DISCUSSION_EFFORT=high
DEEPSEEK_BALLOT_EFFORT=max
DEEPSEEK_API_KEY=
```

`scripted` is the safe local default. Selecting `MAGI_PROVIDER=deepseek` with an empty API key, a model other than `deepseek-v4-flash`, discussion effort other than `high`, or ballot effort other than `max` must fail at startup with a configuration error. Keep these values in environment settings as well as defaults so a future provider experiment does not require orchestration changes.

- [ ] **Step 2: Implement thinking-mode JSON calls**

Construct `AsyncOpenAI(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com")` and call `client.chat.completions.create` with the configured model, messages, `reasoning_effort`, `extra_body={"thinking": {"type": "enabled"}}`, `response_format={"type": "json_object"}`, and the operation-specific `max_tokens`. Prompts must contain the word “JSON,” the exact desired object example, and schema rules. DeepSeek guarantees valid JSON rather than exact schema conformance, so parse `message.content` through the relevant Pydantic model and retry once on empty content, truncation, or validation failure. Do not use provider-managed conversation state; every request receives the explicit current motion and transcript.

- [ ] **Step 3: Implement validated transmission chunks**

For opening and reaction messages, buffer the provider result and validate it first. Record only aggregate usage counts, including `completion_tokens_details.reasoning_tokens`, then discard `message.reasoning_content`. Split only the validated public `content` field into short presentation chunks and emit temporary `message.delta` envelopes for the owning core panel before committing the semantic transcript event. Never forward partial JSON, schema fields, reasoning content, or raw provider events. Ballots may show processing status but must not stream vote content before reveal.

- [ ] **Step 4: Add privacy and error mapping**

Map provider timeout, rate-limit, empty JSON content, `finish_reason="length"`, invalid schema, refusal, and cancellation into internal typed errors. User-facing errors disclose category and retryability but never raw prompts, credentials, reasoning content, or provider response bodies.

- [ ] **Step 5: Run and commit**

Run: `cd backend && pytest tests/agents/test_deepseek.py -q && ruff check src tests && mypy src`

```bash
git add .env.example backend/src/magi/config.py backend/src/magi/agents/deepseek.py backend/tests/agents/test_deepseek.py
git commit -m "feat: add DeepSeek V4 Flash model adapter"
```

---

### Task 7: Expose session control and replayable SSE

**Files:**
- Create: `backend/src/magi/storage/sessions.py`
- Create: `backend/src/magi/api/sse.py`
- Create: `backend/src/magi/api/routes.py`
- Create: `backend/src/magi/main.py`
- Create: `backend/tests/api/test_sessions.py`
- Create: `backend/tests/api/test_sse.py`

**Interfaces:**
- Produces: `POST /api/v1/sessions`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/{id}/events`, `POST /api/v1/sessions/{id}/cancel`, `GET /healthz`.

- [ ] **Step 1: Write API contract tests**

Assert session creation returns `202` with opaque UUID, phase, snapshot URL, and stream URL. Invalid motions return RFC 9457-style problem details. Unknown sessions return `404`. Cancelling a terminal session is idempotent.

- [ ] **Step 2: Implement the in-memory repository**

Store active sessions, coordinator tasks, and a bounded public envelope buffer. Protect repository mutation with a lock. Remove completed sessions after a configurable TTL; never remove an active session.

- [ ] **Step 3: Implement SSE framing and replay**

Emit `id`, `event`, and JSON `data` lines, followed by a blank line. Honor `Last-Event-ID` by replaying buffered envelopes after that sequence. Emit a comment heartbeat every 15 seconds. Set `Cache-Control: no-cache` and disable proxy buffering where supported.

- [ ] **Step 4: Wire application lifespan**

Construct settings, repository, chosen model client, and coordinator once. On shutdown, cancel active sessions and await tasks. In development, allow only the configured Vite origin; production is same-origin.

- [ ] **Step 5: Run and commit**

Run: `cd backend && pytest tests/api -q`

```bash
git add backend/src/magi/storage backend/src/magi/api backend/src/magi/main.py backend/tests/api
git commit -m "feat: expose MAGI session and SSE API"
```

---

### Task 8: Scaffold the React visual system and session reducer

**Files:**
- Modify: `frontend/package.json`, `frontend/vite.config.js`
- Create: `frontend/components.json`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/state/session-reducer.js`
- Create: `frontend/tests/session-reducer.test.js`

**Interfaces:**
- Produces: `reduceSession(state, envelope) -> SessionViewState`.
- Produces: Tailwind tokens and reusable state styles for all core/terminal states.

- [ ] **Step 1: Install the selected UI dependencies**

Use React, Tailwind's Vite plugin, Zod, Motion, Lucide React, and selected shadcn components backed by Radix: Button, Textarea, Select, Tooltip, Dialog, ScrollArea, Badge, Progress, and Switch. Add Vitest and React Testing Library development dependencies.

- [ ] **Step 2: Write reducer tests before UI components**

Test sequence deduplication, out-of-order rejection, per-core delta buffering, replacement by committed messages, readiness changes, private ballot placeholders, atomic ballot reveal, completion, failure, cancellation, and reconnect replay.

- [ ] **Step 3: Implement the reducer as the sole SSE state transition layer**

Keep server envelope history separate from derived UI state. Never reveal ballot data on `ballot.committed`. Invalid Zod payloads move the connection into a protocol-error state and retain the last valid view.

- [ ] **Step 4: Establish visual tokens**

Define semantic CSS variables for background, surface, grid, amber activity, green approval, red denial, conditional warning, text, muted text, focus ring, and core-specific accents. Add `prefers-reduced-motion` behavior and avoid encoding votes by color alone.

- [ ] **Step 5: Run and commit**

Run: `cd frontend && npm test -- --run && npm run build`

```bash
git add frontend
git commit -m "feat: add MAGI frontend protocol and visual tokens"
```

---

### Task 9: Build session creation and resilient streaming

**Files:**
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/components/MotionForm.jsx`
- Create: `frontend/src/components/SessionControls.jsx`
- Create: `frontend/tests/api-client.test.js`
- Create: `frontend/tests/motion-form.test.jsx`

**Interfaces:**
- Produces: `createSession(motion)`, `getSession(id)`, `cancelSession(id)`, and `subscribeToSession(id, handlers)`.

- [ ] **Step 1: Test form semantics**

Verify labels, keyboard submission, question validation, optional context and user-supplied evidence entry, depth choices, stakes-to-quorum defaulting, disabled submission while creating, and readable API errors. Standard is the initial depth; high stakes visibly forces human confirmation.

- [ ] **Step 2: Implement API calls and EventSource lifecycle**

POST the motion, open the returned SSE URL, validate every envelope, and close the stream on terminal events or component unmount. On reconnect, first fetch the session snapshot and then allow EventSource replay to fill missing sequences.

- [ ] **Step 3: Add cancellation and connection states**

Provide Cancel during active sessions, Retry for retryable creation failures, and Reconnect for interrupted streams. Do not clear an existing transcript during reconnection.

- [ ] **Step 4: Run and commit**

Run: `cd frontend && npm test -- --run tests/api-client.test.js tests/motion-form.test.jsx`

```bash
git add frontend/src/api frontend/src/components/MotionForm.jsx frontend/src/components/SessionControls.jsx frontend/tests
git commit -m "feat: create and stream MAGI sessions"
```

---

### Task 10: Build the live tri-core discussion interface

**Files:**
- Create: `frontend/src/components/CorePanel.jsx`
- Create: `frontend/src/components/DiagnosticTrace.jsx`
- Create: `frontend/src/components/BallotReveal.jsx`
- Create: `frontend/src/components/ResultSummary.jsx`
- Create: `frontend/src/App.jsx`, `frontend/src/main.jsx`
- Create: `frontend/tests/app.test.jsx`

**Interfaces:**
- Consumes: `SessionViewState` only; components do not parse raw SSE.
- Produces: complete responsive MAGI session experience.

- [ ] **Step 1: Test the information hierarchy**

Assert the active motion and phase appear first, followed by three labeled cores, diagnostic trace, controls, and final result. Verify streaming deltas are visually marked as uncommitted, committed messages identify act type and reply target, and screen-reader live regions announce important state changes without reading every token.

- [ ] **Step 2: Build responsive core panels**

Use three panels in a triangle-inspired desktop composition and a single-column mobile sequence. Each shows canonical facet, project lens, status, remaining reactions, latest transmission, readiness, and error state. Keep primary content readable without hover.

- [ ] **Step 3: Build the diagnostic trace**

Render committed events in causal order with reply links, act labels, timestamps, and core identity. Clearly mark evidence as user-supplied rather than model-verified. Virtualization is unnecessary for the bounded MVP message count. Provide a maintenance toggle for event IDs, transcript version, and budgets.

- [ ] **Step 4: Build synchronized private lock-in**

During `BALLOTING`, show only per-core committed indicators. On `ballots.revealed`, animate all three ballot surfaces from concealed to visible in one shared Motion transition. Reduced-motion mode performs an immediate state change. Never stagger the vote reveal.

- [ ] **Step 5: Build result semantics**

Show outcome, quorum, all individual votes, merged conditions without duplicates, blocking risks, human-confirmation requirement, and disclaimer. A 2–1 result keeps dissent visible; `INCOMPLETE`, `FAILED`, and `CANCELLED` each have distinct recovery copy.

- [ ] **Step 6: Add restrained sound and motion controls**

Generate short original interface tones with the Web Audio API for message commit and ballot reveal; do not ship copyrighted audio. Sound defaults off until the user enables it. Persist mute preference locally. Respect `prefers-reduced-motion` and expose an explicit reduced-motion toggle alongside mute.

- [ ] **Step 7: Run and commit**

Run: `cd frontend && npm test -- --run && npm run build`

```bash
git add frontend/src frontend/tests
git commit -m "feat: build live MAGI deliberation dashboard"
```

---

### Task 11: Verify the complete experience in a browser

**Files:**
- Create: `e2e/package.json`, `e2e/playwright.config.js`, `e2e/magi-session.spec.js`
- Modify: backend test-mode scripted scenario configuration

**Interfaces:**
- Consumes: production-like frontend and FastAPI processes with scripted inference.
- Produces: repeatable cross-browser acceptance suite.

- [ ] **Step 1: Create a deterministic scripted scenario**

The scenario must produce three independent openings, a CASPER challenge, a BALTHASAR condition, a MELCHIOR concession, early readiness, a 2–1 conditional result, and simultaneous ballot reveal. Give each scripted call a small delay so streaming states are observable without making tests slow.

- [ ] **Step 2: Test the happy path**

Playwright submits a Standard motion, observes all three opening states, verifies causal reactions, checks that votes remain concealed while ballots commit, and confirms the final result preserves the dissenting ballot and condition.

- [ ] **Step 3: Test operational paths**

Cover cancellation, provider failure, reconnect/replay, Quick mode ceiling, Extended mode display, high-stakes human confirmation, mobile viewport, keyboard-only submission, and reduced-motion ballot reveal.

- [ ] **Step 4: Run browser matrix**

Run Chromium on every change. Run Chromium, Firefox, and WebKit in CI before release.

Run: `cd e2e && npx playwright test --project=chromium`

Expected: all scenarios pass with no console errors, failed network requests, or accessibility-name failures.

- [ ] **Step 5: Commit**

```bash
git add e2e backend
git commit -m "test: cover complete MAGI deliberation flow"
```

---

### Task 12: Package, document, and release the MVP

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `README.md`
- Modify: `backend/src/magi/main.py`, `.env.example`, `.gitignore`

**Interfaces:**
- Produces: one production container serving the API and compiled frontend on the same origin.

- [ ] **Step 1: Create a multi-stage container**

Build the Vite frontend in a Node stage, install the Python package into a slim Python 3.12 stage, copy `frontend/dist` into the backend static directory, run as a non-root user, and start Uvicorn with one worker for the in-memory MVP. Add a health check against `/healthz`.

- [ ] **Step 2: Serve the SPA safely**

Mount hashed assets with long-lived immutable caching and serve `index.html` with `no-cache`. Route `/api/*` and `/healthz` before the SPA fallback. Do not use `vite preview` as the production server.

- [ ] **Step 3: Document local and production operation**

README sections must include project purpose, lore/adaptation boundary, architecture, Quick/Standard/Extended modes, privacy and provider-retention note, prerequisites, environment variables, development commands, test commands, Docker commands, accessibility controls, and explicit non-goals.

- [ ] **Step 4: Run the complete release gate**

```bash
cd backend && pytest -q && ruff check src tests && mypy src
cd ../frontend && npm test -- --run && npm run build
cd ../e2e && npx playwright test --project=chromium
cd .. && docker compose config && docker compose build && docker compose up -d
curl --fail http://localhost:8000/healthz
docker compose down
```

Expected: all checks exit 0, the health endpoint returns HTTP 200, and shutdown removes containers without deleting source data.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile compose.yaml README.md .env.example .gitignore backend
git commit -m "docs: package and document MAGI MVP"
```

---

## 2. Release acceptance checklist

- [ ] Three openings begin concurrently and are independent.
- [ ] Completed messages, not deltas, trigger peer reactions.
- [ ] Quick/Standard/Extended enforce 1/3/4 reaction ceilings per core.
- [ ] A core may pass or become ready early without filler.
- [ ] Every challenge targets an earlier committed event.
- [ ] The discussion terminates under contribution, token, wall-clock, cancellation, and provider-failure conditions.
- [ ] All ballots reference one frozen transcript version.
- [ ] Vote content remains hidden until atomic reveal.
- [ ] Majority, unanimity, conditional, and human-confirmation results match the policy truth table.
- [ ] Dissent and conditions remain visible in the final result.
- [ ] SSE reconnect replays missed public events without duplication.
- [ ] Secrets stay server-side and errors are sanitized.
- [ ] Keyboard, mobile, reduced-motion, mute, and non-color state communication work.
- [ ] The scripted experience runs without an external model account.
- [ ] The production container serves both the SPA and API and passes its health check.

## 3. Explicit post-MVP scope

The following require separate designs after the MVP is measured: persistent session history and accounts, user interjections during a running discussion, evidence retrieval and citations, multiple model providers, custom persona editing, shareable public replays, Ireul compromised-core simulation, protection-666 sequences, Redis or distributed workers, and any external action integration.

## 4. Reference documentation

- [Vite guide](https://vite.dev/guide/)
- [Tailwind CSS Vite installation](https://tailwindcss.com/docs/installation/using-vite)
- [shadcn/ui introduction](https://ui.shadcn.com/docs)
- [Radix Primitives accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility)
- [Motion for React](https://motion.dev/docs/react)
- [Vitest guide](https://vitest.dev/guide/)
- [Playwright browsers](https://playwright.dev/docs/browsers)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek thinking mode and reasoning effort](https://api-docs.deepseek.com/guides/thinking_mode)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode)
- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)
