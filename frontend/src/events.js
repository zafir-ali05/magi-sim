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

function requiredString(record, field) {
  if (typeof record[field] !== "string" || record[field].length === 0) {
    fail(`${field} must be a non-empty string.`);
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
  const phase = oneOf(value.phase, PHASES, "phase");
  const activeCores = requiredArray(value, "active_cores").map((core, index) =>
    coreId(core, `active_cores[${index}]`),
  );
  return { type: "phase", phase, active_cores: activeCores };
}

function parseAct(value) {
  if (!isRecord(value)) fail("act event must be an object.");
  if (!Number.isInteger(value.id) || value.id < 1) {
    fail("id must be a positive integer.");
  }
  if (!Number.isInteger(value.round) || value.round < 0) {
    fail("round must be a non-negative integer.");
  }
  if (!isRecord(value.act)) fail("act must be an object.");

  const act = value.act;
  const parsedAct = {
    core: coreId(act.core, "act.core"),
    kind: oneOf(act.kind, ACT_KINDS, "act.kind"),
    content: requiredString(act, "content"),
  };
  if (act.reply_to !== undefined && act.reply_to !== null) {
    if (!Number.isInteger(act.reply_to) || act.reply_to < 1) {
      fail("act.reply_to must be null or a positive integer.");
    }
    parsedAct.reply_to = act.reply_to;
  } else {
    parsedAct.reply_to = null;
  }

  return { type: "act", id: value.id, round: value.round, act: parsedAct };
}

function parseBallot(value, index) {
  if (!isRecord(value)) fail(`ballots[${index}] must be an object.`);
  const conditions = requiredArray(value, "conditions").map((condition, conditionIndex) => {
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
    rationale: requiredString(value, "rationale"),
    conditions,
  };
}

function parseResult(value) {
  if (!isRecord(value)) fail("result event must be an object.");
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
    disclaimer: requiredString(value, "disclaimer"),
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
    case "ballots_locked":
      return { type: "ballots_locked" };
    case "result":
      return parseResult(value);
    case "error":
      return { type: "error", message: requiredString(value, "message") };
    default:
      fail(`unknown event type: ${value.type}`);
  }
}

export { CORE_IDS };
