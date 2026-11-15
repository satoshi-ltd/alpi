import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

export const MUTED_NAME = { "--name-light": "var(--ink-3)", "--name-dark": "var(--ink-3)" };

export function nameVars(accent, ground = "bgPane") {
  const light = nameTone(accent, palettes.light[ground]);
  const dark = nameTone(accent, palettes.dark[ground]);
  return light && dark ? { "--name-light": light, "--name-dark": dark } : null;
}
