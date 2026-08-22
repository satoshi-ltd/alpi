import { ALPI_PATHS, ALPI_VIEWBOX } from "../../../common/alpiMark.mjs";

export default function AlpiSilhouette({ color, style, className }) {
  return (
    <svg
      width="72"
      height="72"
      viewBox={ALPI_VIEWBOX}
      role="img"
      aria-label="alpi"
      className={className}
      style={{ color: color || "currentColor", display: "block", ...style }}
    >
      {ALPI_PATHS.map((d, i) => (
        <path key={i} d={d} fill="currentColor" />
      ))}
    </svg>
  );
}
