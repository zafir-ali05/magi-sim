import { CORE_IDS } from "./events.js";

function initialCoreStatuses() {
  return Object.fromEntries(
    CORE_IDS.map((core) => [
      core,
      { status: "LISTENING", reviewedThroughEventId: 0 },
    ]),
  );
}

export function createSession(startedAt = null) {
  const active = startedAt !== null && startedAt !== undefined;
  return {
    status: active ? "running" : "idle",
    phase: active ? "CONNECTING" : "STANDBY",
    activeCores: [],
    coreStatuses: initialCoreStatuses(),
    acts: [],
    speakingCore: null,
    pendingSpeakers: [],
    ballotsLocked: false,
    ballots: null,
    result: null,
    error: "",
    startedAt,
    elapsedMs: 0,
  };
}

export function applyStreamEvent(session, event) {
  switch (event.type) {
    case "phase":
      return {
        ...session,
        status: "running",
        phase: event.phase,
        activeCores: event.active_cores,
      };
    case "core_status":
      return {
        ...session,
        coreStatuses: {
          ...session.coreStatuses,
          [event.core]: {
            status: event.status,
            reviewedThroughEventId: event.reviewed_through_event_id,
          },
        },
      };
    case "act": {
      const hasSpeaker = session.speakingCore !== null;
      return {
        ...session,
        status: "running",
        acts: [...session.acts, event],
        speakingCore: hasSpeaker ? session.speakingCore : event.act.core,
        pendingSpeakers: hasSpeaker
          ? [...session.pendingSpeakers, event.act.core]
          : session.pendingSpeakers,
      };
    }
    case "ballots_locked":
      return {
        ...session,
        status: "running",
        phase: "BALLOTING",
        ballotsLocked: true,
      };
    case "result":
      return {
        ...session,
        status: "complete",
        phase: "COMPLETE",
        activeCores: [],
        speakingCore: null,
        pendingSpeakers: [],
        ballotsLocked: true,
        ballots: event.ballots,
        result: event,
        error: "",
      };
    case "error":
      return {
        ...session,
        status: "error",
        phase: "FAILED",
        activeCores: [],
        speakingCore: null,
        pendingSpeakers: [],
        error: event.message,
      };
    default:
      return session;
  }
}

export function advanceSpeakerPresentation(session) {
  const [nextSpeaker = null, ...remainingSpeakers] = session.pendingSpeakers;
  return {
    ...session,
    speakingCore: nextSpeaker,
    pendingSpeakers: remainingSpeakers,
  };
}
