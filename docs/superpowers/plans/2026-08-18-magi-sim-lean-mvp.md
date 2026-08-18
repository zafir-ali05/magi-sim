# S.C. MAGI Lean MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that watching three distinct MAGI cores react to one another and privately reach a decision is useful and entertaining, with the least infrastructure needed to run that experience.

**Architecture:** One FastAPI process accepts a motion and returns an NDJSON response stream. It runs three independent DeepSeek contexts through independent openings, up to three synchronized reaction rounds, and one simultaneous private-ballot round; a small React client renders those events as a live tri-core console. There is no session repository, replay protocol, provider abstraction, or distributed worker system.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, `asyncio`, OpenAI Python SDK configured for DeepSeek, pytest, React, TypeScript, Vite, Tailwind CSS, Motion for React.

**Spec:** [`initial-planning.md`](../../initial-planning.md)

## Global constraints

- The canonical cores are exactly `MELCHIOR-1`, `BALTHASAR-2`, and `CASPER-3`, using the scientist, mother, and woman facets defined in the spec.
- All cores use `deepseek-v4-flash`: openings and reactions use `reasoning_effort="high"`; ballots use `reasoning_effort="max"`.
- Each core receives an independent opening call before seeing peer output.
- Each reaction round uses the same frozen transcript snapshot for all three cores. A later round includes every committed message from earlier rounds.
- Run at most three reaction rounds. Stop early only when all three cores return `READY` in the same round.
- Final ballots use one frozen transcript, remain private until all three are complete, and reveal together.
- Votes are `AGREE`, `DISAGREE`, or `CONDITIONAL`; dissent and conditions remain visible in the result.
- The server validates every public model response. Retry one malformed, empty, truncated, or failed call once; otherwise emit an explicit failure and end the request.
- DeepSeek `reasoning_content` is discarded after aggregate usage accounting. Never log, persist, stream, display, or place it in another core's context.
- The API key remains server-side. The application never executes a real-world action.
- A complete discussion may take tens of seconds or several minutes. The UI reports the current phase and active cores instead of implying instant fictional-supercomputer speed.
- Preserve input validation, error handling, private-ballot isolation, readable labels, keyboard operation, accessible contrast, and reduced-motion behavior.

---

## What remains authentically MAGI

The lean version retains the project's defining behavior:

1. Three independent judgments come from three conflicting Naoko-inspired facets.
2. The cores see and respond to completed peer statements rather than producing three isolated answers.
3. `CHALLENGE`, `RESPONSE`, `CONCEDE`, `PROPOSE_CONDITION`, `CLARIFY`, `READY`, and `PASS` remain meaningful public acts.
4. The discussion has a hard boundary and cannot loop forever.
5. All final ballots derive from the same transcript and remain concealed until simultaneous reveal.
6. Deterministic application code—not another model—computes the final majority and preserves conditional votes and dissent.

Synchronized rounds are an implementation simplification, not scripted speaking order. All three cores analyze the same newly committed material concurrently, and later rounds remain substantively reactive.

## How this differs from the full plan

The [full plan](2026-08-17-magi-sim-mvp.md) remains the upgrade path.

| Area | Lean MVP | Full plan | Add the full version when |
| --- | --- | --- | --- |
| Discussion scheduling | Up to three synchronized reaction rounds | Per-core inboxes and event-driven scheduling | Round barriers make conversations noticeably unnatural |
| Transport | One streamed `POST /api/discuss` using NDJSON | Session endpoints plus replayable SSE | Users need reconnect, cancellation, or shareable sessions |
| Session state | Lives only for the request | Repository, snapshots, TTL, event replay | More than one browser must inspect a session |
| Modes | One fixed depth | Quick, Standard, and Extended | Usage shows a real latency/cost preference split |
| Providers | Direct DeepSeek client | Provider protocol plus scripted client | A second provider is actually being added |
| Frontend state | Local React state updated from stream events | Validated protocol reducer with replay semantics | Reconnection or multiple event sources exist |
| Components | Hand-built React, Tailwind, and Motion | shadcn/Radix component set and richer diagnostics | Repeated UI patterns justify the dependency |
| Presentation | Motion input, three core panels, transcript, ballot reveal | Maintenance mode, audio, advanced diagnostics, sharing/export | The basic interaction is already compelling |
| Testing | Coordinator tests, API stream test, frontend build | Broad unit, component, Playwright, and browser-matrix suites | The project has users or regressions the lean checks miss |
| Operations | Local development commands | Docker, health checks, production container | The application is ready to be hosted |

Deliberately deferred features are not partially scaffolded. Upgrade by implementing the relevant full-plan task when its trigger occurs.

---

## Repository map

```text
magi-sim/
├── backend/
│   ├── pyproject.toml
│   ├── src/magi/
│   │   ├── app.py             # FastAPI endpoint and NDJSON framing
│   │   ├── models.py          # validated motion, act, ballot, and stream types
│   │   ├── prompts.py         # the three identities and prompt builders
│   │   ├── deepseek.py        # direct DeepSeek request function
│   │   └── deliberation.py    # openings, reaction rounds, ballot, reduction
│   └── tests/
│       ├── test_deliberation.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── CorePanel.tsx
│       ├── types.ts
│       ├── styles.css
│       └── main.tsx
├── .env.example
├── .gitignore
└── README.md
```

Five backend modules are enough: contracts, prompts, provider call, orchestration, and HTTP. Do not create domain, storage, repository, protocol-interface, budget-ledger, or reducer layers in the lean MVP.

---

### Task 1: Create validated contracts and the direct DeepSeek client

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/magi/models.py`
- Create: `backend/src/magi/prompts.py`
- Create: `backend/src/magi/deepseek.py`
- Create: `.env.example`

**Interfaces:**
- Produces: `Motion`, `Act`, `Ballot`, `PhaseEvent`, `ActEvent`, `BallotsLockedEvent`, `ResultEvent`, `ErrorEvent`, `StreamEvent`, `CoreId`, `ActKind`, and `Vote`.
- Produces: `ask_deepseek(messages: list[dict[str, str]], schema: type[T], effort: Literal["high", "max"], max_tokens: int) -> T`.
- Produces: `opening_messages`, `reaction_messages`, and `ballot_messages` prompt builders.

- [ ] **Step 1: Configure the backend package**

Use only `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, and `openai` at runtime. Use `pytest`, `pytest-asyncio`, and `httpx` for development. Set Python to `>=3.12` and pytest asyncio mode to `auto`.

- [ ] **Step 2: Define strict public models**

Define these minimum shapes in `models.py`:

```python
CoreId = Literal["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"]
ActKind = Literal[
    "POSITION", "CHALLENGE", "RESPONSE", "CONCEDE",
    "PROPOSE_CONDITION", "CLARIFY", "READY", "PASS",
]
Vote = Literal["AGREE", "DISAGREE", "CONDITIONAL"]

class Motion(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)
    context: str = Field(default="", max_length=8_000)

class Act(BaseModel):
    core: CoreId
    kind: ActKind
    content: str = Field(min_length=1, max_length=2_000)
    reply_to: int | None = None

class Ballot(BaseModel):
    core: CoreId
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=2_000)
    conditions: list[str] = Field(default_factory=list, max_length=8)

class PhaseEvent(BaseModel):
    type: Literal["phase"] = "phase"
    phase: Literal["OPENING", "DISCUSSION", "BALLOTING"]
    active_cores: list[CoreId]

class ActEvent(BaseModel):
    type: Literal["act"] = "act"
    id: int
    round: int
    act: Act

class BallotsLockedEvent(BaseModel):
    type: Literal["ballots_locked"] = "ballots_locked"

class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    outcome: Literal["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"]
    ballots: list[Ballot]
    conditions: list[str]
    disclaimer: str

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str

StreamEvent = PhaseEvent | ActEvent | BallotsLockedEvent | ResultEvent | ErrorEvent
```

- [ ] **Step 3: Write the three prompt identities**

Keep the canonical facet separate from the operational lens. Each builder includes the motion, required JSON example, word limit, instruction to address concrete peer claims, and instruction never to reveal hidden reasoning. Reactions receive the numbered frozen transcript and remaining-round count. Ballots receive the final transcript and cannot see peer ballots.

- [ ] **Step 4: Implement one direct provider function**

Read `DEEPSEEK_API_KEY` directly with `os.environ`; fail at startup with a clear message when it is absent. Construct `AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com")`. Request the fixed `deepseek-v4-flash` model, thinking mode, JSON Object output, the supplied effort, and `max_tokens=4096` for public acts or `8192` for ballots. Parse only `message.content` into `schema`; verify the returned `core` matches the requested identity, account for usage, discard `reasoning_content`, and retry once on provider failure, empty content, truncation, JSON failure, or Pydantic failure.

Do not add a `ModelClient` interface, provider factory, generic plugin system, temperature settings, or provider-managed conversation state.

- [ ] **Step 5: Add environment examples and run import checks**

```dotenv
DEEPSEEK_API_KEY=
```

Run:

```bash
cd backend
python -c "from magi.models import Motion, Act, Ballot; print(Motion(question='Proceed?'))"
```

Expected: a valid `Motion` prints without importing or calling DeepSeek.

---

### Task 2: Implement the bounded deliberation engine

**Files:**
- Create: `backend/src/magi/deliberation.py`
- Create: `backend/tests/test_deliberation.py`

**Interfaces:**
- Consumes: the Task 1 models, prompts, and `ask_deepseek` function.
- Produces: `async deliberate(motion: Motion, ask=ask_deepseek) -> AsyncIterator[StreamEvent]`; injected `ask` callables must accept the same arguments as `ask_deepseek`.
- Produces stream event types: `phase`, `act`, `ballots_locked`, `result`, and `error`.

- [ ] **Step 1: Write one complete fake-driven test**

Use a tiny async fake function with queued `Act` and `Ballot` values. Assert:

```python
assert opening_calls_are_concurrent
assert every_reaction_sees_only_prior_committed_rounds
assert discussion_stops_when_all_three_return_ready
assert all_ballots_receive_the_same_frozen_transcript
assert no_ballot_event_is_yielded_before_all_three_ballots_exist
assert final_result_preserves_the_conditional_vote_and_dissent
```

Also test the hard ceiling: when readiness never converges, each core receives exactly three reaction calls before balloting.

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd backend && pytest tests/test_deliberation.py -q`

Expected: failure because `deliberate` does not exist.

- [ ] **Step 3: Implement openings and synchronized reaction rounds**

Use `asyncio.gather` for the three openings. Commit each validated opening with a monotonically increasing integer ID. For rounds 1 through 3, freeze the numbered transcript, call all three cores concurrently, then commit their validated acts in canonical core order. Stop if all three acts in one round are `READY`; otherwise continue.

This barrier is intentional. Do not add inboxes, workers, locks, novelty classifiers, readiness revocation, or a general state machine.

- [ ] **Step 4: Implement private ballots and deterministic reduction**

Freeze the transcript once, request all three ballots concurrently, emit one `ballots_locked` status after all validate, then compute:

- `APPROVED` when at least two ballots are `AGREE` and none of those affirmatives require conditions;
- `APPROVED_WITH_CONDITIONS` when at least two ballots are `AGREE` or `CONDITIONAL` and at least one is conditional;
- `REJECTED` otherwise.

The `result` event contains all three ballots, deduplicated conditions, and a decision-support disclaimer. Never convert a failed core into `DISAGREE`.

- [ ] **Step 5: Add the single failure path and run tests**

Wrap the whole discussion in a five-minute `asyncio.timeout`. On unrecovered provider, validation, or timeout failure, yield one sanitized `error` event and stop without a result.

Run: `cd backend && pytest tests/test_deliberation.py -q`

Expected: all deliberation tests pass.

---

### Task 3: Stream one discussion over HTTP

**Files:**
- Create: `backend/src/magi/app.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Motion` and `deliberate`.
- Produces: `POST /api/discuss` with `application/x-ndjson` output.

- [ ] **Step 1: Write the API test**

Override the deliberation dependency with a short async generator. Submit a valid motion and assert each non-empty response line parses as JSON in order. Assert a two-character question returns `422`, and assert the response never includes `reasoning_content` or an API key.

- [ ] **Step 2: Implement the endpoint**

Encode each event as one compact JSON object followed by `\n`:

```python
@app.post("/api/discuss")
async def discuss(motion: Motion) -> StreamingResponse:
    async def body():
        async for event in deliberate(motion):
            yield event.model_dump_json() + "\n"
    return StreamingResponse(body(), media_type="application/x-ndjson")
```

Allow `http://localhost:5173` during local development. Do not add origin settings, IDs, repositories, replay buffers, heartbeats, snapshot endpoints, cancellation endpoints, health endpoints, or RFC problem-detail wrappers.

- [ ] **Step 3: Run the backend checks**

Run: `cd backend && pytest -q`

Expected: both test files pass without a real API key or network access.

---

### Task 4: Build the single-screen MAGI console

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/CorePanel.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: the NDJSON event stream from `POST /api/discuss`.
- Produces: motion form, live phase display, three core panels, shared transcript, concealed ballot state, simultaneous reveal, and final result.

- [ ] **Step 1: Configure only the selected dependencies**

Install React, React DOM, Tailwind's Vite plugin, and Motion. Do not install shadcn, Radix, Zod, a state library, a router, an SSE library, or a component test framework.

- [ ] **Step 2: Define the small public event union**

Mirror only `phase`, `act`, `ballots_locked`, `result`, and `error` in `types.ts`. Parse NDJSON lines defensively in `App.tsx`; unknown event types become a visible protocol error rather than modifying state.

- [ ] **Step 3: Implement streaming fetch**

Submit with `fetch`, read `response.body` through `TextDecoderStream`, retain an incomplete trailing line between chunks, and apply complete JSON lines to local React state. Disable submission while active. `AbortController` cancels the request when the component unmounts or the user starts over after an error.

- [ ] **Step 4: Build the core experience**

Use one accessible form and three `CorePanel` instances. Show the current phase, elapsed time, active cores, committed acts in order, and up to three remaining reaction rounds. During balloting show only locked indicators. Apply all three ballot values from the single `result` event so they reveal together.

Use CSS for the technical grid, panel geometry, labels, responsive single-column layout, focus states, and `prefers-reduced-motion`. Use Motion only for core activity and the synchronized ballot reveal. Do not add audio, maintenance mode, event-ID controls, reply-link diagrams, themes, sharing, or export.

- [ ] **Step 5: Verify the frontend**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both commands exit successfully. Manually run one fake or real discussion and confirm the UI remains informative during a multi-minute response.

---

### Task 5: Document and run the vertical slice

**Files:**
- Create: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces: repeatable local development and validation commands.

- [ ] **Step 1: Write the short operator README**

Document purpose, lore-versus-project interpretation, prerequisites, `DEEPSEEK_API_KEY`, separate backend/frontend start commands, expected latency, model cost warning, private-reasoning handling, limitations, and the exact backend/frontend checks. Link both this plan and the long-term plan.

- [ ] **Step 2: Ignore only generated and secret files**

Ignore `.env`, virtual environments, Python caches, `node_modules`, and `frontend/dist`. Do not ignore `docs/`.

- [ ] **Step 3: Run the lean release check**

```bash
cd backend && pytest -q
cd ../frontend && npm run typecheck && npm run build
```

Expected: all commands exit successfully. No Docker, Playwright, CI matrix, deployment manifest, or production hosting work belongs in this task.

---

## Lean MVP acceptance checklist

- [ ] The three openings are independent and generated concurrently.
- [ ] Every core can react to peer content for up to three rounds and can stop with `READY` or `PASS`.
- [ ] The public transcript contains only validated content, never hidden reasoning.
- [ ] Ballots use one frozen transcript and appear simultaneously.
- [ ] The result preserves all three votes, dissent, rationale, and conditions.
- [ ] The UI visibly distinguishes analysis, discussion, ballot lock, completion, and failure.
- [ ] The discussion terminates after three reaction rounds or five minutes.
- [ ] A failed core produces an explicit failed session rather than fabricated consensus.
- [ ] The server keeps the DeepSeek key and `reasoning_content` out of the stream.
- [ ] Backend tests, frontend type-checking, and the production frontend build pass.

## Promotion rule

Do not implement the full plan merely because the lean MVP is complete. Promote individual capabilities only after observing a concrete limitation: lost sessions justify replay, user demand justifies persistence, awkward round barriers justify the event-driven coordinator, repeated regressions justify broader tests, and actual deployment justifies containers and operational endpoints.
