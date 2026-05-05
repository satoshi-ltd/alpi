import { useEffect, useRef } from "react";

export default function Textarea({ value, className, style, ...rest }) {
  const ref = useRef(null);
  const minHeightRef = useRef(null);

  useEffect(() => {
    const ta = ref.current;
    if (!ta) return;
    // Capture natural min-height (from rows attr + CSS) on first render.
    if (minHeightRef.current === null) {
      minHeightRef.current = ta.scrollHeight;
    }
    ta.style.height = "auto";
    ta.style.height = `${Math.max(ta.scrollHeight, minHeightRef.current)}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      className={className}
      style={{ resize: "none", overflow: "hidden", ...style }}
      {...rest}
    />
  );
}
