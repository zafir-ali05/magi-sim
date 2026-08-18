import test from "node:test";
import assert from "node:assert/strict";

import { eventsForMotion } from "./mock-discussion-server.mjs";

test("provides a complete mixed-ballot discussion for browser verification", () => {
  const events = eventsForMotion("Should the reversible proposal proceed?");

  assert.equal(events[0].type, "phase");
  assert.deepEqual(events.filter((event) => event.type === "act").map((event) => event.act.core), [
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
  ]);
  assert.equal(events.at(-2).type, "ballots_locked");
  assert.deepEqual(events.at(-1).ballots.map((ballot) => ballot.vote), [
    "AGREE",
    "CONDITIONAL",
    "DISAGREE",
  ]);
});

test("provides one sanitized error for the explicit failure fixture", () => {
  assert.deepEqual(eventsForMotion("[fail] exercise the error state"), [
    { type: "error", message: "Mock deliberation failed safely." },
  ]);
});
