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
    speakingCore: null,
    coreStatus: { status: "LISTENING", reviewedThroughEventId: 0 },
    ...overrides,
  };
}

test("maps only the current public speaker to processing during discussion", () => {
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
      flicker: false,
    },
  );

  assert.deepEqual(
    getCoreVisualState(
      coreState({
        phase: "DISCUSSION",
        sessionStatus: "running",
        activeCores: [CORE],
        speakingCore: CORE,
      }),
    ),
    { key: "processing", english: "SPEAKING", japanese: "情 報", flicker: false },
  );

  assert.deepEqual(
    getCoreVisualState(
      coreState({
        phase: "DISCUSSION",
        sessionStatus: "running",
        activeCores: [CORE],
        speakingCore: "MELCHIOR-1",
      }),
    ),
    { key: "listening", english: "LISTENING", japanese: "情 報", flicker: false },
  );
});

test("maps backend review statuses without treating readiness as agreement", () => {
  const cases = [
    ["THINKING", "thinking", "ANALYZING"],
    ["LISTENING", "listening", "LISTENING"],
    ["READY", "ready", "READY"],
    ["BUDGET_EXHAUSTED", "bounded", "REVIEW BOUNDED"],
    ["FAILED", "error", "ERROR"],
  ];

  for (const [status, key, english] of cases) {
    const state = getCoreVisualState(
      coreState({
        phase: "DISCUSSION",
        sessionStatus: "running",
        coreStatus: { status, reviewedThroughEventId: 4 },
      }),
    );
    assert.equal(state.key, key);
    assert.equal(state.english, english);
  }

  const ready = getCoreVisualState(
    coreState({
      phase: "DISCUSSION",
      sessionStatus: "running",
      coreStatus: { status: "READY", reviewedThroughEventId: 4 },
    }),
  );
  assert.notEqual(ready.key, "agree");
});

test("keeps locked ballots concealed behind the processing information state", () => {
  assert.deepEqual(
    getCoreVisualState(coreState({ phase: "BALLOTING", sessionStatus: "running", ballotsLocked: true })),
    {
      key: "locked",
      english: "VOTE SEALED",
      japanese: "情 報",
      flicker: false,
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
  assert.equal(
    getSystemVisualState({ result: { outcome: "HUMAN_CONFIRMATION_REQUIRED" } }).key,
    "conditional",
  );
  assert.equal(getSystemVisualState({ result: { outcome: "INCOMPLETE" } }).key, "error");
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
        seen_through_event_id: 3,
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
        seen_through_event_id: 4,
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
    fullResponse: "SEEN 3 CHALLENGE: Public objection.\n\nVote sealed until all cores report.",
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
        seen_through_event_id: 0,
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
    "SEEN 0 POSITION: Proceed cautiously.\n\nFINAL RATIONALE: Proceed if the safeguards remain reversible.",
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

test("labels the currently presented core as speaking in its response dialog", () => {
  const speaking = buildCoreDialogModel({
    core: CORE,
    question: "Proceed?",
    phase: "DISCUSSION",
    sessionStatus: "running",
    speakingCore: CORE,
  });

  assert.equal(speaking.status, "speaking");
});
