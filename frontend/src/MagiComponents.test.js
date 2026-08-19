import test, { after } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const vite = await createServer({
  root: new URL("..", import.meta.url).pathname,
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});
const { CoreResponseDialog } = await vite.ssrLoadModule("/src/CoreResponseDialog.jsx");
const { MagiCoreArray } = await vite.ssrLoadModule("/src/MagiCoreArray.jsx");
const { default: App } = await vite.ssrLoadModule("/src/App.jsx");

after(async () => {
  await vite.close();
});

function renderArray(overrides = {}) {
  return renderToStaticMarkup(
    React.createElement(MagiCoreArray, {
      phase: "STANDBY",
      sessionStatus: "idle",
      coreStatuses: {},
      ballots: null,
      ballotsLocked: false,
      result: null,
      elapsedMs: 0,
      latestEventId: 0,
      onSelectCore() {},
      ...overrides,
    }),
  );
}

test("renders the reference headers and three polygon cores in canonical visual order", () => {
  const html = renderArray();

  assert.match(html, /質問/);
  assert.match(html, /解決/);
  assert.match(html, /CODE:473/);
  assert.match(html, /FILE:MAGI_SYS/);
  assert.match(html, /VERSION:0/);
  assert.doesNotMatch(html, /ROUND:/);
  assert.match(html, /MAGI/);
  assert.equal((html.match(/<button/g) ?? []).length, 3);

  const balthasar = html.indexOf("BALTHASAR • 2");
  const casper = html.indexOf("CASPER • 3");
  const melchior = html.indexOf("MELCHIOR • 1");
  assert.ok(balthasar > -1 && casper > balthasar && melchior > casper);
});

test("gives every core a status tooltip and accessible click instruction", () => {
  const html = renderArray();

  assert.equal((html.match(/title="Click for status"/g) ?? []).length, 3);
  assert.equal((html.match(/aria-label="[^"]*Click for status"/g) ?? []).length, 3);
});

test("does not apply a ballot color until a public result exists", () => {
  const ballot = {
    core: "CASPER-3",
    vote: "DISAGREE",
    confidence: 0.8,
    rationale: "Public only after reveal.",
    conditions: [],
  };

  const concealed = renderArray({ ballots: [ballot], ballotsLocked: true, phase: "BALLOTING" });
  assert.doesNotMatch(concealed, /magi-system__core--disagree/);
  assert.match(concealed, /magi-system__core--locked/);

  const revealed = renderArray({
    ballots: [ballot],
    ballotsLocked: true,
    phase: "COMPLETE",
    sessionStatus: "complete",
    result: { outcome: "REJECTED" },
  });
  assert.match(revealed, /magi-system__core--disagree/);
});

test("illuminates only the core whose public discussion act is being presented", () => {
  const html = renderArray({
    phase: "DISCUSSION",
    sessionStatus: "running",
    speakingCore: "MELCHIOR-1",
  });

  assert.equal((html.match(/magi-system__core--speaking/g) ?? []).length, 1);
  assert.match(
    html,
    /magi-system__core--melchior[^"\n]*magi-system__core--processing[^"\n]*magi-system__core--speaking/,
  );
  assert.equal((html.match(/magi-system__core--listening/g) ?? []).length, 2);
  assert.doesNotMatch(html, /magi-system__core--flicker/);
});

test("renders backend core review states without using approval colors for ready", () => {
  const html = renderArray({
    phase: "DISCUSSION",
    sessionStatus: "running",
    coreStatuses: {
      "MELCHIOR-1": { status: "THINKING", reviewedThroughEventId: 3 },
      "BALTHASAR-2": { status: "READY", reviewedThroughEventId: 4 },
      "CASPER-3": { status: "BUDGET_EXHAUSTED", reviewedThroughEventId: 4 },
    },
  });

  assert.match(html, /magi-system__core--melchior[^"\n]*magi-system__core--thinking/);
  assert.match(html, /magi-system__core--balthasar[^"\n]*magi-system__core--ready/);
  assert.match(html, /magi-system__core--casper[^"\n]*magi-system__core--bounded/);
  assert.doesNotMatch(html, /magi-system__core--agree/);
});

test("renders the core response as an open non-modal dialog with an accessible close control", () => {
  const html = renderToStaticMarkup(
    React.createElement(CoreResponseDialog, {
      open: true,
      model: {
        title: "casper",
        question: "Is 3 > 2?",
        status: "agree",
        error: "—",
        conditions: "Retain oversight.",
        fullResponse: "SEEN 0 POSITION: Yes.\n\nFINAL RATIONALE: Simple math, but important.",
      },
      onClose() {},
    }),
  );

  assert.match(html, /<dialog[^>]* open=""/);
  assert.doesNotMatch(html, /aria-modal="true"/);
  assert.match(html, /aria-label="Close core response"/);
  assert.match(html, /question:/);
  assert.match(html, /status:/);
  assert.match(html, /error:/);
  assert.match(html, /conditions:/);
  assert.match(html, /full response:/);
  assert.match(html, /Simple math, but important/);
});

test("uses the reference MAGI array as the application's core display", () => {
  const html = renderToStaticMarkup(React.createElement(App));

  assert.match(html, /class="magi-system"/);
  assert.match(html, /BALTHASAR • 2/);
  assert.doesNotMatch(html, /class="core-grid"/);
  assert.match(html, /LATEST VERSION/);
  assert.doesNotMatch(html, /REMAINING REACTION ROUNDS/);
  assert.doesNotMatch(html, /DECISION POLICY/);
  assert.doesNotMatch(html, /<select/);
});

test("starts with the motion input instead of the console header", () => {
  const html = renderToStaticMarkup(React.createElement(App));

  assert.doesNotMatch(html, /S\.C\. MAGI \/ OPERATIONAL CONSOLE/);
  assert.doesNotMatch(html, /TRI-CORE DECISION SUPPORT/);
  assert.doesNotMatch(html, /LOCAL STREAM/);
  assert.doesNotMatch(html, /PUBLIC TRACE ONLY/);
  assert.match(html, /01 \/ MOTION INPUT/);
});

test("renders one motion input with the deliberation action beside it", () => {
  const html = renderToStaticMarkup(React.createElement(App));

  assert.equal((html.match(/<textarea/g) ?? []).length, 1);
  assert.match(html, /id="motion-question"/);
  assert.doesNotMatch(html, /id="motion-context"/);
  assert.doesNotMatch(html, /name="context"/);
  assert.match(html, /class="form-actions"/);
  assert.match(html, /RUN DELIBERATION/);
});

test("omits the motion note and console footer while retaining input validation", () => {
  const html = renderToStaticMarkup(React.createElement(App));

  assert.doesNotMatch(html, /REQUIRED \/ 3–2,000 CHARACTERS/);
  assert.doesNotMatch(html, /PUBLIC ACTS EXCLUDE PRIVATE REASONING CONTENT/);
  assert.doesNotMatch(html, /NO REAL-WORLD ACTIONS EXECUTED/);
  assert.doesNotMatch(html, /<footer/);
  assert.match(html, /minLength="3"/);
  assert.match(html, /maxLength="2000"/);
  assert.match(html, /required=""/);
});
