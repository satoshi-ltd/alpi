import { setTheme, useTheme } from "../../../lib/theme.js";

const OPTIONS = [
  ["system", "System"],
  ["light", "Light"],
  ["dark", "Dark"],
];

export function ThemeField() {
  const theme = useTheme();
  return (
    <div className="ds-seg" role="group" aria-label="Theme">
      {OPTIONS.map(([value, label]) => (
        <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>
          {label}
        </button>
      ))}
    </div>
  );
}
