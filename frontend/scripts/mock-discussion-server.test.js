import test from "node:test";
import assert from "node:assert/strict";

import { eventsForMotion } from "./mock-discussion-server.mjs";

test("provides a complete mixed-ballot discussion for browser verification", () => {
  const events = eventsForMotion("Should the reversible proposal proceed?");
  const acts = events.filter((event) => event.type === "act");

  assert.equal(events[0].type, "phase");
  assert.deepEqual(acts.map((event) => event.act.core), [
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
    "CASPER-3",
    "MELCHIOR-1",
    "BALTHASAR-2",
  ]);
  assert.deepEqual(
    acts.map((event) => event.seen_through_event_id),
    [0, 0, 0, 3, 4, 5],
  );
  assert.equal(acts.some((event) => "round" in event), false);
  assert.equal(events.some((event) => event.type === "core_status"), true);
  const discussionIndex = events.findIndex(
    (event) => event.type === "phase" && event.phase === "DISCUSSION",
  );
  assert.equal(
    events
      .slice(0, discussionIndex)
      .filter((event) => event.type === "core_status" && event.status === "THINKING")
      .length,
    3,
  );
  const speakingStatuses = events
    .filter((event) => event.type === "core_status" && event.status === "SPEAKING")
    .map((event) => event.core);
  assert.deepEqual(speakingStatuses, [
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
    "CASPER-3",
    "MELCHIOR-1",
    "BALTHASAR-2",
  ]);
  assert.equal(events.at(-2).type, "ballots_locked");
  assert.equal(events.at(-1).quorum, "majority");
  assert.equal(events.at(-1).recommendation, "APPROVED_WITH_CONDITIONS");
  assert.equal(events.at(-1).outcome, "APPROVED_WITH_CONDITIONS");
  assert.equal(events.at(-1).requires_human_confirmation, false);
  assert.deepEqual(events.at(-1).ballots.map((ballot) => ballot.vote), [
    "AGREE",
    "CONDITIONAL",
    "DISAGREE",
  ]);
  assert.equal(
    acts.every(
      (event) =>
        event.act.reply_to === null || event.act.reply_to <= event.seen_through_event_id,
    ),
    true,
  );
  assert.doesNotMatch(
    JSON.stringify(events.slice(0, -1)),
    /"ballots"|"vote"|reasoning_content|private_reasoning|DEEPSEEK_API_KEY/,
  );
});

test("provides one sanitized error for the explicit failure fixture", () => {
  assert.deepEqual(eventsForMotion("[fail] exercise the error state"), [
    { type: "error", message: "Mock deliberation failed safely." },
  ]);
});
