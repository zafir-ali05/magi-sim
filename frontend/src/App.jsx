import React, { useEffect, useRef, useState } from "react";

import { CORE_IDS, parseNdjsonChunk, parseStreamEvent, StreamProtocolError } from "./events.js";
import { CoreResponseDialog } from "./CoreResponseDialog.jsx";
import { MagiCoreArray } from "./MagiCoreArray.jsx";
import { buildCoreDialogModel } from "./magiVisualState.js";
import { createSession } from "./session.js";

const MAX_REACTION_ROUNDS = 3;

function formatElapsed(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function outcomeLabel(outcome) {
  return outcome.replaceAll("_", " ");
}

function protocolMessage(error) {
  if (error instanceof StreamProtocolError) return error.message;
  if (error instanceof Error && error.name === "AbortError") return "";
  if (error instanceof Error && error.message.startsWith("HTTP ")) {
    return `Connection error: ${error.message}`;
  }
  return "Connection error: the deliberation stream could not be completed.";
}

function isRunning(status) {
  return status === "running";
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [selectedCore, setSelectedCore] = useState(null);
  const [session, setSession] = useState(() => createSession());
  const controllerRef = useRef(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!session.startedAt || !isRunning(session.status)) return undefined;

    const updateElapsed = () => {
      setSession((current) => ({
        ...current,
        elapsedMs: Date.now() - current.startedAt,
      }));
    };
    updateElapsed();
    const interval = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(interval);
  }, [session.startedAt, session.status]);

  useEffect(
    () => () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
    },
    [],
  );

  const applyEvent = (event) => {
    setSession((current) => {
      switch (event.type) {
        case "phase":
          return {
            ...current,
            status: "running",
            phase: event.phase,
            activeCores: event.active_cores,
          };
        case "act":
          return {
            ...current,
            status: "running",
            acts: [...current.acts, event],
            round: Math.max(current.round, event.round),
          };
        case "ballots_locked":
          return {
            ...current,
            status: "running",
            phase: "BALLOTING",
            ballotsLocked: true,
          };
        case "result":
          return {
            ...current,
            status: "complete",
            phase: "COMPLETE",
            activeCores: [],
            ballotsLocked: true,
            ballots: event.ballots,
            result: event,
            error: "",
          };
        case "error":
          return {
            ...current,
            status: "error",
            phase: "FAILED",
            activeCores: [],
            error: event.message,
          };
        default:
          return current;
      }
    });
  };

  const handleStartOver = () => {
    requestIdRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setQuestion("");
    setContext("");
    setSubmittedQuestion("");
    setSelectedCore(null);
    setSession(createSession());
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isRunning(session.status)) return;

    controllerRef.current?.abort();
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const controller = new AbortController();
    controllerRef.current = controller;
    const startedAt = Date.now();
    const motion = { question: question.trim(), context: context.trim() };
    setSubmittedQuestion(motion.question);
    setSelectedCore(null);
    setSession(createSession(startedAt));

    let terminalEventSeen = false;
    const processLine = (line) => {
      if (requestId !== requestIdRef.current) return;
      if (!line.trim()) return;
      let value;
      try {
        value = JSON.parse(line);
      } catch {
        throw new StreamProtocolError("a stream line was not valid JSON.");
      }
      const parsed = parseStreamEvent(value);
      if (parsed.type === "result" || parsed.type === "error") terminalEventSeen = true;
      applyEvent(parsed);
    };

    try {
      const response = await fetch("/api/discuss", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify(motion),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (!response.body) throw new StreamProtocolError("the response did not contain a stream.");

      const decoded = response.body.pipeThrough(new TextDecoderStream());
      let remainder = "";
      for await (const chunk of decoded) {
        const parsedChunk = parseNdjsonChunk(remainder, chunk);
        remainder = parsedChunk.remainder;
        for (const line of parsedChunk.lines) processLine(line);
      }
      if (remainder.trim()) processLine(remainder);
      if (!terminalEventSeen) {
        throw new StreamProtocolError("the stream ended before a final result.");
      }
    } catch (error) {
      if (requestId !== requestIdRef.current || error?.name === "AbortError") return;
      const message = protocolMessage(error);
      setSession((current) => ({
        ...current,
        status: "error",
        phase: "FAILED",
        activeCores: [],
        error: message || "Connection closed.",
      }));
      controller.abort();
    } finally {
      if (requestId === requestIdRef.current) controllerRef.current = null;
    }
  };

  const roundsRemaining =
    session.phase === "OPENING"
      ? MAX_REACTION_ROUNDS
      : session.phase === "DISCUSSION"
        ? Math.max(0, MAX_REACTION_ROUNDS - session.round)
        : 0;

  const selectedBallot =
    selectedCore && session.result
      ? session.ballots?.find((ballot) => ballot.core === selectedCore) ?? null
      : null;
  const dialogModel = selectedCore
    ? buildCoreDialogModel({
        core: selectedCore,
        question: submittedQuestion || question.trim(),
        phase: session.phase,
        sessionStatus: session.status,
        activeCores: session.activeCores,
        acts: session.acts,
        ballot: selectedBallot,
        ballotsLocked: session.ballotsLocked,
        error: session.error,
      })
    : null;

  return (
    <main className="console-shell" aria-busy={isRunning(session.status)}>
      <div className="console-frame">
        <header className="console-header">
          <div className="console-mark" aria-label="S.C. MAGI">
            <span className="console-mark__shape" aria-hidden="true">
              ◇
            </span>
            <div>
              <p className="micro-label">S.C. MAGI / OPERATIONAL CONSOLE</p>
              <h1>TRI-CORE DECISION SUPPORT</h1>
            </div>
          </div>
          <div className="console-header__meta">
            <span>LOCAL STREAM</span>
            <span className="header-rule" aria-hidden="true" />
            <span>PUBLIC TRACE ONLY</span>
          </div>
        </header>

        <section className="motion-section" aria-labelledby="motion-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">01 / MOTION INPUT</p>
              <h2 id="motion-heading">Submit a question to the three cores.</h2>
            </div>
            <span className="required-note">REQUIRED / 3–2,000 CHARACTERS</span>
          </div>
          <form className="motion-form" onSubmit={handleSubmit}>
            <label htmlFor="motion-question">
              <span className="field-label">MOTION</span>
              <textarea
                id="motion-question"
                name="question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="State the decision, dilemma, or proposed action."
                minLength={3}
                maxLength={2000}
                required
                disabled={isRunning(session.status)}
                rows={3}
              />
            </label>
            <label htmlFor="motion-context">
              <span className="field-label">CONTEXT <span>(OPTIONAL)</span></span>
              <textarea
                id="motion-context"
                name="context"
                value={context}
                onChange={(event) => setContext(event.target.value)}
                placeholder="Facts or constraints the cores should weigh."
                maxLength={8000}
                disabled={isRunning(session.status)}
                rows={3}
              />
            </label>
            <div className="form-actions">
              <button type="submit" disabled={isRunning(session.status)}>
                <span aria-hidden="true">▶</span>
                {isRunning(session.status) ? " STREAM IN PROGRESS" : " RUN DELIBERATION"}
              </button>
              {session.status === "complete" || session.status === "error" ? (
                <button type="button" className="button-secondary" onClick={handleStartOver}>
                  START OVER
                </button>
              ) : null}
            </div>
          </form>
        </section>

        <section className="status-strip" aria-labelledby="status-heading">
          <div className="status-strip__title">
            <p className="eyebrow">02 / LIVE STATUS</p>
            <h2 id="status-heading" className="sr-only">
              Live deliberation status
            </h2>
            <span className="phase-value" aria-live="polite">
              {session.phase}
            </span>
          </div>
          <dl className="status-grid">
            <div>
              <dt>ELAPSED</dt>
              <dd>{formatElapsed(session.elapsedMs)}</dd>
            </div>
            <div>
              <dt>ACTIVE CORES</dt>
              <dd title={session.activeCores.join(" / ") || "None"}>
                {session.activeCores.length ? session.activeCores.join(" / ") : "—"}
              </dd>
            </div>
            <div>
              <dt>ROUND</dt>
              <dd>{session.phase === "DISCUSSION" ? `${session.round} / ${MAX_REACTION_ROUNDS}` : "—"}</dd>
            </div>
            <div>
              <dt>REMAINING REACTION ROUNDS</dt>
              <dd>{session.phase === "OPENING" || session.phase === "DISCUSSION" ? roundsRemaining : "—"}</dd>
            </div>
          </dl>
        </section>

        {session.error ? (
          <div className="error-banner" role="alert">
            <span className="error-banner__shape" aria-hidden="true">
              !
            </span>
            <div>
              <strong>STREAM HALTED</strong>
              <span>{session.error}</span>
            </div>
          </div>
        ) : null}

        <section className="cores-section" aria-labelledby="cores-heading">
          <div className="section-heading section-heading--inline">
            <div>
              <p className="eyebrow">03 / CORE ARRAY</p>
              <h2 id="cores-heading">Independent identities. One public trace.</h2>
            </div>
            <span className="section-side-note">{CORE_IDS.length} / {CORE_IDS.length} ONLINE</span>
          </div>
          <MagiCoreArray
            phase={session.phase}
            sessionStatus={session.status}
            activeCores={session.activeCores}
            acts={session.acts}
            ballots={session.result ? session.ballots : null}
            ballotsLocked={session.ballotsLocked}
            result={session.result}
            elapsedMs={session.elapsedMs}
            round={session.round}
            onSelectCore={setSelectedCore}
          />
        </section>

        <CoreResponseDialog
          open={Boolean(selectedCore)}
          model={dialogModel}
          onClose={() => setSelectedCore(null)}
        />

        <section className="transcript-section" aria-labelledby="transcript-heading">
          <div className="section-heading section-heading--inline">
            <div>
              <p className="eyebrow">04 / SHARED TRANSCRIPT</p>
              <h2 id="transcript-heading">Committed public acts, in order.</h2>
            </div>
            <span className="section-side-note">{session.acts.length.toString().padStart(2, "0")} ACTS COMMITTED</span>
          </div>
          <div className="transcript" aria-live="polite">
            {session.acts.length === 0 ? (
              <p className="transcript-empty">No public signals committed. Opening analysis will appear here.</p>
            ) : (
              <ol>
                {session.acts.map((event) => (
                  <li key={event.id} className={`transcript-entry transcript-entry--${event.act.core.toLowerCase()}`}>
                    <div className="transcript-entry__meta">
                      <span>ACT {event.id.toString().padStart(2, "0")}</span>
                      <span>R{event.round}</span>
                      <span>{event.act.core}</span>
                      <span className="transcript-entry__kind">{event.act.kind}</span>
                    </div>
                    <p>{event.act.content}</p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        {session.result ? (
          <section className="result-section" aria-labelledby="result-heading">
            <div className="section-heading section-heading--inline">
              <div>
                <p className="eyebrow">05 / DECISION SUPPORT RESULT</p>
                <h2 id="result-heading">All ballots revealed together.</h2>
              </div>
              <div className={`outcome-badge outcome-badge--${session.result.outcome.toLowerCase()}`}>
                <span aria-hidden="true">{session.result.outcome === "REJECTED" ? "×" : "＋"}</span>
                <span>{outcomeLabel(session.result.outcome)}</span>
              </div>
            </div>
            {session.result.conditions.length > 0 ? (
              <div className="result-conditions">
                <span className="field-label">AGGREGATED CONDITIONS</span>
                <ul>
                  {session.result.conditions.map((condition) => (
                    <li key={condition}>{condition}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <p className="disclaimer">{session.result.disclaimer}</p>
          </section>
        ) : null}

        <footer className="console-footer">
          <span>PUBLIC ACTS EXCLUDE PRIVATE REASONING CONTENT</span>
          <span>NO REAL-WORLD ACTIONS EXECUTED</span>
          <span>SC / 03</span>
        </footer>
      </div>
    </main>
  );
}
