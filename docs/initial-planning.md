# Project S.C. MAGI: Live Multi-Agent Deliberation Simulator

**Product and architecture direction — version 1.1**

---

## Planning status

This document remains the product and lore specification. Implementation should begin with the [lean MVP plan](superpowers/plans/2026-08-18-magi-sim-lean-mvp.md). The existing [full implementation plan](superpowers/plans/2026-08-17-magi-sim-mvp.md) is retained as the long-term hardening and expansion path after the core deliberation experience proves compelling.

---

## 1. Project intent

S.C. MAGI is a small, theatrical AI side project inspired by the MAGI system in *Neon Genesis Evangelion*. A user submits a dilemma or proposed action and watches three AI cores examine it from conflicting perspectives, react to one another in a live discussion, and lock in individual ballots.

The experience should feel like operating a consequential command system. It is still decision support and entertainment: agreement among three language-model calls does not make an answer objectively correct, safe, or authorized for real-world execution.

### The central product loop

```text
Submit a motion
      ↓
Three cores form independent positions in parallel
      ↓
The cores publish, challenge, concede, and add conditions live
      ↓
All cores become ready to vote, or the discussion reaches its budget
      ↓
Ballots are committed privately and revealed together
      ↓
MAGI applies the selected quorum policy and presents the result
```

The live discussion is not decorative loading text. Each core receives completed messages from the shared transcript and may respond to their substance. The user sees the conversation develop as an event stream rather than waiting for three isolated answers.

---

## 2. Lore baseline and adaptation boundary

The primary inspiration is the original television continuity and *The End of Evangelion*. Detailed research and sources live in [`research/magi-system-lore.md`](research/magi-system-lore.md).

### Canonical foundation

- MAGI consists of three independent seventh-generation organic computers: **MELCHIOR-1**, **BALTHASAR-2**, and **CASPER-3**.
- Dr. Naoko Akagi imprinted three conflicting facets of herself into them: herself as a **scientist**, a **mother**, and a **woman**.
- The system evaluates proposals using the three differing judgments. Ordinary civic decisions are described as majority decisions.
- MAGI can issue qualified or conditional answers. Exceptional operations, especially self-destruction, are not safely modeled as ordinary “two votes always wins.”
- The anime presents terse votes, probabilities, status readouts, intrusion alerts, and machine judgments. It does not show the three cores holding a natural-language debate.

### Project interpretation

Visible conversation, rebuttals, readiness signals, confidence estimates, a completion controller, and color-coded activity states are original interface mechanics. They are an *Evangelion-inspired visualization* of the conflict inside MAGI, not a claim about its canonical implementation.

The richer operational lenses below are also project-specific. “Mother” is not treated as a synonym for universal ethics, and “woman” is not treated as a synonym for realpolitik.

| Core | Canonical facet | Project lens | Product behavior |
| --- | --- | --- | --- |
| **MELCHIOR-1** | The scientist | Evidence and systems | Tests assumptions, quantifies uncertainty, compares expected outcomes, and asks what the available evidence actually supports. |
| **BALTHASAR-2** | The mother | Care and stewardship | Examines harm, reversibility, affected people, duties of care, and protections for the most exposed stakeholders. |
| **CASPER-3** | The woman | Desire and human reality | Examines motives, relationships, power, incentives, social consequences, and the gap between rational plans and human behavior. |

These lenses should remain configurable. The names and canonical facets provide the fiction; the operational prompts make the product understandable and useful.

---

## 3. What “live discussion” means

The cores are concurrent participants on a shared, append-only discussion transcript. They do not follow a permanently fixed `A → B → C` speaking order.

### Discussion behavior

1. **Independent opening positions:** All three cores receive the same motion and evidence at the same time. They produce their first positions without seeing the others, reducing immediate groupthink.
2. **Publication:** A completed statement is appended to the transcript and broadcast to the other two inboxes. Partial token fragments are streamed to the UI but are not treated as messages by peer cores.
3. **Reactive interjection:** A core may respond when a new statement conflicts with its lens, introduces unsupported evidence, changes a condition, or resolves one of its objections.
4. **Meaningful acts:** Each contribution is classified as `POSITION`, `CHALLENGE`, `RESPONSE`, `CONCEDE`, `PROPOSE_CONDITION`, `CLARIFY`, or `READY`. A core may also `PASS` rather than manufacture disagreement.
5. **Readiness:** A core signals `READY` when it has no material unresolved challenge and can commit a ballot. A later material claim may revoke readiness while the discussion remains open.
6. **Closure:** Discussion closes when all cores are ready and no challenge is outstanding, or when a hard event/time/token budget is reached.
7. **Simultaneous lock-in:** Final ballots are generated from the same frozen transcript, committed privately, and revealed together so one visible final vote cannot influence another.

### Bounded autonomy

The discussion should feel emergent without becoming an unbounded agent loop. Contribution limits are ceilings, not quotas: a core should become ready or `PASS` instead of filling unused turns with repetition.

The product exposes three discussion depths:

| Mode | Maximum reactive contributions per core | Intended use |
| --- | ---: | --- |
| **Quick** | 1 | Fast or simple motions. |
| **Standard** | 3 | Default; enough room to challenge, respond, and refine or concede. |
| **Extended** | 4 | Complicated motions where the user accepts greater latency and model cost. |

Every mode should enforce:

- one opening statement per core;
- a maximum wall-clock duration;
- per-core and whole-session token budgets;
- deduplication of substantially repeated claims;
- a novelty check requiring each reaction to address a specific event, add information, resolve a challenge, change a condition, or update the core's position;
- cancellation and timeout handling;
- a forced-ballot fallback when the discussion budget expires before every core signals readiness.

These are safety rails around a live event-driven discussion, not a conversion to a hidden batch pipeline.

---

## 4. Deliberation architecture

```text
                         USER MOTION + EVIDENCE
                                   │
                                   ▼
                     ┌──────────────────────────┐
                     │   SESSION COORDINATOR    │
                     │ budgets · state · policy │
                     └─────────────┬────────────┘
                                   │
                     ┌─────────────▼────────────┐
                     │ APPEND-ONLY EVENT STREAM │
                     │ shared public transcript │
                     └───────┬──────┬──────┬────┘
                             │      │      │
                   ┌─────────▼─┐ ┌──▼──────┐ ┌▼─────────┐
                   │MELCHIOR-1│ │BALTHASAR│ │ CASPER-3 │
                   │  inbox   │ │  inbox  │ │  inbox   │
                   └─────┬────┘ └────┬────┘ └────┬─────┘
                         └────────────┼────────────┘
                                      │ public messages
                                      ▼
                               COMPLETION CHECK
                                      │
                                      ▼
                           PRIVATE BALLOT COMMIT
                                      │
                                      ▼
                           SIMULTANEOUS REVEAL
```

### Coordinator responsibilities

The coordinator is plumbing, not a fourth opinionated agent. It:

- owns the canonical session state and monotonically ordered event IDs;
- fans completed transcript events out to core inboxes;
- prevents a core from responding to its own event;
- enforces contribution, token, and time budgets;
- tracks unresolved challenges and readiness without treating silence as agreement;
- freezes the exact transcript version used for final ballots;
- applies a deterministic quorum policy after ballots are revealed;
- emits UI telemetry and terminal states;
- cancels outstanding work when a session ends or the user aborts it.

### Why an event stream still matters

For only three cores, Redis, Nostr, or an external message broker would add complexity without improving the experience. An in-memory event stream and one inbox per core are enough for a single-process MVP while preserving genuine reactive behavior. A durable or distributed transport can replace this boundary later without changing the event contract.

### No raw chain-of-thought

The interface streams concise, intentional discussion messages and evidence references—not hidden chain-of-thought. Each message should be written for the other cores and the user to inspect. Internal model reasoning remains internal.

---

## 5. Motion, event, and ballot contracts

### Motion

```json
{
  "motion_id": "motion_123",
  "question": "Should the proposed action proceed?",
  "context": "Relevant background supplied by the user.",
  "evidence": [],
  "stakes": "normal",
  "quorum": "majority"
}
```

`quorum` is one of:

- `majority`: two affirmative ballots can approve an ordinary motion;
- `unanimous`: every core must affirm;
- `human_confirm`: MAGI provides a recommendation but never marks the motion executable without user confirmation.

High-impact, destructive, medical, legal, financial, or otherwise consequential motions should default to `human_confirm`. The simulator must not execute external actions in the MVP.

### Discussion event

```json
{
  "event_id": 12,
  "session_id": "session_123",
  "sender": "CASPER-3",
  "kind": "CHALLENGE",
  "reply_to": 9,
  "content": "The projected adoption rate assumes cooperation that has not been established.",
  "claims": ["adoption assumption is unsupported"],
  "created_at": "2026-08-17T12:00:00Z"
}
```

### Final ballot

```json
{
  "node_id": "BALTHASAR-2",
  "vote": "CONDITIONAL",
  "confidence": 0.74,
  "rationale": "Proceed only with a reversible pilot and an explicit opt-out.",
  "conditions": ["limit the first release to a reversible pilot", "provide an opt-out"],
  "blocking_risks": [],
  "transcript_version": 18
}
```

`vote` is `AGREE`, `DISAGREE`, or `CONDITIONAL`. Confidence is a project-specific self-report and must be displayed as such, not as a calibrated probability of truth.

### Session result

The result preserves every ballot and condition. It never flattens `CONDITIONAL` into an unconditional yes.

Possible terminal outcomes are:

- `APPROVED`;
- `REJECTED`;
- `APPROVED_WITH_CONDITIONS`;
- `HUMAN_CONFIRMATION_REQUIRED`;
- `INCOMPLETE`;
- `CANCELLED`;
- `FAILED`.

A 3–0 rejection is **unanimous refusal**, not a deadlock. `INCOMPLETE` means the system could not obtain valid ballots under the configured rules; disagreement by itself is a valid completed result.

---

## 6. Initial technical shape

The MVP should be one deployable web application with a small server-side orchestration layer.

| Layer | Initial responsibility |
| --- | --- |
| **Coordinator** | Session state machine, budgets, transcript, readiness, ballot freeze, and quorum reduction. |
| **Core runtime** | Three independent `deepseek-v4-flash` contexts with separate prompts and inboxes. Openings and reactive contributions use `high` reasoning effort; final ballots use `max`. |
| **Streaming API** | Server-Sent Events for one-way session telemetry. Use WebSockets only if users later need to interject during an active discussion. |
| **Persistence** | In-memory sessions for the first vertical slice; optionally persist completed session summaries later. |
| **Interface** | React + TypeScript built with Vite, Tailwind CSS, selected shadcn/ui components backed by Radix primitives, and Motion for meaningful state transitions. |

Python `asyncio` with FastAPI remains the backend choice. The frontend uses React, TypeScript, Vite, Tailwind CSS, selected shadcn/Radix primitives, and Motion. The architecture does not require persistent standby workers: create scoped tasks for a session, cancel them at session completion, and keep all session mutation behind the coordinator.

### Model and reasoning configuration

All three cores use the same DeepSeek model ID, `deepseek-v4-flash`, through independent calls and persona-specific contexts:

| Operation | Model | Reasoning effort |
| --- | --- | --- |
| Independent opening position | `deepseek-v4-flash` | `high` |
| Reactive contribution or readiness review | `deepseek-v4-flash` | `high` |
| Private final ballot | `deepseek-v4-flash` | `max` |

The coordinator, completion checks, transcript, budgets, and quorum reducer remain deterministic Python and do not call an LLM. DeepSeek's private `reasoning_content` is never sent to peer cores, persisted in the public transcript, streamed to the browser, or shown to the user. Only the validated public answer participates in the discussion.

### Required failure behavior

- A failed core does not silently become a negative vote.
- If one core fails before ballots, the session becomes `FAILED` or asks the user whether to retry; it does not pretend to have full MAGI consensus.
- Malformed model output is validated and retried once with a repair prompt.
- Duplicate or late events are ignored using session state and event IDs.
- Disconnecting the browser does not corrupt the running session; reconnect behavior can be added after the first slice.
- Every session has an explicit cancellation path.

---

## 7. Experience and visual direction

### Primary layout

- Three prominent core surfaces in a triangular or overlapping arrangement.
- A central shared diagnostic trace that shows completed conversational acts and their relationships.
- A motion header with the selected quorum, elapsed time, budget, and current phase.
- A final reveal that locks all three ballots simultaneously, followed by conditions and human-confirmation status.

### Core activity states

- `STANDBY`
- `ANALYZING`
- `TRANSMITTING`
- `CHALLENGING`
- `READY`
- `LOCKED`
- `COMPROMISED` (reserved for the later Ireul mode)
- `ERROR`

Amber, red, green, and pale technical text can support the atmosphere, but colors should not carry meaning alone. Labels, shapes, motion, and accessible contrast must communicate state too.

### Distinctive Evangelion-inspired motifs

- severe geometric overlays, condensed labels, timers, and terse machine verdicts;
- escalating countdown and takeover indicators;
- a clean command interface hiding an organic maintenance layer of cabling, wetware textures, handwritten notes, and back doors;
- optional “maintenance mode” that exposes prompts, event metadata, budgets, and transcript versions;
- restrained sound and synchronized lock-in motion, with reduced-motion and mute controls.

The project should use original graphics and typography rather than copied NERV logos, character art, screenshots, or soundtrack material.

---

## 8. Product guardrails

- MAGI is a perspective generator, not a truth oracle.
- Three agents may repeat the same hallucination or inherit the same blind spot.
- Model agreement is not evidence unless the underlying claims are supported.
- User-supplied facts and retrieved evidence must be visually distinguishable from model assertions.
- The public discussion should favor short, falsifiable claims over speeches.
- Conditions, dissent, uncertainty, and incomplete sessions are first-class results.
- No external action is automatically executed by an MVP verdict.

---

## 9. Implementation roadmap

| Phase | Milestone | Deliverables |
| --- | --- | --- |
| **1. Vertical slice** | One complete theatrical decision | Motion input, three independent openings, Quick mode with one reactive contribution per core, SSE event stream, simultaneous structured ballots, quorum reducer, and final UI. |
| **2. Live deliberation** | Robust reactive conversation | Per-core inboxes, challenge/readiness tracking, Standard mode with three reactions and Extended mode with four, novelty checks, early stopping, time/token budgets, retries, cancellation, and transcript replay. |
| **3. Presentation polish** | MAGI command experience | Tri-core layout, diagnostic trace, maintenance mode, audio cues, synchronized lock-in, accessibility, and session sharing/export. |
| **4. Lore extensions** | Fictional failure scenarios | Ireul intrusion simulation, compromised-core states, quorum degradation, protection-666-inspired defense sequence, and recovery tools. |
| **5. Optional experiments** | Compare orchestration choices | Multiple model providers, alternate persona lenses, durable persistence, and distributed transports only if the local architecture proves insufficient. |

### MVP acceptance criteria

The first usable version is complete when:

1. a user can submit a motion and choose or accept a quorum policy;
2. all three cores independently publish an opening position;
3. each core can react to at least one completed peer message;
4. the UI streams those events in causal order without exposing raw chain-of-thought;
5. contribution limits act as maximums, and cores can stop early without manufacturing additional disagreement;
6. the discussion always terminates within configured contribution, time, and token budgets;
7. all ballots use the same frozen transcript version and reveal together;
8. the result preserves dissent and conditions and never performs an external action;
9. failures and cancellation produce explicit terminal states rather than fabricated consensus.

---

## 10. Deferred ideas

The following are intentionally outside the first version:

- Redis, Nostr, or another distributed event backbone;
- long-lived autonomous workers between user sessions;
- arbitrary numbers of cores;
- automatic real-world command execution;
- multiple providers selected primarily for persona flavor;
- claims that the Ireul mode is a real prompt-injection defense;
- unlimited debate or token-by-token peer reactions.

They can be reconsidered after the live three-core experience is compelling, predictable, and affordable.
