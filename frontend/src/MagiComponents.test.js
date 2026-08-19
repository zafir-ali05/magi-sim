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
      activeCores: [],
      acts: [],
      ballots: null,
      ballotsLocked: false,
      result: null,
      elapsedMs: 0,
      round: 0,
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
  assert.match(html, /MAGI/);
  assert.equal((html.match(/<button/g) ?? []).length, 3);

  const balthasar = html.indexOf("BALTHASAR • 2");
  const casper = html.indexOf("CASPER • 3");
  const melchior = html.indexOf("MELCHIOR • 1");
  assert.ok(balthasar > -1 && casper > balthasar && melchior > casper);
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
    activeCores: ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"],
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

test("renders the reference modal fields and an accessible close control", () => {
  const html = renderToStaticMarkup(
    React.createElement(CoreResponseDialog, {
      open: true,
      model: {
        title: "casper",
        question: "Is 3 > 2?",
        status: "agree",
        error: "—",
        conditions: "Retain oversight.",
        fullResponse: "R0 POSITION: Yes.\n\nFINAL RATIONALE: Simple math, but important.",
        ballotLocked: false,
      },
      onClose() {},
    }),
  );

  assert.match(html, /<dialog/);
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
});
