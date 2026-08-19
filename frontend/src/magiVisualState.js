const CORE_STATES = {
  information: {
    key: "information",
    english: "INFORMATION",
    japanese: "情 報",
  },
  processing: {
    key: "processing",
    english: "SPEAKING",
    japanese: "情 報",
  },
  connecting: {
    key: "processing",
    english: "PROCESSING",
    japanese: "情 報",
  },
  listening: {
    key: "listening",
    english: "LISTENING",
    japanese: "情 報",
  },
  thinking: {
    key: "thinking",
    english: "ANALYZING",
    japanese: "解 析",
  },
  ready: {
    key: "ready",
    english: "READY",
    japanese: "待 機",
  },
  bounded: {
    key: "bounded",
    english: "REVIEW BOUNDED",
    japanese: "限 界",
  },
  locked: {
    key: "locked",
    english: "VOTE SEALED",
    japanese: "情 報",
  },
  agree: { key: "agree", english: "AGREE", japanese: "合 意" },
  conditional: {
    key: "conditional",
    english: "CONDITIONAL",
    japanese: "状 態",
  },
  disagree: {
    key: "disagree",
    english: "DISAGREE",
    japanese: "拒 絶",
  },
  error: { key: "error", english: "ERROR", japanese: "誤 差" },
};

const SYSTEM_STATES = {
  information: { key: "information", english: "INFORMATION", japanese: "情 報" },
  processing: { key: "processing", english: "PROCESSING", japanese: "情 報" },
  locked: { key: "locked", english: "BALLOT LOCK", japanese: "情 報" },
  agree: { key: "agree", english: "APPROVED", japanese: "合 意" },
  conditional: {
    key: "conditional",
    english: "APPROVED WITH CONDITIONS",
    japanese: "状 態",
  },
  disagree: { key: "disagree", english: "REJECTED", japanese: "拒 絶" },
  error: { key: "error", english: "ERROR", japanese: "誤 差" },
};

const VOTE_STATES = {
  AGREE: "agree",
  CONDITIONAL: "conditional",
  DISAGREE: "disagree",
};

const OUTCOME_STATES = {
  APPROVED: "agree",
  APPROVED_WITH_CONDITIONS: "conditional",
  REJECTED: "disagree",
  HUMAN_CONFIRMATION_REQUIRED: "conditional",
  INCOMPLETE: "error",
};

export function getCoreVisualState({
  core,
  phase = "STANDBY",
  sessionStatus = "idle",
  speakingCore = null,
  coreStatus = null,
  ballot = null,
  ballotsLocked = false,
} = {}) {
  if (sessionStatus === "error" || phase === "FAILED") return CORE_STATES.error;

  const revealedState = VOTE_STATES[ballot?.vote];
  if (revealedState) return CORE_STATES[revealedState];

  if (ballotsLocked || phase === "BALLOTING") return CORE_STATES.locked;

  if (sessionStatus === "running" && phase === "CONNECTING") {
    return CORE_STATES.connecting;
  }

  if (sessionStatus === "running" && ["OPENING", "DISCUSSION"].includes(phase)) {
    if (core === speakingCore) return CORE_STATES.processing;

    const statusState = {
      THINKING: CORE_STATES.thinking,
      LISTENING: CORE_STATES.listening,
      SPEAKING: CORE_STATES.listening,
      READY: CORE_STATES.ready,
      BUDGET_EXHAUSTED: CORE_STATES.bounded,
      FAILED: CORE_STATES.error,
    }[coreStatus?.status];
    return statusState ?? CORE_STATES.listening;
  }

  return CORE_STATES.information;
}

export function getSystemVisualState({
  phase = "STANDBY",
  sessionStatus = "idle",
  ballotsLocked = false,
  result = null,
} = {}) {
  if (sessionStatus === "error" || phase === "FAILED") return SYSTEM_STATES.error;

  const resultState = OUTCOME_STATES[result?.outcome];
  if (resultState) return SYSTEM_STATES[resultState];

  if (ballotsLocked || phase === "BALLOTING") return SYSTEM_STATES.locked;

  if (
    sessionStatus === "running" &&
    ["CONNECTING", "OPENING", "DISCUSSION"].includes(phase)
  ) {
    return SYSTEM_STATES.processing;
  }

  return SYSTEM_STATES.information;
}

function coreTitle(core) {
  return core.split("-")[0].toLowerCase();
}

function publicActLines(acts, core) {
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
    speakingCore,
    coreStatus,
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
      ballot?.conditions.length > 0
        ? ballot.conditions.join("\n")
        : "—",
    fullResponse: responseParts.length > 0 ? responseParts.join("\n\n") : "Waiting for public response...",
  };
}
