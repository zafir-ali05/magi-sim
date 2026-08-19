# MAGI simulator

This is a small project based on the MAGI system from *Neon Genesis Evangelion*. I mostly wanted to see what would happen if the three parts of the system were treated as independent AI decision makers instead of wrapping one normal chatbot response in three names.

Evangelion leaves most of the actual machinery unexplained. The anime gives each MAGI core a different part of Naoko Akagi's personality and shows them reaching decisions through voting. This project takes that idea and turns it into a visible, bounded discussion between three AI perspectives. So yeah, it is my interpretation of the MAGI built as a normal Python web app. The fictional biological hardware is still fictional.

Everything runs locally. It gives advice, shows short public conclusions and objections, and produces a majority decision. Real-world execution is outside its scope.

## The three cores

Each core uses the same DeepSeek model with a separate identity and decision method:

- **MELCHIOR-1, the scientist:** looks at evidence, causal claims, uncertainty, and whether an idea can survive scrutiny.
- **BALTHASAR-2, the mother:** looks at care, consent, vulnerability, protection, and who carries the risk.
- **CASPER-3, the woman:** looks at desire, autonomy, identity, relationships, incentives, and how people are likely to behave.

Those descriptions come from the anime's scientist, mother, and woman split. The more detailed methods are project interpretations that make the roles useful during an actual discussion. They are also given failure modes to avoid, so Melchior should not become cold and amoral, Balthasar should not turn care into control, and Casper should not manufacture emotional contrarianism for the sake of it.

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

All three openings are requested concurrently from the same motion. Each core forms its opening blind to the other two. Once all three are ready, the coordinator commits them to the public transcript in a stable order.

The discussion then becomes event-driven. Each core has a worker and an `asyncio.Queue` inbox. The inbox carries transcript version notifications, and every conversation passes through the validated shared record. When a new public act is committed, the other workers wake up, inspect the latest transcript, and independently choose one action:

- `PUBLISH` a challenge, response, concession, clarification, or condition.
- `PASS` because nothing useful needs to be added yet.
- `READY` because the core has reviewed the current version and has no remaining public objection.

There is no fixed MELCHIOR -> BALTHASAR -> CASPER loop. A core can respond several times, stay quiet, concede a point, or become ready. Publishing a new act wakes the peers again and revokes their earlier readiness because the shared record has changed.

The workers stay alive and listen during one deliberation. Every LLM response is still a fresh API inference supplied with that core's identity, the motion, and the current public transcript. The coordinator, queues, transcript, and session state provide the continuity. Honestly, that is enough for this local version without pulling in Redis or a whole agent framework.

Discussion is deliberately bounded. By default, each core gets up to five review evaluations and three public contributions, while the entire discussion has time and token limits. This keeps one stubborn loop from going forever or quietly burning through an absurd number of tokens.

## Ballots and decisions

Once review closes, the public transcript is frozen. Each core receives the same final transcript and casts a private ballot with one of these votes:

- `AGREE`
- `DISAGREE`
- `CONDITIONAL`, with explicit conditions

Ballots stay hidden until all three are complete. The current interface always uses majority rule. Two affirmative votes approve the motion, with `CONDITIONAL` counting as affirmative and producing an approved-with-conditions result. Fewer than two affirmative votes reject it. A missing or failed core produces an incomplete result instead of pretending that silence means agreement.

Final ballot calls use DeepSeek's maximum reasoning setting. Openings and public reviews use high reasoning. The adapter validates every response against a strict schema and retries malformed output with a repair instruction.

Private provider reasoning content is never displayed, persisted, streamed, or passed between cores. Its token count can be recorded for budget accounting, but the content itself is discarded. The visible transcript contains only short, validated public acts.

## Stack

- **Frontend:** React 19, Vite 7, and plain CSS
- **Backend:** Python 3.12+, FastAPI, Pydantic, and `asyncio`
- **LLM:** DeepSeek V4 Flash through its OpenAI-compatible API
- **Streaming:** newline-delimited JSON over one HTTP response

## Running it locally

You will need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), Node.js with npm, and a DeepSeek API key.

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

### Running the UI without an API key

There is a small mock discussion server for frontend testing. Stop the real backend first, then run:

```bash
cd frontend
npm run mock:api
```

Keep that terminal open and run `npm run dev` in a second frontend terminal. The mock server uses the same port as the real backend and streams a fixed mixed-ballot discussion.

## Checks

The tracked automated checks currently cover the frontend event protocol, session reducer, MAGI visual state, core components, and mock discussion stream.

```bash
cd frontend
npm test
npm run build
```

## Project layout

```text
backend/src/magi/   coordinator, prompts, transcript, policies, and DeepSeek adapter
frontend/src/       React console, stream handling, session state, and MAGI core display
frontend/scripts/   local mock discussion server
THIRD_PARTY_NOTICES.md
```

## UI credit

The frontend adapts the visual structure and styling of [Tomasz Rewak's MAGI project](https://github.com/TomaszRewak/MAGI), especially the three polygon cores, amber framing, Japanese status headers, state colors, and response window.

Only the frontend presentation was adapted. This project's backend, discussion protocol, prompts, state handling, motion form, and streaming API were written separately. The original access-code flow and API handling remain in the source project. The full attribution and license text are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
