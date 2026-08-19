import React, { useEffect, useId } from "react";

export function CoreResponseDialog({ open = false, model = null, onClose = () => {} }) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return undefined;

    const handleKeyDown = (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onClose();
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!model) return null;

  const fields = [
    ["question:", model.question],
    ["status:", model.status],
    ["error:", model.error],
    ["conditions:", model.conditions],
    ["full response:", model.fullResponse],
  ];

  return (
    <dialog
      open={open}
      className="core-response-dialog"
      aria-labelledby={titleId}
    >
      <header className="core-response-dialog__header">
        <h2 id={titleId}>{model.title}</h2>
        <button type="button" aria-label="Close core response" onClick={onClose}>
          X
        </button>
      </header>
      <div className="core-response-dialog__body">
        {fields.map(([label, value]) => (
          <React.Fragment key={label}>
            <strong>{label}</strong>
            <div>{value}</div>
          </React.Fragment>
        ))}
      </div>
    </dialog>
  );
}
