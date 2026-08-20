# MAGI simulator

This is a small side project based on the MAGI system from *Neon Genesis Evangelion*. I mostly wanted to see what the three cores would look like as actual AI workers instead of one chatbot answer copied into three boxes.

Evangelion leaves most of the machinery unexplained. The anime gives each core a different part of Naoko Akagi's personality and shows them voting on decisions. Basically, this is my take on that idea built as a normal Python web app. The fictional biological hardware is still fictional.


## The three cores

Each core uses the same DeepSeek model with a separate identity and decision method:

- **MELCHIOR-1, the scientist:** looks at evidence, causal claims, uncertainty, and whether an idea can survive scrutiny.
- **BALTHASAR-2, the mother:** looks at care, consent, vulnerability, protection, and who carries the risk.
- **CASPER-3, the woman:** looks at desire, autonomy, identity, relationships, incentives, and how people are likely to behave.

Those three labels come from the anime. The detailed methods are my own interpretation so the roles have something useful to work with. I also gave them a few failure modes to avoid. Melchior should not become cold and amoral, Balthasar should not turn care into control, and Casper should not argue just for the sake of it.

## How the discussion works

The basic flow looks like this:

```text
motion submitted
      |
      v
three independent opening positions
      |
      v
shared versioned transcript
      |
      v
per-core inbox notifications and reactive reviews
      |
      v
transcript freezes when review is finished or bounded
      |
      v
three private ballots
      |
      v
majority result
```

All three opening calls start together. None of the cores sees the other openings early, and the coordinator adds them to the transcript in a fixed order once all three are done.

After that, each core has a worker and an `asyncio.Queue` inbox. The queue messages are just transcript version numbers. The agents are not directly DMing each other or passing around hidden reasoning. When a public act is added, the other workers wake up, read the newest transcript, and pick one action:

- `PUBLISH` a challenge, response, concession, clarification, or condition.
- `PASS` because nothing useful needs to be added yet.
- `READY` because the core has reviewed the current version and has no remaining public objection.

Each core must publish once during its first shared review before `PASS` or `READY` becomes available. That gives every successful deliberation at least six public acts: three openings and three initial reviews.

There is no fixed MELCHIOR -> BALTHASAR -> CASPER loop after the openings. A core can respond a few more times, stay quiet, concede something, or mark itself ready. A new act wakes the other cores again because their previous review is now stale.

The workers stay alive for one deliberation. Every response is still a fresh API call with that core's identity, the motion, and the current public transcript. The coordinator and queues are what make it feel like one continuing discussion. Honestly, that is enough for this local version without pulling in Redis or some huge agent framework.

The discussion has limits. Each core gets up to five reviews and three public contributions by default, plus there is an overall time and token budget. Otherwise one stubborn loop could run forever and burn through a dumb amount of tokens.

## Ballots and decisions

When the discussion stops, the transcript is frozen. Each core gets the same final copy and casts a private ballot:

- `AGREE`
- `DISAGREE`
- `CONDITIONAL`, with explicit conditions

Ballots stay hidden until all three are done. The interface always uses majority rule. Two affirmative votes approve the motion, and a `CONDITIONAL` vote adds its conditions to the result. Fewer than two rejects it. If a core fails, the result is incomplete instead of treating silence as agreement.

Final ballots use DeepSeek's maximum reasoning setting. Openings and public reviews use high reasoning. Every answer gets checked against the expected JSON shape, and malformed output gets another try with a repair message.

Private provider reasoning is never displayed, saved, streamed, or passed between cores. I count its tokens for the budget and throw away the content. Only the short public acts make it into the transcript.

## Stack

- **Frontend:** React, Vite, and plain CSS
- **Backend:** Python, FastAPI, Pydantic, and `asyncio`
- **LLM:** DeepSeek V4 Flash through its API
- **Streaming:** JSON over one HTTP response

## Running it locally

You will need Python 3.12 or newer, uv, Node.js with npm, and a DeepSeek API key (or any OpenAI compatible provider).

Start the backend in one terminal:

```bash
cd backend
uv sync
DEEPSEEK_API_KEY="your-key-here" uv run uvicorn magi.app:app --reload --port 8000
```

Then start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` requests to the backend on port `8000`.

## Checks

Build the frontend before committing UI changes:

```bash
cd frontend
npm run build
```

## Project layout

```text
backend/src/magi/   coordinator, prompts, transcript, policies, and DeepSeek adapter
frontend/src/       React console, stream handling, session state, and MAGI core display
```

## UI credit

The frontend adapts the visual structure and styling of [Tomasz Rewak's MAGI project](https://github.com/TomaszRewak/MAGI), especially the three polygon cores, amber framing, Japanese status headers, state colors, and response window.

Only the frontend presentation was adapted. This project's backend, discussion protocol, prompts, state handling, motion form, and streaming API were written separately. The original access-code flow and API handling remain in the source project.
