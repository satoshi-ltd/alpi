import { useEffect, useRef } from "react";

export default function Textarea({ value, className, style, ...rest }) {
  const ref = useRef(null);
  const minHeightRef = useRef(null);

  useEffect(() => {
    const ta = ref.current;
    if (!ta) return;
    if (minHeightRef.current === null) {
      minHeightRef.current = ta.scrollHeight;
    }
    ta.style.height = "auto";
    const natural = Math.max(ta.scrollHeight, minHeightRef.current);
    const maxH = parseFloat(getComputedStyle(ta).maxHeight);
    const capped = Number.isFinite(maxH) && maxH > 0 ? Math.min(natural, maxH) : natural;
    ta.style.height = `${capped}px`;
    ta.style.overflowY = capped < natural ? "auto" : "hidden";
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
