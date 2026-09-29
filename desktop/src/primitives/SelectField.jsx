import Dropdown from "./Dropdown.jsx";

export default function SelectField({
  value,
  options,
  onChange,
  "aria-label": ariaLabel,
  disabled = false,
  portal = false,
  fullWidth = false,
  width = 280,
  align = "left",
}) {
  const current = options.find((option) => option.value === value) ?? options[0];
  return (
    <Dropdown
      trigger={{ label: current?.label ?? "" }}
      variant="field"
      align={align}
      width={width}
      portal={portal}
      fullWidth={fullWidth}
      disabled={disabled}
      aria-label={ariaLabel}
    >
      {({ close }) => options.map((option) => (
        <Dropdown.Row
          key={String(option.value)}
          active={option.value === value}
          caption={option.caption}
          onClick={() => {
            onChange?.(option.value);
            close();
          }}
        >
          {option.label}
        </Dropdown.Row>
      ))}
    </Dropdown>
  );
}
