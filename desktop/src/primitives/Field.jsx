import { forwardRef, useId } from "react";

const Field = forwardRef(function Field(
  { mono = false, multiline = false, className = "", style, helper, error, ...rest },
  ref,
) {
  const Tag = multiline ? "textarea" : "input";
  const noteId = useId();
  const note = error || helper;
  const describedBy = [rest["aria-describedby"], note ? noteId : null].filter(Boolean).join(" ") || undefined;
  const control = (
    <Tag
      ref={ref}
      className={`ds-field ${mono ? "ds-field-mono" : ""} ${className}`.trim()}
      style={style}
      {...rest}
      aria-invalid={error ? true : rest["aria-invalid"]}
      aria-describedby={describedBy}
    />
  );
  if (!note) return control;
  return (
    <span className="ds-field-wrap">
      {control}
      <span id={noteId} className={`ds-field-note${error ? " is-error" : ""}`} role={error ? "alert" : undefined}>{note}</span>
    </span>
  );
});

export default Field;
