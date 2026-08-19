import React from "react";

import { getCoreVisualState, getSystemVisualState } from "./magiVisualState.js";

const CORE_ORDER = ["BALTHASAR-2", "CASPER-3", "MELCHIOR-1"];

const CORE_META = Object.freeze({
  "BALTHASAR-2": { name: "BALTHASAR", order: 2, className: "balthasar" },
  "CASPER-3": { name: "CASPER", order: 3, className: "casper" },
  "MELCHIOR-1": { name: "MELCHIOR", order: 1, className: "melchior" },
});

function formatElapsed(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor((milliseconds ?? 0) / 1000));
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function ReferenceHeader({ side, title }) {
  return (
    <div className={`magi-system__header magi-system__header--${side}`} aria-hidden="true">
      <hr />
      <hr />
      <span lang="ja">{title}</span>
      <hr />
      <hr />
    </div>
  );
}

function SystemDiagnostics({ phase, round, elapsedMs }) {
  return (
    <div className="magi-system__diagnostics" aria-label="System diagnostics">
      <div>CODE:473</div>
      <div>FILE:MAGI_SYS</div>
      <div>PHASE:{phase}</div>
      <div>ROUND:{round || 0}</div>
      <div>TIME:{formatElapsed(elapsedMs)}</div>
    </div>
  );
}

function SystemResponse({ state }) {
  return (
    <div
      className={`magi-system__response magi-system__response--${state.key}`}
      aria-live="polite"
      aria-label={`System status: ${state.english}`}
    >
      <span lang="ja">{state.japanese}</span>
    </div>
  );
}

function CoreButton({ core, state, speaking, onSelectCore }) {
  const meta = CORE_META[core];
  const speakingClass = speaking ? " magi-system__core--speaking" : "";

  return (
    <button
      type="button"
      className={`magi-system__core magi-system__core--${meta.className} magi-system__core--${state.key}${speakingClass}`}
      aria-label={`${meta.name} ${meta.order}: ${state.english}`}
      onClick={() => onSelectCore(core)}
    >
      <span className="magi-system__core-inner">
        {meta.name} • {meta.order}
      </span>
    </button>
  );
}

export function MagiCoreArray({
  phase = "STANDBY",
  sessionStatus = "idle",
  activeCores = [],
  speakingCore = null,
  acts = [],
  ballots = null,
  ballotsLocked = false,
  result = null,
  elapsedMs = 0,
  round = 0,
  onSelectCore = () => {},
}) {
  const publicBallots = result && Array.isArray(ballots) ? ballots : [];
  const systemState = getSystemVisualState({ phase, sessionStatus, ballotsLocked, result });

  return (
    <div className="magi-system" aria-label="MAGI tri-core decision array">
      <div className="magi-system__viewport">
        <div className="magi-system__stage">
          <ReferenceHeader side="left" title="質問" />
          <ReferenceHeader side="right" title="解決" />
          <SystemDiagnostics phase={phase} round={round} elapsedMs={elapsedMs} />
          <SystemResponse state={systemState} />

          <span
            className="magi-system__connection magi-system__connection--casper-balthasar"
            aria-hidden="true"
          />
          <span
            className="magi-system__connection magi-system__connection--casper-melchior"
            aria-hidden="true"
          />
          <span
            className="magi-system__connection magi-system__connection--balthasar-melchior"
            aria-hidden="true"
          />

          {CORE_ORDER.map((core) => (
            <CoreButton
              key={core}
              core={core}
              speaking={core === speakingCore}
              state={getCoreVisualState({
                core,
                phase,
                sessionStatus,
                activeCores,
                speakingCore,
                acts,
                ballot: publicBallots.find((candidate) => candidate.core === core) ?? null,
                ballotsLocked,
              })}
              onSelectCore={onSelectCore}
            />
          ))}

          <span className="magi-system__title" aria-hidden="true">
            MAGI
          </span>
        </div>
      </div>
    </div>
  );
}

export { CORE_META, CORE_ORDER };
