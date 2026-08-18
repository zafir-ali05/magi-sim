import React, { useEffect, useId, useRef } from "react";

export function CoreResponseDialog({ open = false, model = null, onClose = () => {} }) {
  const dialogRef = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const handleCancel = (event) => {
    event.preventDefault();
    onClose();
  };

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
      ref={dialogRef}
      className="core-response-dialog"
      aria-labelledby={titleId}
      onCancel={handleCancel}
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
