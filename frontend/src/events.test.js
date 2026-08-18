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
      round: 0,
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
