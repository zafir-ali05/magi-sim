export function createSession(startedAt = null) {
  const active = startedAt !== null && startedAt !== undefined;
  return {
    status: active ? "running" : "idle",
    phase: active ? "CONNECTING" : "STANDBY",
    activeCores: [],
    acts: [],
    ballotsLocked: false,
    ballots: null,
    result: null,
    error: "",
    startedAt,
    elapsedMs: 0,
  };
}
