import { motion, useReducedMotion } from "motion/react";

export const CORE_DETAILS = {
  "MELCHIOR-1": {
    facet: "SCIENTIST",
    lens: "Evidence / systems",
    accent: "amber",
    glyph: "△",
  },
  "BALTHASAR-2": {
    facet: "MOTHER",
    lens: "Care / stewardship",
    accent: "green",
    glyph: "□",
  },
  "CASPER-3": {
    facet: "WOMAN",
    lens: "Desire / human reality",
    accent: "red",
    glyph: "○",
  },
};

const STATUS_COPY = {
  active: "ACTIVE",
  locked: "VOTE SEALED",
  decided: "DECIDED",
  standby: "STANDBY",
};

function formatConfidence(confidence) {
  return `${Math.round(confidence * 100)}% confidence`;
}

export function CorePanel({
  core,
  acts,
  active,
  ballot,
  ballotsLocked,
  phase,
}) {
  const reduceMotion = useReducedMotion();
  const details = CORE_DETAILS[core];
  const latestAct = acts.length > 0 ? acts[acts.length - 1] : null;
  const hasDecision = Boolean(ballot);
  const status = hasDecision
    ? "decided"
    : ballotsLocked
      ? "locked"
      : active
        ? "active"
        : "standby";
  const labelId = `${core.toLowerCase()}-label`;

  return (
    <motion.article
      className={`core-panel core-panel--${details.accent} core-panel--${status}`}
      aria-labelledby={labelId}
    >
      <header className="core-panel__header">
        <div className="core-panel__identity">
          <span className="core-glyph" aria-hidden="true">
            {details.glyph}
          </span>
          <div>
            <p className="micro-label">CORE IDENTITY</p>
            <h2 id={labelId}>{core}</h2>
            <p className="core-panel__facet">
              {details.facet} <span aria-hidden="true">/</span> {details.lens}
            </p>
          </div>
        </div>
        <div className="core-status" aria-label={`${core} status: ${STATUS_COPY[status]}`}>
          <motion.span
            className="status-mark"
            aria-hidden="true"
            animate={
              !reduceMotion && active && !hasDecision
                ? { opacity: [0.45, 1, 0.45], scale: [0.9, 1.08, 0.9] }
                : { opacity: 1, scale: 1 }
            }
            transition={
              !reduceMotion && active && !hasDecision
                ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0 }
            }
          />
          <span>{STATUS_COPY[status]}</span>
        </div>
      </header>

      <div className="core-panel__body">
        {latestAct ? (
          <div className="core-latest">
            <div className="core-latest__meta">
              <span>LAST SIGNAL</span>
              <span>
                R{latestAct.round} · {latestAct.act.kind}
              </span>
            </div>
            <p>{latestAct.act.content}</p>
          </div>
        ) : (
          <div className="core-latest core-latest--empty">
            <div className="core-latest__meta">
              <span>LAST SIGNAL</span>
              <span>NO COMMIT</span>
            </div>
            <p>{phase === "OPENING" ? "Awaiting independent opening analysis." : "Awaiting a committed signal."}</p>
          </div>
        )}

        <div className="core-ballot" aria-live="polite">
          {ballot ? (
            <motion.div
              key={`${ballot.core}-${ballot.vote}`}
              className="ballot-reveal"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.45, ease: "easeOut" }}
            >
              <div className="core-latest__meta">
                <span>FINAL BALLOT</span>
                <span>{formatConfidence(ballot.confidence)}</span>
              </div>
              <div className={`vote-chip vote-chip--${ballot.vote.toLowerCase()}`}>
                <span className="vote-shape" aria-hidden="true">
                  {ballot.vote === "AGREE" ? "＋" : ballot.vote === "DISAGREE" ? "−" : "◇"}
                </span>
                <span>{ballot.vote}</span>
              </div>
              <p className="ballot-rationale">{ballot.rationale}</p>
              {ballot.conditions.length > 0 ? (
                <ul className="condition-list">
                  {ballot.conditions.map((condition) => (
                    <li key={condition}>{condition}</li>
                  ))}
                </ul>
              ) : null}
            </motion.div>
          ) : ballotsLocked ? (
            <div className="ballot-locked">
              <span className="lock-shape" aria-hidden="true">
                ◈
              </span>
              <div>
                <span className="micro-label">PRIVATE BALLOT</span>
                <strong>VOTE SEALED</strong>
                <span>Reveal pending all-core lock.</span>
              </div>
            </div>
          ) : (
            <div className="ballot-pending">
              <span className="micro-label">PRIVATE BALLOT</span>
              <span>Not yet requested.</span>
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}
