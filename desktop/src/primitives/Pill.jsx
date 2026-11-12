import Chip from "./Chip.jsx";

const STATE = { on: "on", err: "error", warn: "warn", off: "off" };

export default function Pill({ state, children }) {
  return <Chip state={STATE[state]}>{children}</Chip>;
}
