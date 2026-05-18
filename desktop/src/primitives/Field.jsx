import { forwardRef } from "react";

const Field = forwardRef(function Field(
  { mono = false, multiline = false, className = "", style, ...rest },
  ref,
) {
  const Tag = multiline ? "textarea" : "input";
  return (
    <Tag
      ref={ref}
      className={`ds-field ${mono ? "ds-field-mono" : ""} ${className}`.trim()}
      style={style}
      {...rest}
    />
  );
});

export default Field;
