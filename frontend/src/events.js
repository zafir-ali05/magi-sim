const CORE_IDS = ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"];
const ACT_KINDS = [
  "POSITION",
  "CHALLENGE",
  "RESPONSE",
  "CONCEDE",
  "PROPOSE_CONDITION",
  "CLARIFY",
  "READY",
  "PASS",
];
const VOTES = ["AGREE", "DISAGREE", "CONDITIONAL"];
const PHASES = ["OPENING", "DISCUSSION", "BALLOTING"];
const OUTCOMES = ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"];
const CORE_STATUSES = [
  "LISTENING",
  "THINKING",
  "SPEAKING",
  "READY",
  "BUDGET_EXHAUSTED",
  "FAILED",
];

export class StreamProtocolError extends Error {
  constructor(message) {
    super(`Protocol error: ${message}`);
    this.name = "StreamProtocolError";
  }
}

export function parseNdjsonChunk(buffer, chunk) {
  if (typeof buffer !== "string" || typeof chunk !== "string") {
    throw new TypeError("NDJSON parser input must be strings.");
  }

  const lines = `${buffer}${chunk}`.split("\n");
  const remainder = lines.pop() ?? "";
  return {
    lines: lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line)),
    remainder,
  };
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function fail(message) {
  throw new StreamProtocolError(message);
}

function exactKeys(record, allowed, label) {
  if (Object.keys(record).some((key) => !allowed.includes(key))) {
    fail(`${label} contains an unsupported field.`);
  }
}

function stringField(record, field, { minLength = 0, maxLength = null } = {}) {
  if (typeof record[field] !== "string") {
    fail(`${field} must be a string.`);
  }
  if (record[field].length < minLength) {
    fail(`${field} must be at least ${minLength} character long.`);
  }
  if (maxLength !== null && record[field].length > maxLength) {
    fail(`${field} must be at most ${maxLength} characters.`);
  }
  return record[field];
}

function requiredArray(record, field) {
  if (!Array.isArray(record[field])) {
    fail(`${field} must be an array.`);
  }
  return record[field];
}

function oneOf(value, choices, field) {
  if (!choices.includes(value)) {
    fail(`${field} has an unsupported value.`);
  }
  return value;
}

function coreId(value, field = "core") {
  return oneOf(value, CORE_IDS, field);
}

function parsePhase(value) {
  if (!isRecord(value)) fail("phase event must be an object.");
  exactKeys(value, ["type", "phase", "active_cores"], "phase event");
  const phase = oneOf(value.phase, PHASES, "phase");
  const activeCores = requiredArray(value, "active_cores").map((core, index) =>
    coreId(core, `active_cores[${index}]`),
  );
  return { type: "phase", phase, active_cores: activeCores };
}

function parseAct(value) {
  if (!isRecord(value)) fail("act event must be an object.");
  exactKeys(value, ["type", "id", "seen_through_event_id", "act"], "act event");
  if (!Number.isInteger(value.id) || value.id < 1) {
    fail("id must be a positive integer.");
  }
  if (!Number.isInteger(value.seen_through_event_id) || value.seen_through_event_id < 0) {
    fail("seen_through_event_id must be a non-negative integer.");
  }
  if (!isRecord(value.act)) fail("act must be an object.");

  const act = value.act;
  exactKeys(act, ["core", "kind", "content", "reply_to"], "act");
  const parsedAct = {
    core: coreId(act.core, "act.core"),
    kind: oneOf(act.kind, ACT_KINDS, "act.kind"),
    content: stringField(act, "content", { minLength: 1, maxLength: 2000 }),
  };
  if (act.reply_to !== undefined && act.reply_to !== null) {
    if (
      !Number.isInteger(act.reply_to) ||
      act.reply_to < 1 ||
      act.reply_to > value.seen_through_event_id
    ) {
      fail("act.reply_to must reference a visible positive event id.");
    }
    parsedAct.reply_to = act.reply_to;
  } else {
    parsedAct.reply_to = null;
  }

  return {
    type: "act",
    id: value.id,
    seen_through_event_id: value.seen_through_event_id,
    act: parsedAct,
  };
}

function parseCoreStatus(value) {
  if (!isRecord(value)) fail("core_status event must be an object.");
  exactKeys(
    value,
    ["type", "core", "status", "reviewed_through_event_id"],
    "core_status event",
  );
  if (
    !Number.isInteger(value.reviewed_through_event_id) ||
    value.reviewed_through_event_id < 0
  ) {
    fail("reviewed_through_event_id must be a non-negative integer.");
  }
  return {
    type: "core_status",
    core: coreId(value.core),
    status: oneOf(value.status, CORE_STATUSES, "status"),
    reviewed_through_event_id: value.reviewed_through_event_id,
  };
}

function parseBallot(value, index) {
  if (!isRecord(value)) fail(`ballots[${index}] must be an object.`);
  exactKeys(value, ["core", "vote", "confidence", "rationale", "conditions"], `ballots[${index}]`);
  const rawConditions = value.conditions === undefined ? [] : requiredArray(value, "conditions");
  if (rawConditions.length > 8) {
    fail(`ballots[${index}].conditions must contain at most 8 items.`);
  }
  const conditions = rawConditions.map((condition, conditionIndex) => {
    if (typeof condition !== "string") {
      fail(`ballots[${index}].conditions[${conditionIndex}] must be a string.`);
    }
    return condition;
  });
  if (typeof value.confidence !== "number" || !Number.isFinite(value.confidence)) {
    fail(`ballots[${index}].confidence must be a finite number.`);
  }
  if (value.confidence < 0 || value.confidence > 1) {
    fail(`ballots[${index}].confidence must be between 0 and 1.`);
  }
  return {
    core: coreId(value.core, `ballots[${index}].core`),
    vote: oneOf(value.vote, VOTES, `ballots[${index}].vote`),
    confidence: value.confidence,
    rationale: stringField(value, "rationale", { minLength: 1, maxLength: 2000 }),
    conditions,
  };
}

function parseResult(value) {
  if (!isRecord(value)) fail("result event must be an object.");
  exactKeys(value, ["type", "outcome", "ballots", "conditions", "disclaimer"], "result event");
  const ballots = requiredArray(value, "ballots").map(parseBallot);
  if (ballots.length !== CORE_IDS.length) {
    fail("result ballots must contain all three cores.");
  }
  const ballotCores = new Set(ballots.map((ballot) => ballot.core));
  if (ballotCores.size !== CORE_IDS.length || CORE_IDS.some((core) => !ballotCores.has(core))) {
    fail("result ballots must contain one ballot for each core.");
  }
  const conditions = requiredArray(value, "conditions").map((condition, index) => {
    if (typeof condition !== "string") {
      fail(`conditions[${index}] must be a string.`);
    }
    return condition;
  });
  return {
    type: "result",
    outcome: oneOf(value.outcome, OUTCOMES, "outcome"),
    ballots,
    conditions,
    disclaimer: stringField(value, "disclaimer"),
  };
}

export function parseStreamEvent(value) {
  if (!isRecord(value)) fail("event must be an object.");
  if (typeof value.type !== "string") fail("event type must be a string.");

  switch (value.type) {
    case "phase":
      return parsePhase(value);
    case "act":
      return parseAct(value);
    case "core_status":
      return parseCoreStatus(value);
    case "ballots_locked":
      exactKeys(value, ["type"], "ballots_locked event");
      return { type: "ballots_locked" };
    case "result":
      return parseResult(value);
    case "error":
      exactKeys(value, ["type", "message"], "error event");
      return { type: "error", message: stringField(value, "message") };
    default:
      fail("unknown event type.");
  }
}

export { CORE_IDS };
