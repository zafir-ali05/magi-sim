import test from "node:test";
import assert from "node:assert/strict";

import {
  advanceSpeakerPresentation,
  applyStreamEvent,
  createSession,
} from "./session.js";
import { eventsForMotion } from "../scripts/mock-discussion-server.mjs";
import { parseStreamEvent } from "./events.js";

test("createSession marks a started request active before the first stream event", () => {
  const startedAt = 1234;
  const session = createSession(startedAt);

  assert.equal(session.status, "running");
  assert.equal(session.phase, "CONNECTING");
  assert.equal(session.startedAt, startedAt);
  assert.equal(session.elapsedMs, 0);
  assert.equal("round" in session, false);
});

test("createSession without a request timestamp remains in standby", () => {
  assert.equal(createSession().status, "idle");
});

test("applies backend core status facts by exact core id", () => {
  const session = applyStreamEvent(createSession(1000), {
    type: "core_status",
    core: "CASPER-3",
    status: "THINKING",
    reviewed_through_event_id: 3,
  });

  assert.deepEqual(session.coreStatuses["CASPER-3"], {
    status: "THINKING",
    reviewedThroughEventId: 3,
  });
  assert.deepEqual(session.coreStatuses["MELCHIOR-1"], {
    status: "LISTENING",
    reviewedThroughEventId: 0,
  });
});

test("queues committed act speakers without blocking the following stream event", () => {
  const firstAct = {
    type: "act",
    id: 1,
    seen_through_event_id: 0,
    act: {
      core: "CASPER-3",
      kind: "POSITION",
      content: "Opening position.",
      reply_to: null,
    },
  };
  const secondAct = {
    type: "act",
    id: 2,
    seen_through_event_id: 0,
    act: {
      core: "MELCHIOR-1",
      kind: "POSITION",
      content: "Independent position.",
      reply_to: null,
    },
  };

  let session = applyStreamEvent(createSession(1000), firstAct);
  session = applyStreamEvent(session, secondAct);
  session = applyStreamEvent(session, {
    type: "core_status",
    core: "BALTHASAR-2",
    status: "READY",
    reviewed_through_event_id: 2,
  });

  assert.equal(session.speakingCore, "CASPER-3");
  assert.deepEqual(session.pendingSpeakers, ["MELCHIOR-1"]);
  assert.deepEqual(session.acts, [firstAct, secondAct]);
  assert.equal(session.coreStatuses["BALTHASAR-2"].status, "READY");
});

test("result atomically clears presentation and reveals complete policy facts", () => {
  const active = {
    ...createSession(1000),
    speakingCore: "CASPER-3",
    pendingSpeakers: ["MELCHIOR-1"],
  };
  const result = {
    type: "result",
    quorum: "unanimous",
    recommendation: "APPROVED_WITH_CONDITIONS",
    outcome: "HUMAN_CONFIRMATION_REQUIRED",
    requires_human_confirmation: true,
    ballots: [
      { core: "MELCHIOR-1", vote: "AGREE", confidence: 0.8, rationale: "Yes.", conditions: [] },
      {
        core: "BALTHASAR-2",
        vote: "CONDITIONAL",
        confidence: 0.7,
        rationale: "Only with safeguards.",
        conditions: ["Retain review."],
      },
      { core: "CASPER-3", vote: "AGREE", confidence: 0.6, rationale: "Yes.", conditions: [] },
    ],
    conditions: ["Retain review."],
    disclaimer: "Decision support only.",
  };

  const session = applyStreamEvent(active, result);

  assert.equal(session.status, "complete");
  assert.equal(session.speakingCore, null);
  assert.deepEqual(session.pendingSpeakers, []);
  assert.deepEqual(session.ballots, result.ballots);
  assert.equal(session.result.quorum, "unanimous");
  assert.equal(session.result.recommendation, "APPROVED_WITH_CONDITIONS");
  assert.equal(session.result.requires_human_confirmation, true);
});

test("advances speaker presentation independently from stream parsing", () => {
  const session = {
    ...createSession(1000),
    speakingCore: "CASPER-3",
    pendingSpeakers: ["MELCHIOR-1", "BALTHASAR-2"],
  };

  const next = advanceSpeakerPresentation(session);

  assert.equal(next.speakingCore, "MELCHIOR-1");
  assert.deepEqual(next.pendingSpeakers, ["BALTHASAR-2"]);
});

test("applies the complete public stream without revealing ballots before the result", () => {
  const events = eventsForMotion("Should the reversible proposal proceed?");
  let session = createSession(1000);

  for (const value of events) {
    const event = parseStreamEvent(value);
    if (event.type !== "result") {
      assert.equal(session.ballots, null);
      assert.equal(session.result, null);
    }
    session = applyStreamEvent(session, event);
    if (event.type === "ballots_locked") {
      assert.equal(session.ballots, null);
      assert.equal(session.result, null);
    }
  }

  assert.deepEqual(session.ballots.map((ballot) => ballot.vote), [
    "AGREE",
    "CONDITIONAL",
    "DISAGREE",
  ]);
  assert.equal(session.result.recommendation, "APPROVED_WITH_CONDITIONS");
  assert.doesNotMatch(
    JSON.stringify(session),
    /reasoning_content|private_reasoning|DEEPSEEK_API_KEY|sk-test-secret/,
  );
});
