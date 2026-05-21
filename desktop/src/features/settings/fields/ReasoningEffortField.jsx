import Dropdown from "../../../primitives/Dropdown.jsx";

const OPTIONS = [
  { value: "", label: "Default", caption: "use provider default" },
  { value: "low", label: "Low", caption: "fastest, cheapest" },
  { value: "medium", label: "Medium", caption: "balanced" },
  { value: "high", label: "High", caption: "slower, more thorough" },
];

const LABEL_BY_VALUE = Object.fromEntries(OPTIONS.map((o) => [o.value, o.label]));

export function ReasoningEffortField({ value, onChange }) {
  const current = value ?? "";
  const label = LABEL_BY_VALUE[current] ?? "Default";
  return (
    <Dropdown
      trigger={{ label }}
      direction="down"
      align="left"
      width={240}
      variant="field"
    >
      {({ close }) => (
        <>
          {OPTIONS.map((opt) => (
            <Dropdown.Row
              key={opt.value || "off"}
              onClick={() => {
                onChange?.(opt.value);
                close?.();
              }}
              caption={opt.caption}
              selected={opt.value === current}
            >
              {opt.label}
            </Dropdown.Row>
          ))}
        </>
      )}
    </Dropdown>
  );
}
