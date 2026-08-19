const CORE_STATES = Object.freeze({
  information: Object.freeze({
    key: "information",
    english: "INFORMATION",
    japanese: "情 報",
    flicker: false,
  }),
  processing: Object.freeze({
    key: "processing",
    english: "SPEAKING",
    japanese: "情 報",
    flicker: false,
  }),
  connecting: Object.freeze({
    key: "processing",
    english: "PROCESSING",
    japanese: "情 報",
    flicker: false,
  }),
  listening: Object.freeze({
    key: "listening",
    english: "LISTENING",
    japanese: "情 報",
    flicker: false,
  }),
  thinking: Object.freeze({
    key: "thinking",
    english: "ANALYZING",
    japanese: "解 析",
    flicker: false,
  }),
  ready: Object.freeze({
    key: "ready",
    english: "READY",
    japanese: "待 機",
    flicker: false,
  }),
  bounded: Object.freeze({
    key: "bounded",
    english: "REVIEW BOUNDED",
    japanese: "限 界",
    flicker: false,
  }),
  locked: Object.freeze({
    key: "locked",
    english: "VOTE SEALED",
    japanese: "情 報",
    flicker: false,
  }),
  agree: Object.freeze({ key: "agree", english: "AGREE", japanese: "合 意", flicker: false }),
  conditional: Object.freeze({
    key: "conditional",
    english: "CONDITIONAL",
    japanese: "状 態",
    flicker: false,
  }),
  disagree: Object.freeze({
    key: "disagree",
    english: "DISAGREE",
    japanese: "拒 絶",
    flicker: false,
  }),
  error: Object.freeze({ key: "error", english: "ERROR", japanese: "誤 差", flicker: false }),
});

const SYSTEM_STATES = Object.freeze({
  information: Object.freeze({ key: "information", english: "INFORMATION", japanese: "情 報" }),
  processing: Object.freeze({ key: "processing", english: "PROCESSING", japanese: "情 報" }),
  locked: Object.freeze({ key: "locked", english: "BALLOT LOCK", japanese: "情 報" }),
  agree: Object.freeze({ key: "agree", english: "APPROVED", japanese: "合 意" }),
  conditional: Object.freeze({
    key: "conditional",
    english: "APPROVED WITH CONDITIONS",
    japanese: "状 態",
  }),
  disagree: Object.freeze({ key: "disagree", english: "REJECTED", japanese: "拒 絶" }),
  error: Object.freeze({ key: "error", english: "ERROR", japanese: "誤 差" }),
});

const VOTE_STATES = Object.freeze({
  AGREE: "agree",
  CONDITIONAL: "conditional",
  DISAGREE: "disagree",
});

const OUTCOME_STATES = Object.freeze({
  APPROVED: "agree",
  APPROVED_WITH_CONDITIONS: "conditional",
  REJECTED: "disagree",
  HUMAN_CONFIRMATION_REQUIRED: "conditional",
  INCOMPLETE: "error",
});

function copyState(state) {
  return { ...state };
}

export function getCoreVisualState({
  core,
  phase = "STANDBY",
  sessionStatus = "idle",
  activeCores = [],
  speakingCore = null,
  coreStatus = null,
  ballot = null,
  ballotsLocked = false,
} = {}) {
  if (sessionStatus === "error" || phase === "FAILED") return copyState(CORE_STATES.error);

  const revealedState = VOTE_STATES[ballot?.vote];
  if (revealedState) return copyState(CORE_STATES[revealedState]);

  if (ballotsLocked || phase === "BALLOTING") return copyState(CORE_STATES.locked);

  if (sessionStatus === "running" && phase === "CONNECTING") {
    return copyState(CORE_STATES.connecting);
  }

  if (sessionStatus === "running" && ["OPENING", "DISCUSSION"].includes(phase)) {
    if (core === speakingCore) return copyState(CORE_STATES.processing);

    const statusState = {
      THINKING: CORE_STATES.thinking,
      LISTENING: CORE_STATES.listening,
      SPEAKING: CORE_STATES.listening,
      READY: CORE_STATES.ready,
      BUDGET_EXHAUSTED: CORE_STATES.bounded,
      FAILED: CORE_STATES.error,
    }[coreStatus?.status];
    return copyState(statusState ?? CORE_STATES.listening);
  }

  return copyState(CORE_STATES.information);
}

export function getSystemVisualState({
  phase = "STANDBY",
  sessionStatus = "idle",
  ballotsLocked = false,
  result = null,
} = {}) {
  if (sessionStatus === "error" || phase === "FAILED") return copyState(SYSTEM_STATES.error);

  const resultState = OUTCOME_STATES[result?.outcome];
  if (resultState) return copyState(SYSTEM_STATES[resultState]);

  if (ballotsLocked || phase === "BALLOTING") return copyState(SYSTEM_STATES.locked);

  if (
    sessionStatus === "running" &&
    ["CONNECTING", "OPENING", "DISCUSSION"].includes(phase)
  ) {
    return copyState(SYSTEM_STATES.processing);
  }

  return copyState(SYSTEM_STATES.information);
}

function coreTitle(core) {
  return typeof core === "string" ? core.split("-")[0].toLowerCase() : "core";
}

function publicActLines(acts, core) {
  if (!Array.isArray(acts)) return [];
  return acts
    .filter((event) => event?.act?.core === core)
    .map(
      (event) =>
        `SEEN ${event.seen_through_event_id} ${event.act.kind}: ${event.act.content}`,
    );
}

export function buildCoreDialogModel({
  core,
  question = "",
  phase = "STANDBY",
  sessionStatus = "idle",
  activeCores = [],
  speakingCore = null,
  coreStatus = null,
  acts = [],
  ballot = null,
  ballotsLocked = false,
  error = "",
} = {}) {
  const state = getCoreVisualState({
    core,
    phase,
    sessionStatus,
    activeCores,
    speakingCore,
    coreStatus,
    acts,
    ballot,
    ballotsLocked,
  });
  const responseParts = publicActLines(acts, core);

  if (ballot?.rationale) responseParts.push(`FINAL RATIONALE: ${ballot.rationale}`);
  if (!ballot && (ballotsLocked || phase === "BALLOTING")) {
    responseParts.push("Vote sealed until all cores report.");
  }

  return {
    title: coreTitle(core),
    question: question || "—",
    status: state.english.toLowerCase(),
    error: error || "—",
    conditions:
      Array.isArray(ballot?.conditions) && ballot.conditions.length > 0
        ? ballot.conditions.join("\n")
        : "—",
    fullResponse: responseParts.length > 0 ? responseParts.join("\n\n") : "Waiting for public response...",
    ballotLocked: !ballot && (ballotsLocked || phase === "BALLOTING"),
  };
}

export { CORE_STATES, SYSTEM_STATES };
