# Exact MAGI Frontend Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current frontend presentation with a faithful, accessible React/Vite port of Tomasz Rewak's MAGI UI while preserving this project's existing backend, live discussion flow, and public-data privacy boundary.

**Architecture:** Keep `App.jsx` as the owner of request and stream state, add one pure adapter module that maps public session data to reference visual states and modal content, and render the reference tri-core grid through two focused React components. Replace the current visual layer with namespaced reference-derived CSS, then visually validate the complete app against the supplied screenshots using deterministic mocked streams.

**Tech Stack:** JavaScript, React 19, Vite 7, Tailwind CSS 4 entrypoint, native CSS Grid/container queries/clip paths, native `<dialog>`, Node's built-in test runner. Keep the existing Python 3.12/FastAPI backend unchanged.

**Spec:** [`../specs/2026-08-18-exact-magi-ui-port-design.md`](../specs/2026-08-18-exact-magi-ui-port-design.md)

## Global Constraints

- The supplied `MAGI-master.zip` and screenshots are the visual source of truth; do not reinterpret the schematic as generic cards or an SVG approximation.
- Copy the reference grid, clip paths, amber connector bars, palette, striped background, Japanese headers, response indicator, and modal composition.
- Keep the existing `/api/discuss` request, NDJSON protocol, React stream lifecycle, transcript, result, error handling, and start-over behavior.
- Do not modify any file under `backend/`.
- Do not copy the reference access-code input, question input, Dash wiring, Python callbacks, or OpenAI integration.
- Keep this project's motion and context fields outside the schematic and style them to match its amber/black visual language.
- Never render, persist, stream, log, or pass `reasoning_content` to a frontend component.
- Never reveal a ballot before the existing `result` event; `ballots_locked` exposes only a sealed state.
- Preserve keyboard interaction, native focus management, visible focus, screen-reader labels, 320px layout safety, and reduced-motion behavior.
- The processing effect uses a hard step flicker at an 800ms cycle, not the reference's unsafe 250ms cycle; reduced motion disables flicker.
- Do not add a component library, state library, font package, remote font, SVG asset package, or animation dependency.
- Retain the full reference MIT notice in `THIRD_PARTY_NOTICES.md`.
- The rejected `codex/magi-polygon-ui` prototype commits `1a1c92b` and `496b5d3` are not an implementation base. Start from `testing` and reuse only independently verified pure-state ideas where they conform to this spec.

---

## File Map

```text
frontend/src/
├── App.jsx                    # existing stream lifecycle; composes the new UI
├── CoreResponseDialog.jsx     # accessible reference-style full-response modal
├── MagiCoreArray.jsx          # exact header, diagnostics, polygons, connectors, status
├── magiVisualState.js         # pure public-session-to-view-model translation
├── magiVisualState.test.js    # exhaustive mapping and privacy tests
├── events.js                  # unchanged
├── events.test.js             # unchanged
├── session.js                 # unchanged
├── session.test.js            # unchanged
└── styles.css                 # complete reference-derived visual layer

THIRD_PARTY_NOTICES.md         # reference attribution and MIT license
```

Delete `frontend/src/CorePanel.jsx` after `App.jsx` no longer imports it. Do not create a general-purpose design-system directory; this is one intentionally specific surface.

---

### Task 1: Build the Public Visual-State Adapter

**Files:**
- Create: `frontend/src/magiVisualState.js`
- Create: `frontend/src/magiVisualState.test.js`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: current `phase`, `sessionStatus`, `activeCores`, public `acts`, optional revealed `ballot`, `ballotsLocked`, public `result`, sanitized `error`, and submitted `question`.
- Produces: `getCoreVisualState(input) -> { key, english, japanese, flicker }`.
- Produces: `getSystemVisualState(input) -> { key, english, japanese }`.
- Produces: `buildCoreDialogModel(input) -> { title, question, status, error, conditions, fullResponse, ballotLocked }`.

- [ ] **Step 1: Add failing tests for the exact state palette**

Create table-driven tests in `magiVisualState.test.js` asserting:

```js
[
  ["idle", null, "information", "INFORMATION", "情 報", false],
  ["running", null, "processing", "PROCESSING", "情 報", true],
  ["complete", "AGREE", "agree", "AGREE", "合 意", false],
  ["complete", "CONDITIONAL", "conditional", "CONDITIONAL", "状 態", false],
  ["complete", "DISAGREE", "disagree", "DISAGREE", "拒 絶", false],
  ["error", null, "error", "ERROR", "誤 差", false],
]
```

Also assert that a completed public act makes an inactive pre-ballot core stable cyan, while active/connecting and locked states flicker.

- [ ] **Step 2: Run the focused test and confirm the missing-module failure**

Run:

```bash
cd frontend
node --test src/magiVisualState.test.js
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `magiVisualState.js`.

- [ ] **Step 3: Add failing tests for dialog mapping and ballot privacy**

Cover these exact cases:

```js
const locked = buildCoreDialogModel({
  core: "CASPER-3",
  question: "Proceed?",
  phase: "BALLOTING",
  sessionStatus: "running",
  acts: [{ id: 4, round: 1, act: { core: "CASPER-3", kind: "CHALLENGE", content: "Public objection." } }],
  ballot: null,
  ballotsLocked: true,
  error: "",
});

assert.equal(locked.ballotLocked, true);
assert.match(locked.fullResponse, /Public objection/);
assert.match(locked.fullResponse, /Vote sealed until all cores report/);
assert.doesNotMatch(JSON.stringify(locked), /reasoning_content|private rationale/i);
```

For a revealed `CONDITIONAL` ballot, assert that `conditions` contains each public condition and `fullResponse` appends the public rationale. For a failed session, assert that only the sanitized `error` is rendered. For a core with no acts, assert `Waiting for public response...`.

- [ ] **Step 4: Implement immutable state constants and pure mapping functions**

Use these keys and copy exactly:

```js
const CORE_STATES = {
  information: { key: "information", english: "INFORMATION", japanese: "情 報", flicker: false },
  processing: { key: "processing", english: "PROCESSING", japanese: "情 報", flicker: true },
  locked: { key: "locked", english: "VOTE SEALED", japanese: "情 報", flicker: true },
  agree: { key: "agree", english: "AGREE", japanese: "合 意", flicker: false },
  conditional: { key: "conditional", english: "CONDITIONAL", japanese: "状 態", flicker: false },
  disagree: { key: "disagree", english: "DISAGREE", japanese: "拒 絶", flicker: false },
  error: { key: "error", english: "ERROR", japanese: "誤 差", flicker: false },
};
```

Precedence is: sanitized error, revealed ballot, locked ballot, active processing, stable information. `buildCoreDialogModel` filters acts with `event.act.core === core`, sorts in existing stream order without mutating input, formats each public act as `R{round} {kind}: {content}`, and appends a ballot section only when a ballot argument exists.

- [ ] **Step 5: Add the test file to the existing test command and run all frontend unit tests**

Change `frontend/package.json` to:

```json
"test": "node --test src/events.test.js src/session.test.js src/magiVisualState.test.js"
```

Run:

```bash
cd frontend
npm test
```

Expected: all existing and new tests pass.

- [ ] **Step 6: Commit the independently testable adapter**

```bash
git add frontend/package.json frontend/src/magiVisualState.js frontend/src/magiVisualState.test.js
git commit -m "feat: map MAGI public states to reference visuals"
```

---

### Task 2: Port the Exact Tri-Core Schematic and Modal

**Files:**
- Create: `frontend/src/MagiCoreArray.jsx`
- Create: `frontend/src/CoreResponseDialog.jsx`
- Modify: `frontend/src/App.jsx`
- Delete: `frontend/src/CorePanel.jsx`

**Interfaces:**
- Consumes: Task 1 functions and the current public session fields.
- Produces: `MagiCoreArray(props)` with `onSelectCore(coreId)`.
- Produces: `CoreResponseDialog({ open, model, onClose })`.
- `App.jsx` owns `selectedCore` and `submittedQuestion`; neither component fetches or parses events.

- [ ] **Step 1: Write a rendered component-contract test before creating the components**

Create `MagiComponents.test.js`, load JSX through Vite's SSR module loader, and assert the actual static HTML rendered by React:

```js
const html = renderToStaticMarkup(React.createElement(MagiCoreArray, idleProps));
assert.equal((html.match(/<button/g) ?? []).length, 3);
assert.ok(html.indexOf("BALTHASAR • 2") < html.indexOf("CASPER • 3"));
assert.ok(html.indexOf("CASPER • 3") < html.indexOf("MELCHIOR • 1"));

const dialogHtml = renderToStaticMarkup(
  React.createElement(CoreResponseDialog, { open: true, model, onClose() {} }),
);
assert.match(dialogHtml, /<dialog/);
assert.match(dialogHtml, /aria-label="Close core response"/);
```

Run `npm test` and confirm failure because the component files do not exist.

- [ ] **Step 2: Implement `MagiCoreArray.jsx` with the reference DOM hierarchy**

Render this structure with React JSX and namespaced classes:

```jsx
<div className="magi-system" aria-label="MAGI tri-core decision array">
  <div className="magi-system__stage">
    <ReferenceHeader side="left" title="質問" />
    <ReferenceHeader side="right" title="解決" />
    <SystemDiagnostics elapsedMs={elapsedMs} round={round} phase={phase} />
    <SystemResponse state={systemState} />
    <span className="magi-system__connection magi-system__connection--casper-balthasar" />
    <span className="magi-system__connection magi-system__connection--casper-melchior" />
    <span className="magi-system__connection magi-system__connection--balthasar-melchior" />
    <CoreButton core="BALTHASAR-2" order={2} />
    <CoreButton core="CASPER-3" order={3} />
    <CoreButton core="MELCHIOR-1" order={1} />
    <span className="magi-system__title">MAGI</span>
  </div>
</div>
```

Keep helpers local to the file because they are one-surface render fragments. Each core button calls `onSelectCore(core)` and uses Task 1 state for class names and `aria-label`. Do not include facets, glyphs, confidence, status chips, or the rejected prototype's detail rail inside the polygons.

Diagnostics reuse the reference copy but map dynamic values truthfully:

```text
CODE:473
FILE:MAGI_SYS
PHASE:{phase}
ROUND:{round or 0}
TIME:{mm:ss}
```

- [ ] **Step 3: Implement `CoreResponseDialog.jsx` with native dialog behavior**

Use a `ref` and effect:

```js
if (open && !dialog.open) dialog.showModal();
if (!open && dialog.open) dialog.close();
```

Wire `onCancel` to prevent the browser from bypassing React state, then call `onClose`. Render the reference header and exact five labels: `question:`, `status:`, `error:`, `conditions:`, `full response:`. Use `<button type="button" aria-label="Close core response">X</button>` and return focus to the core button through native dialog behavior.

- [ ] **Step 4: Integrate the components without changing the stream lifecycle**

In `App.jsx`:

```js
const [submittedQuestion, setSubmittedQuestion] = useState("");
const [selectedCore, setSelectedCore] = useState(null);
```

Set `submittedQuestion` from `motion.question` immediately before the fetch. Clear both fields in `handleStartOver`. Replace the `core-grid` / `CorePanel` loop with `MagiCoreArray`. Compute a selected ballot only as:

```js
const revealedBallot = session.result
  ? session.ballots?.find((ballot) => ballot.core === selectedCore) ?? null
  : null;
```

Build the modal model from Task 1 and render one `CoreResponseDialog` after the schematic section. Keep every existing form, status, transcript, result, and footer behavior.

- [ ] **Step 5: Remove the obsolete card component and run unit/build checks**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: tests pass; Vite produces a successful production build; `rg "CorePanel" src` has no matches.

- [ ] **Step 6: Commit the functional port before styling**

```bash
git add frontend/src/App.jsx frontend/src/MagiCoreArray.jsx frontend/src/CoreResponseDialog.jsx frontend/src/magiVisualState.test.js
git rm frontend/src/CorePanel.jsx
git commit -m "feat: port the MAGI core array and response dialog"
```

---

### Task 3: Reproduce the Reference Visual System Across the Frontend

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: Task 2 class names and current semantic section markup.
- Produces: a reference-faithful desktop schematic plus one coherent responsive amber/black application shell.

- [ ] **Step 1: Replace the global tokens and page surface**

Define only these shared visual tokens:

```css
:root {
  --magi-black: #000;
  --magi-stripe: #140b02;
  --magi-amber: #ff8d00;
  --magi-amber-dim: #6e3d00;
  --magi-header-green: #277547;
  --magi-info: #3caee0;
  --magi-agree: #52e691;
  --magi-conditional-alt: #82cd68;
  --magi-disagree: #a41413;
  --magi-mono: "Lucida Console", Monaco, Consolas, monospace;
  --magi-ui: Helvetica, Arial, sans-serif;
  --magi-serif: "Yu Mincho", "Hiragino Mincho ProN", "Times New Roman", serif;
  --magi-line: 2px;
}
```

Use the exact repeating page background, black section surfaces, square controls, amber borders, and visible amber focus outlines. Remove the incumbent gray grid, shadows, rounded cards, muted green palette, and decorative glyph styling.

- [ ] **Step 2: Port the reference grid and clip paths verbatim under namespaced selectors**

Translate the reference `.magi` named grid to `.magi-system__stage` without changing its track ratios. Copy the three clip paths exactly. Use an amber 2px outer polygon with the inner fill inset by 2px, as the source does. Copy the three connector placements and rotations. Preserve `aspect-ratio: 2 / 1` and `container-type: size`.

The visual acceptance points are:

- Balthasar centered at the top.
- Casper and Melchior occupy matching lower halves.
- Polygon notches meet the central `MAGI` block at the same proportions as the screenshot.
- Amber connectors are visible behind the polygons.
- Japanese headers sit between paired green rules.
- Diagnostics occupy the upper-left gap and the response indicator the upper-right gap.

- [ ] **Step 3: Implement exact status fills and safe flicker**

Use class-driven fills:

```css
.magi-system__core--information .magi-system__core-inner,
.magi-system__core--processing .magi-system__core-inner,
.magi-system__core--locked .magi-system__core-inner { background: var(--magi-info); }
.magi-system__core--agree .magi-system__core-inner { background: var(--magi-agree); }
.magi-system__core--disagree .magi-system__core-inner { background: var(--magi-disagree); }
.magi-system__core--conditional .magi-system__core-inner {
  background: repeating-linear-gradient(56deg, var(--magi-agree) 0 30px, var(--magi-conditional-alt) 30px 60px);
}
```

Implement an `800ms infinite step-end` fill-layer flicker. Never animate the text, border, button transform, focus outline, or entire stage. Under `prefers-reduced-motion: reduce`, disable animation and use a stable cyan/black processing hatch.

- [ ] **Step 4: Port the modal styling without copying its layout bugs**

Style `dialog` as black with a 2px amber border, no rounded corners, no default padding, and a striped black/dark-amber title bar. Use a fixed overlay with `max-inline-size: min(60rem, calc(100vw - 2rem))`, `max-block-size: calc(100dvh - 2rem)`, and an independently scrollable body. Style `::backdrop` as mostly opaque black.

At wide widths, the body is `grid-template-columns: max-content minmax(0, 1fr)`. Below 600px, each label/value pair stacks. Apply `overflow-wrap: anywhere` to every value and preserve whitespace in the full response.

- [ ] **Step 5: Retheme the existing simulator controls and records**

Keep the existing content hierarchy but make it visually subordinate to the schematic:

- Motion/context inputs: black fill, 1–2px amber border, amber mono labels, amber submit button.
- Status strip: amber frame and separators, black background, mono values.
- Transcript: one amber-bordered black log, compact amber metadata, white/amber public text; no colored per-core cards.
- Result: amber frame with green/striped/red outcome treatment matching the core states.
- Error: red boundary plus amber mono label; retain the current sanitized text.
- Footer: dim amber mono text and simple separators.

Do not add the reference access-code/question rows. Do not move the current motion form into the schematic.

- [ ] **Step 6: Add responsive rules and run mechanical checks**

At `max-width: 720px`, stack the form and status details. Wrap the schematic in `.magi-system__viewport` with local horizontal scrolling only when its minimum readable width exceeds the viewport. Ensure the document itself remains within the viewport.

Run:

```bash
cd frontend
npm test
npm run build
node /Users/zafir/.codex/plugins/cache/impeccable/impeccable/4.0.2/skills/impeccable/scripts/detect.mjs --json src/App.jsx src/MagiCoreArray.jsx src/CoreResponseDialog.jsx src/styles.css
```

Expected: tests and build pass; detector reports no unresolved critical findings.

- [ ] **Step 7: Commit the visual system**

```bash
git add frontend/src/App.jsx frontend/src/styles.css
git commit -m "style: match the reference MAGI interface"
```

---

### Task 4: Attribute and Verify the Complete Interaction

**Files:**
- Create or Modify: `THIRD_PARTY_NOTICES.md`
- Create: `frontend/scripts/mock-discussion-server.mjs`
- Modify: `frontend/package.json`
- Modify: `docs/superpowers/plans/2026-08-18-magi-sim-lean-mvp.md`
- Test only: frontend files from Tasks 1–3

**Interfaces:**
- Consumes: the completed frontend and current fake/local backend flow.
- Produces: legal attribution, checked lean-plan status, and desktop/mobile visual evidence.

- [ ] **Step 1: Add the full MIT notice and source identification**

`THIRD_PARTY_NOTICES.md` must name:

```text
MAGI by Tomasz Rewak
Source: https://github.com/TomaszRewak/MAGI
Adapted commit: 98a4d0184b1b0013e2216689c770127b6aff2efc
Adapted frontend files: assets/style.css and components/*.js
License: MIT
```

Follow it with the complete license text from the attached repository, including `Copyright (c) 2023 Tomasz Rewak`.

- [ ] **Step 2: Add a deterministic browser-only discussion fixture**

Create `frontend/scripts/mock-discussion-server.mjs` with Node's built-in `http` module. It listens only on `127.0.0.1:8000`, accepts `POST /api/discuss`, and emits a fixed NDJSON sequence with short delays: opening phase; three opening acts; discussion phase; three reaction acts; balloting; `ballots_locked`; and a mixed `result` containing `AGREE`, `CONDITIONAL`, and `DISAGREE`. If the submitted question contains `[fail]`, emit one sanitized `error` event instead. Handle `SIGINT` by closing the server. Do not import application secrets or provider code.

Add this package script:

```json
"mock:api": "node scripts/mock-discussion-server.mjs"
```

The fixture is development-only verification infrastructure; Vite continues proxying `/api` to `127.0.0.1:8000` and production behavior is unchanged.

- [ ] **Step 3: Start the deterministic fixture and Vite frontend without credentials**

Run in separate terminals:

```bash
cd frontend
npm run mock:api
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Confirm `http://127.0.0.1:5173` loads without console errors. Do not set `DEEPSEEK_API_KEY`, place a provider key in the browser, or copy the reference access-code behavior.

- [ ] **Step 4: Perform one bounded desktop and mobile browser inspection pass**

Capture these states in the first pass:

1. 800x459 schematic at idle, compared side by side with `example_1.png`.
2. 1280x720 whole app at idle.
3. Processing with at least one flickering cyan core.
4. Complete result containing one agreement, one conditional vote, and one disagreement.
5. Stream failure.
6. Core modal with long question, multiple public acts, conditions, and rationale.
7. 390x844 and 320x700 layouts.
8. Reduced-motion mode.

Inspect geometry, amber line continuity, Japanese header placement, color values, clipping, core labels, modal overflow, keyboard focus, and document overflow. Record every defect from the pass before editing.

- [ ] **Step 5: Fix all observed defects in one batch and perform one confirmation pass**

Make only evidence-driven corrections. The confirmation pass repeats desktop idle, mixed final result, modal, 390px mobile, and reduced motion. Stop after the confirmation pass unless a correctness defect remains.

- [ ] **Step 6: Run final automated verification**

```bash
cd frontend
npm test
npm run build
cd ../backend
pytest -q
cd ..
git diff --check
git status --short
```

Expected: frontend tests pass, production build succeeds, all backend tests remain green without backend modifications, diff check is clean, and only intended frontend/docs/notice files are changed.

- [ ] **Step 7: Update the lean plan and commit the verified port**

Add a checked frontend fidelity sub-item under lean MVP Task 4 that links to this plan and records the exact reference commit. Do not mark Task 5 complete.

```bash
git add THIRD_PARTY_NOTICES.md frontend docs/superpowers/plans/2026-08-18-magi-sim-lean-mvp.md
git commit -m "docs: record the verified MAGI frontend port"
```

---

## Acceptance Checklist

- [ ] The schematic is recognizably the supplied UI at first glance, not an inspired reinterpretation.
- [ ] Its three polygon shapes and positions match the reference clip paths and 2:1 grid.
- [ ] Japanese headers, green line stacks, amber frame/connectors, diagnostic block, response box, and `MAGI` center are present.
- [ ] Cyan, green, striped conditional, red, and error states derive only from current public session data.
- [ ] Processing visibly flickers; reduced motion remains clear without flicker.
- [ ] Clicking or keyboard-activating any core opens the reference-style modal.
- [ ] Modal question, status, error, conditions, public acts, and revealed rationale are truthful and wrap safely.
- [ ] No ballot detail appears before the final result.
- [ ] No private reasoning can enter the frontend view model.
- [ ] The original access-code/question rows are absent.
- [ ] The current motion/context form, live discussion transcript, result, start-over, and errors still work.
- [ ] The backend and protocol are unchanged.
- [ ] 320px, 390px, tablet, and desktop layouts are usable without document overflow.
- [ ] Full MIT attribution is present.
- [ ] Frontend tests/build, backend tests, browser verification, and `git diff --check` pass.
