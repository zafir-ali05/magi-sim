import test from "node:test";
import assert from "node:assert/strict";

import {
  buildCoreDialogModel,
  getCoreVisualState,
  getSystemVisualState,
} from "./magiVisualState.js";

const CORE = "CASPER-3";

function coreState(overrides = {}) {
  return {
    core: CORE,
    phase: "STANDBY",
    sessionStatus: "idle",
    activeCores: [],
    acts: [],
    ballot: null,
    ballotsLocked: false,
    ...overrides,
  };
}

test("maps public session phases to stable and processing information states", () => {
  assert.deepEqual(getCoreVisualState(coreState()), {
    key: "information",
    english: "INFORMATION",
    japanese: "情 報",
    flicker: false,
  });

  assert.deepEqual(
    getCoreVisualState(coreState({ phase: "CONNECTING", sessionStatus: "running" })),
    {
      key: "processing",
      english: "PROCESSING",
      japanese: "情 報",
      flicker: true,
    },
  );

  assert.equal(
    getCoreVisualState(
      coreState({
        phase: "DISCUSSION",
        sessionStatus: "running",
        activeCores: [CORE],
      }),
    ).key,
    "processing",
  );

  assert.equal(
    getCoreVisualState(
      coreState({
        phase: "DISCUSSION",
        sessionStatus: "running",
        activeCores: [],
        acts: [
          {
            id: 1,
            round: 0,
            act: { core: CORE, kind: "POSITION", content: "A public position." },
          },
        ],
      }),
    ).key,
    "information",
  );
});

test("keeps locked ballots concealed behind the processing information state", () => {
  assert.deepEqual(
    getCoreVisualState(coreState({ phase: "BALLOTING", sessionStatus: "running", ballotsLocked: true })),
    {
      key: "locked",
      english: "VOTE SEALED",
      japanese: "情 報",
      flicker: true,
    },
  );
});

test("maps each revealed ballot to the matching reference state", () => {
  const cases = [
    ["AGREE", "agree", "AGREE", "合 意"],
    ["CONDITIONAL", "conditional", "CONDITIONAL", "状 態"],
    ["DISAGREE", "disagree", "DISAGREE", "拒 絶"],
  ];

  for (const [vote, key, english, japanese] of cases) {
    assert.deepEqual(
      getCoreVisualState(coreState({ sessionStatus: "complete", phase: "COMPLETE", ballot: { vote } })),
      { key, english, japanese, flicker: false },
    );
  }
});

test("a stream failure takes visual precedence over a revealed ballot", () => {
  assert.deepEqual(
    getCoreVisualState(
      coreState({
        sessionStatus: "error",
        phase: "FAILED",
        ballot: { vote: "AGREE" },
      }),
    ),
    { key: "error", english: "ERROR", japanese: "誤 差", flicker: false },
  );
});

test("maps the system indicator from phase and final outcome", () => {
  assert.deepEqual(getSystemVisualState({}), {
    key: "information",
    english: "INFORMATION",
    japanese: "情 報",
  });
  assert.equal(
    getSystemVisualState({ phase: "DISCUSSION", sessionStatus: "running" }).key,
    "processing",
  );
  assert.equal(
    getSystemVisualState({ phase: "BALLOTING", sessionStatus: "running", ballotsLocked: true }).key,
    "locked",
  );
  assert.equal(getSystemVisualState({ result: { outcome: "APPROVED" } }).key, "agree");
  assert.equal(
    getSystemVisualState({ result: { outcome: "APPROVED_WITH_CONDITIONS" } }).key,
    "conditional",
  );
  assert.equal(getSystemVisualState({ result: { outcome: "REJECTED" } }).key, "disagree");
  assert.equal(getSystemVisualState({ phase: "FAILED", sessionStatus: "error" }).key, "error");
});

test("builds a locked dialog from public acts without leaking private fields", () => {
  const model = buildCoreDialogModel({
    core: CORE,
    question: "Should the proposal proceed?",
    phase: "BALLOTING",
    sessionStatus: "running",
    acts: [
      {
        id: 4,
        round: 1,
        act: {
          core: CORE,
          kind: "CHALLENGE",
          content: "Public objection.",
          reasoning_content: "private act reasoning",
        },
        reasoning_content: "private event reasoning",
      },
      {
        id: 5,
        round: 1,
        act: { core: "MELCHIOR-1", kind: "RESPONSE", content: "Another core." },
      },
    ],
    ballot: null,
    ballotsLocked: true,
    error: "",
  });

  assert.deepEqual(model, {
    title: "casper",
    question: "Should the proposal proceed?",
    status: "vote sealed",
    error: "—",
    conditions: "—",
    fullResponse: "R1 CHALLENGE: Public objection.\n\nVote sealed until all cores report.",
    ballotLocked: true,
  });
  assert.doesNotMatch(JSON.stringify(model), /private act reasoning|private event reasoning|reasoning_content/);
});

test("adds only a revealed ballot's public rationale and conditions", () => {
  const model = buildCoreDialogModel({
    core: CORE,
    question: "Proceed?",
    phase: "COMPLETE",
    sessionStatus: "complete",
    acts: [
      {
        id: 1,
        round: 0,
        act: { core: CORE, kind: "POSITION", content: "Proceed cautiously." },
      },
    ],
    ballot: {
      vote: "CONDITIONAL",
      confidence: 0.72,
      rationale: "Proceed if the safeguards remain reversible.",
      conditions: ["Publish the review.", "Retain a rollback path."],
      reasoning_content: "private ballot reasoning",
    },
    ballotsLocked: true,
    error: "",
  });

  assert.equal(model.status, "conditional");
  assert.equal(model.conditions, "Publish the review.\nRetain a rollback path.");
  assert.equal(
    model.fullResponse,
    "R0 POSITION: Proceed cautiously.\n\nFINAL RATIONALE: Proceed if the safeguards remain reversible.",
  );
  assert.doesNotMatch(JSON.stringify(model), /private ballot reasoning|reasoning_content/);
});

test("uses explicit waiting and sanitized failure copy for empty dialogs", () => {
  const waiting = buildCoreDialogModel({ core: "BALTHASAR-2", question: "Proceed?" });
  assert.equal(waiting.title, "balthasar");
  assert.equal(waiting.fullResponse, "Waiting for public response...");

  const failed = buildCoreDialogModel({
    core: "MELCHIOR-1",
    question: "Proceed?",
    phase: "FAILED",
    sessionStatus: "error",
    error: "Connection error: HTTP 503",
  });
  assert.equal(failed.status, "error");
  assert.equal(failed.error, "Connection error: HTTP 503");
});
