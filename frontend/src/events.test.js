import test from "node:test";
import assert from "node:assert/strict";

import { parseNdjsonChunk, parseStreamEvent } from "./events.js";

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
  const result = parseStreamEvent({
    type: "result",
    outcome: "APPROVED_WITH_CONDITIONS",
    ballots: [
      {
        core: "MELCHIOR-1",
        vote: "AGREE",
        confidence: 0.8,
        rationale: "The evidence supports proceeding.",
        conditions: [],
      },
      {
        core: "BALTHASAR-2",
        vote: "CONDITIONAL",
        confidence: 0.65,
        rationale: "Proceed with a reversible safeguard.",
        conditions: ["Keep the affected group informed."],
      },
      {
        core: "CASPER-3",
        vote: "AGREE",
        confidence: 0.7,
        rationale: "The incentives remain aligned.",
        conditions: [],
      },
    ],
    conditions: ["Keep the affected group informed."],
    disclaimer: "Decision support only.",
  });
  assert.equal(result.ballots.length, 3);
  assert.deepEqual(parseStreamEvent({ type: "error", message: "Deliberation failed." }), {
    type: "error",
    message: "Deliberation failed.",
  });
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
      parseStreamEvent({
        type: "result",
        outcome: "APPROVED",
        ballots: [
          {
            core: "MELCHIOR-1",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "x".repeat(2001),
            conditions: [],
          },
          {
            core: "BALTHASAR-2",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "A valid rationale.",
            conditions: [],
          },
          {
            core: "CASPER-3",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "A valid rationale.",
            conditions: [],
          },
        ],
        conditions: [],
        disclaimer: "Decision support only.",
      }),
    /rationale.*2000/i,
  );
  assert.throws(
    () =>
      parseStreamEvent({
        type: "result",
        outcome: "APPROVED",
        ballots: [
          {
            core: "MELCHIOR-1",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "A valid rationale.",
            conditions: [],
          },
          {
            core: "BALTHASAR-2",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "A valid rationale.",
            conditions: [],
          },
          {
            core: "CASPER-3",
            vote: "AGREE",
            confidence: 0.8,
            rationale: "A valid rationale.",
            conditions: [
              "condition 1",
              "condition 2",
              "condition 3",
              "condition 4",
              "condition 5",
              "condition 6",
              "condition 7",
              "condition 8",
              "condition 9",
            ],
          },
        ],
        conditions: [],
        disclaimer: "Decision support only.",
      }),
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
        type: "core_status",
        core: "CASPER-3",
        status: "PRIVATE_REASONING",
        reviewed_through_event_id: 3,
      }),
    /status/i,
  );
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
