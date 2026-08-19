import test from "node:test";
import assert from "node:assert/strict";

import { parseNdjsonChunk, parseStreamEvent } from "./events.js";

const CORES = ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"];

function validBallot(core, overrides = {}) {
  return {
    core,
    vote: "AGREE",
    confidence: 0.8,
    rationale: "A valid rationale.",
    conditions: [],
    ...overrides,
  };
}

function validResult(overrides = {}) {
  return {
    type: "result",
    quorum: "majority",
    recommendation: "APPROVED",
    outcome: "APPROVED",
    requires_human_confirmation: false,
    ballots: CORES.map((core) => validBallot(core)),
    conditions: [],
    disclaimer: "Decision support only.",
    ...overrides,
  };
}

test("parseStreamEvent accepts the public phase event", () => {
  assert.deepEqual(
    parseStreamEvent({
      type: "phase",
      phase: "DISCUSSION",
      active_cores: ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"],
    }),
    {
      type: "phase",
      phase: "DISCUSSION",
      active_cores: ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"],
    },
  );
});

test("parseStreamEvent rejects unknown and malformed events", () => {
  assert.throws(
    () => parseStreamEvent({ type: "telemetry", payload: "private" }),
    /unknown event type/i,
  );
  assert.throws(
    () => parseStreamEvent({ type: "phase", phase: "DISCUSSION" }),
    /active_cores/i,
  );
});

test("parseStreamEvent accepts acts, ballot lock, result, and error events", () => {
  assert.deepEqual(
    parseStreamEvent({
      type: "act",
      id: 1,
      seen_through_event_id: 0,
      act: {
        core: "MELCHIOR-1",
        kind: "POSITION",
        content: "The evidence is sufficient to compare both options.",
        reply_to: null,
      },
    }).act,
    {
      core: "MELCHIOR-1",
      kind: "POSITION",
      content: "The evidence is sufficient to compare both options.",
      reply_to: null,
    },
  );
  assert.deepEqual(
    parseStreamEvent({
      type: "core_status",
      core: "CASPER-3",
      status: "THINKING",
      reviewed_through_event_id: 3,
    }),
    {
      type: "core_status",
      core: "CASPER-3",
      status: "THINKING",
      reviewed_through_event_id: 3,
    },
  );
  assert.deepEqual(parseStreamEvent({ type: "ballots_locked" }), { type: "ballots_locked" });
  const result = parseStreamEvent(validResult({
    recommendation: "APPROVED_WITH_CONDITIONS",
    outcome: "APPROVED_WITH_CONDITIONS",
    ballots: [
      validBallot("MELCHIOR-1", { rationale: "The evidence supports proceeding." }),
      validBallot("BALTHASAR-2", {
        vote: "CONDITIONAL",
        confidence: 0.65,
        rationale: "Proceed with a reversible safeguard.",
        conditions: ["Keep the affected group informed."],
      }),
      validBallot("CASPER-3", {
        confidence: 0.7,
        rationale: "The incentives remain aligned.",
      }),
    ],
    conditions: ["Keep the affected group informed."],
  }));
  assert.equal(result.ballots.length, 3);
  assert.equal(result.quorum, "majority");
  assert.equal(result.recommendation, "APPROVED_WITH_CONDITIONS");
  assert.equal(result.requires_human_confirmation, false);
  assert.deepEqual(parseStreamEvent({ type: "error", message: "Deliberation failed." }), {
    type: "error",
    message: "Deliberation failed.",
  });
});

test("parseStreamEvent rejects review control outcomes as public acts", () => {
  for (const kind of ["READY", "PASS"]) {
    assert.throws(
      () =>
        parseStreamEvent({
          type: "act",
          id: 4,
          seen_through_event_id: 3,
          act: {
            core: "CASPER-3",
            kind,
            content: "No public contribution.",
            reply_to: null,
          },
        }),
      /act\.kind/i,
    );
  }
});

test("parseStreamEvent rejects unsupported top-level and nested keys", () => {
  assert.throws(
    () =>
      parseStreamEvent({
        type: "phase",
        phase: "DISCUSSION",
        active_cores: ["MELCHIOR-1"],
        private_trace: "reasoning",
      }),
    /unsupported field/i,
  );
  assert.throws(
    () =>
      parseStreamEvent({
        type: "act",
        id: 1,
        seen_through_event_id: 0,
        act: {
          core: "MELCHIOR-1",
          kind: "POSITION",
          content: "A bounded public statement.",
          reply_to: null,
          reasoning_content: "hidden reasoning",
        },
      }),
    /unsupported field/i,
  );
  assert.throws(
    () => parseStreamEvent({ type: "ballots_locked", extra: true }),
    /unsupported field/i,
  );
  assert.throws(
    () => parseStreamEvent({ type: "error", message: "failed", secret: "hidden" }),
    /unsupported field/i,
  );

  const privateBallotResult = validResult({
    ballots: [
      validBallot("MELCHIOR-1", {
        reasoning_content: "private ballot reasoning",
      }),
      validBallot("BALTHASAR-2"),
      validBallot("CASPER-3"),
    ],
  });
  assert.throws(() => parseStreamEvent(privateBallotResult), /unsupported field/i);
});

test("parseStreamEvent mirrors public content and ballot condition bounds", () => {
  assert.throws(
    () =>
      parseStreamEvent({
        type: "act",
        id: 1,
        seen_through_event_id: 0,
        act: {
          core: "MELCHIOR-1",
          kind: "POSITION",
          content: "x".repeat(2001),
          reply_to: null,
        },
      }),
    /content.*2000/i,
  );
  assert.throws(
    () =>
      parseStreamEvent(validResult({
        ballots: [
          validBallot("MELCHIOR-1", { rationale: "x".repeat(2001) }),
          validBallot("BALTHASAR-2"),
          validBallot("CASPER-3"),
        ],
      })),
    /rationale.*2000/i,
  );
  assert.throws(
    () =>
      parseStreamEvent(validResult({
        ballots: [
          validBallot("MELCHIOR-1"),
          validBallot("BALTHASAR-2"),
          validBallot("CASPER-3", {
            conditions: Array.from({ length: 9 }, (_, index) => `condition ${index + 1}`),
          }),
        ],
      })),
    /conditions.*8/i,
  );
});

test("parseStreamEvent rejects invalid causal and core status fields", () => {
  assert.throws(
    () =>
      parseStreamEvent({
        type: "act",
        id: 1,
        seen_through_event_id: -1,
        act: {
          core: "MELCHIOR-1",
          kind: "POSITION",
          content: "A public position.",
          reply_to: null,
        },
      }),
    /seen_through_event_id/i,
  );
  assert.throws(
    () =>
      parseStreamEvent({
        type: "act",
        id: 4,
        seen_through_event_id: 3,
        act: {
          core: "CASPER-3",
          kind: "CHALLENGE",
          content: "Invalid future reference.",
          reply_to: 4,
        },
      }),
    /reply_to/i,
  );
  assert.throws(
    () =>
      parseStreamEvent({
        type: "core_status",
        core: "CASPER-3",
        status: "PRIVATE_REASONING",
        reviewed_through_event_id: 3,
      }),
    /status/i,
  );
});

test("parseStreamEvent rejects invalid decision policy fields", () => {
  const result = validResult();

  assert.throws(() => parseStreamEvent({ ...result, quorum: "plurality" }), /quorum/i);
  assert.throws(
    () => parseStreamEvent({ ...result, recommendation: "MAYBE" }),
    /recommendation/i,
  );
  assert.throws(
    () => parseStreamEvent({ ...result, outcome: "EXECUTED" }),
    /outcome/i,
  );
  assert.throws(
    () => parseStreamEvent({ ...result, requires_human_confirmation: "no" }),
    /requires_human_confirmation/i,
  );
});

test("parseStreamEvent accepts an incomplete result without revealing partial ballots", () => {
  const result = parseStreamEvent({
    type: "result",
    quorum: "unanimous",
    recommendation: "INCOMPLETE",
    outcome: "INCOMPLETE",
    requires_human_confirmation: true,
    ballots: [],
    conditions: [],
    disclaimer: "Decision support only.",
  });

  assert.deepEqual(result.ballots, []);
  assert.equal(result.outcome, "INCOMPLETE");
});

test("unknown event errors do not echo an untrusted type value", () => {
  assert.throws(
    () => parseStreamEvent({ type: "PRIVATE_REASONING_PAYLOAD" }),
    (error) =>
      /unknown event type/i.test(error.message) &&
      !error.message.includes("PRIVATE_REASONING_PAYLOAD"),
  );
});

test("parseNdjsonChunk retains an incomplete trailing line", () => {
  const first = parseNdjsonChunk("", '{"type":"phase"}\n{"type":"act"');
  assert.deepEqual(first.lines, ['{"type":"phase"}']);
  assert.equal(first.remainder, '{"type":"act"');

  const second = parseNdjsonChunk(first.remainder, "," + "\"id\":1}\n");
  assert.deepEqual(second.lines, ['{"type":"act","id":1}']);
  assert.equal(second.remainder, "");
});

test("parseNdjsonChunk leaves a final unterminated line for the caller", () => {
  const result = parseNdjsonChunk("", '{"type":"error","message":"wait"}');
  assert.deepEqual(result.lines, []);
  assert.equal(result.remainder, '{"type":"error","message":"wait"}');
});
