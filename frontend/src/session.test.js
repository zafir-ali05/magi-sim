import test from "node:test";
import assert from "node:assert/strict";

import { createSession } from "./session.js";

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
