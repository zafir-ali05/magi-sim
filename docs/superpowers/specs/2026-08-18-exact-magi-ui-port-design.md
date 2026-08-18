# Exact MAGI Frontend Port Design

**Date:** 2026-08-18

**Status:** Implemented and browser-verified

**Reference implementation:** Tomasz Rewak, `MAGI`, commit `98a4d0184b1b0013e2216689c770127b6aff2efc` (MIT)

## Purpose

Replace the current generic operational-console presentation with a faithful React/Vite port of the supplied MAGI frontend. The three-core array, Japanese headers, amber framing, status colors, processing flicker, and response modal should visually match the supplied screenshots and GIFs. The existing MAGI simulator backend, NDJSON protocol, deliberation flow, motion form, shared transcript, result, privacy boundaries, and error handling remain in place.

This is a frontend port, not a port of the reference repository's Python, Dash, OpenAI, or access-code behavior.

## Source of Truth

Visual and structural decisions come from these files in `MAGI-master.zip`:

- `assets/style.css`
- `components/header.js`
- `components/magi.js`
- `components/modal.js`
- `components/response.js`
- `components/status.js`
- `components/wise_man.js`
- `examples/example_1.gif`
- `examples/example_2.gif`

The screenshots supplied with this request are the acceptance reference. Existing frontend styling is not a visual authority. Existing frontend behavior and data contracts are authoritative.

## Scope Boundary

### In scope

- Port the reference `.system` shell, diagonal black/dark-amber page background, double amber borders, green header rules, Japanese `質問` and `解決` headers, diagnostic block, tri-core grid, connectors, central `MAGI` label, response indicator, status colors, and striped conditional state.
- Port the response modal's striped title bar, amber frame, close control, two-column labels, and full-response layout.
- Replace the current three `CorePanel` cards with the ported tri-core schematic.
- Restyle the current motion form, live status, transcript, result, errors, and footer into the same black/amber terminal visual language.
- Preserve keyboard operation, focus visibility, screen-reader labels, long-text wrapping, responsive layout, and reduced-motion behavior.
- Include the reference project's complete MIT license notice.

### Out of scope

- No backend changes.
- No changes to `/api/discuss`, NDJSON events, prompts, DeepSeek settings, or decision logic.
- No reference access-code field, API-key field, or bottom `question:` field.
- No Dash custom components or Python callbacks.
- No new component library, animation library, state library, or font download.
- No private `reasoning_content`, hidden ballots, or provider details in the UI.

## Visual Contract

### Shell and typography

- Page background: `repeating-linear-gradient(45deg, #000 0 20px, #140b02 20px 40px)`.
- Main surfaces: solid black.
- Primary line and text color: `#ff8d00`.
- Header rule color: `#277547`.
- Information cyan: `#3caee0`.
- Agreement green: `#52e691`.
- Rejection red: `#a41413`.
- Conditional stripe pair: `rgb(82 230 145)` and `#82cd68`, at the reference 56-degree angle.
- Core and compact interface labels use a local system stack headed by `Helvetica`, then `Arial`, then sans-serif.
- Diagnostics, transcript metadata, form labels, and modal fields use `"Lucida Console"`, Monaco, Consolas, monospace.
- Japanese headers and the central `MAGI` wordmark use a bold Japanese-capable serif fallback stack: `"Yu Mincho"`, `"Hiragino Mincho ProN"`, `"Times New Roman"`, serif. No remote font request is introduced.
- Corners stay square. Borders are predominantly 2px. The port does not add gradients, shadows, cards, pills, glass, rounded corners, or decorative icons absent from the reference.

### Exact tri-core geometry

The schematic keeps the reference 2:1 aspect ratio and named CSS-grid structure. These clip paths are copied without reinterpretation:

```css
.melchior,
.melchior > .inner {
  clip-path: polygon(35% 0, 100% 0, 100% 100%, 0 100%, 0 44%);
}

.balthasar,
.balthasar > .inner {
  clip-path: polygon(0 0, 100% 0, 100% 80%, 75% 100%, 25% 100%, 0 80%);
}

.casper,
.casper > .inner {
  clip-path: polygon(0 0, 65% 0, 100% 44%, 100% 100%, 0 100%);
}
```

The core order and labels are exactly:

- top: `BALTHASAR • 2`
- lower left: `CASPER • 3`
- lower right: `MELCHIOR • 1`

Amber connection bars retain the reference horizontal base and approximately `-54deg` / `54deg` diagonals. The stage retains its border, internal 20px gutters at the reference size, and central amber `MAGI` label.

### Responsive treatment

- At desktop and tablet widths, the schematic preserves the 2:1 layout and reference proportions.
- It scales down using container query units as the reference does, with a minimum readable label size.
- Below the width at which the 2:1 schematic is readable, the stage remains 2:1 inside a horizontally scrollable viewport rather than rearranging the core topology. This preserves the recognizable geometry.
- The surrounding form, status details, transcript, and result collapse to one column on small screens.
- The page must not cause document-level horizontal overflow at 320px, 390px, or 768px.

## State Mapping

`frontend/src/magiVisualState.js` is the only place that translates existing session data into reference visual states.

| Simulator state | Core fill | Japanese response | Flicker |
| --- | --- | --- | --- |
| idle / no public act | cyan `#3caee0` | `情 報` | no |
| connecting or core active | cyan `#3caee0` | `情 報` | yes |
| public act committed, core inactive | cyan `#3caee0` | `情 報` | no |
| ballots locked but not revealed | cyan `#3caee0` | `情 報` | yes |
| `AGREE` | green `#52e691` | `合 意` | no |
| `CONDITIONAL` | green diagonal stripes | `状 態` | no |
| `DISAGREE` | red `#a41413` | `拒 絶` | no |
| failed stream | black with visible red/amber boundary | `誤 差` | no |

The central response indicator uses the reference label/color pair. Individual final ballot colors take precedence once the `result` event exists. Before the result exists, no ballot content is placed in component props or modal data.

The reference's 0.25-second on/off animation is visually reproduced as a hard `step-end` state flicker but slowed to an 800ms cycle, yielding fewer than three flashes per second. `prefers-reduced-motion: reduce` disables it and shows a stable high-contrast processing hatch. The animation changes the fill layer only; core text, focus outlines, and borders remain readable.

## Component Design

### `MagiCoreArray.jsx`

Owns the reference header, diagnostics, status indicator, connectors, three polygon buttons, and central title. It receives already-public simulator state and emits only `onSelectCore(coreId)`.

```js
MagiCoreArray({
  phase,
  sessionStatus,
  activeCores,
  acts,
  ballots,
  ballotsLocked,
  result,
  elapsedMs,
  round,
  onSelectCore,
})
```

The core polygons are semantic `<button type="button">` elements styled with the reference geometry. They expose a readable name and state through `aria-label`. Selecting a core opens its response modal.

### `CoreResponseDialog.jsx`

Ports the modal appearance while using the native `<dialog>` element for focus handling, Escape-to-close, and overlay positioning. It is rendered at the app shell level so it cannot be clipped by the schematic's overflow rules.

Fields map as follows:

- `question:` the submitted motion text captured when the current run begins.
- `status:` the selected core's public visual state in lowercase English.
- `error:` the sanitized session error when failed; otherwise an em dash.
- `conditions:` the selected core's revealed ballot conditions, joined as readable lines; otherwise an em dash.
- `full response:` every committed public act from the selected core, in stream order, followed by its revealed ballot rationale after the result. Before a public act exists, show `Waiting for public response...`.

The dialog never receives or renders private reasoning. It receives no ballot until `session.result` exists. While a ballot is locked but unrevealed, it shows `Vote sealed until all cores report.` rather than inferred ballot content.

### `magiVisualState.js`

Contains pure functions:

```js
getCoreVisualState({ core, phase, sessionStatus, activeCores, acts, ballot, ballotsLocked })
getSystemVisualState({ phase, sessionStatus, ballotsLocked, result })
buildCoreDialogModel({ core, question, phase, sessionStatus, acts, ballot, ballotsLocked, error })
```

This module owns the status vocabulary, color keys, Japanese labels, latest/public act filtering, and modal text construction. Pure tests cover all phase and ballot combinations and privacy rules.

### `App.jsx`

Keeps the current stream parsing, request lifecycle, timer, form, transcript, result, and error behavior. It adds:

- `submittedQuestion`, captured from the trimmed motion when a request begins;
- `selectedCore`, initially `null`;
- the ported `MagiCoreArray` in the existing core-array section;
- one `CoreResponseDialog` driven by `selectedCore`.

The motion form remains part of this simulator but is not placed inside the reference schematic. The reference repository's access-code and question rows are not copied.

### `styles.css`

Replaces the current gray/green console theme with one coherent reference-derived theme. Reference-specific selectors are namespaced beneath `.magi-system` to prevent generic names such as `.header`, `.title`, `.response`, and `.modal` from leaking into the rest of the app. Shared tokens are limited to values used across at least three areas: amber, cyan, green, red, black, muted amber, header green, mono stack, and border width.

## Existing Simulator Sections

The surrounding application remains functionally recognizable:

1. Motion and optional context form.
2. Live phase, elapsed time, active cores, round, and remaining rounds.
3. Exact reference tri-core schematic.
4. Shared public transcript.
5. Simultaneous ballot result and aggregate conditions.

Every section uses amber framing and black surfaces. The tri-core schematic is the dominant visual element; the rest of the interface supports it without adding a competing card system.

## Errors and Edge Cases

- Stream errors keep the current sanitized message and also put the core array into the reference error state.
- Closing the dialog does not reset the session or selected core data.
- Starting over closes the dialog and clears `submittedQuestion`.
- A selected core continues updating while its dialog is open as new public acts arrive.
- Long questions, acts, rationales, conditions, and single unbroken tokens wrap without enlarging the viewport.
- Duplicate React keys are avoided by using event IDs and condition indexes where necessary.
- Core buttons remain operable while processing; users may inspect the public output committed so far.

## Verification Contract

Automated checks:

- Existing `events` and `session` tests stay green.
- Pure state tests cover standby, active, committed, locked, all three votes, result outcomes, and failure precedence.
- Dialog-model tests prove that unrevealed ballots and `reasoning_content` cannot appear.
- Frontend production build succeeds.

Browser checks use deterministic mocked NDJSON streams and cover:

- 800x459 reference-size schematic comparison.
- 1280x720 full application.
- 390x844 and 320x700 responsive layouts with no document overflow.
- Initial cyan state.
- Processing flicker and reduced-motion fallback.
- `AGREE`, `CONDITIONAL`, and `DISAGREE` color states.
- Error state.
- Dialog open by pointer and keyboard, Escape close, close-button focus, and long-content wrapping.
- Existing form submission, transcript growth, simultaneous ballot reveal, start-over, and sanitized stream failure.

Pixel-for-pixel identity is expected for the schematic's geometry, borders, palette, and visual hierarchy at the reference aspect ratio. Differences are intentional only where this simulator has different data, where removed reference inputs leave space, or where accessibility and responsive safety require them.

## Attribution

`THIRD_PARTY_NOTICES.md` will include the full MIT license and identify the adapted source files and commit. No source code from the reference backend is copied.
