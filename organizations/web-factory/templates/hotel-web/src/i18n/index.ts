import es from "./es.json";
import en from "./en.json";
import fr from "./fr.json";
import de from "./de.json";
import it from "./it.json";
import pt from "./pt.json";
import nl from "./nl.json";
import zhHans from "./zh-Hans.json";
import ca from "./ca.json";
import ru from "./ru.json";

// Supported UI-chrome locales. A project may declare ONLY these in
// site.json.locales — scout's rubric is constrained to this set so chrome
// never falls back to another language. Adding a locale = drop its dict here.
const dicts: Record<string, Record<string, string>> = {
  es, en, fr, de, it, pt, nl, ca, ru, "zh-Hans": zhHans,
};

// t(locale) → a translate function. Falls back to the key if missing.
export function useT(locale: string) {
  const d = dicts[locale] ?? dicts.es;
  return (key: string) => d[key] ?? key;
}

export const locales = Object.keys(dicts);
