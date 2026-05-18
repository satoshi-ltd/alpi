import AlpiSilhouette from "./AlpiSilhouette.jsx";

export default function Logo({ color, className, style }) {
  return (
    <AlpiSilhouette
      color={color || "var(--ink)"}
      className={className}
      style={style}
    />
  );
}
