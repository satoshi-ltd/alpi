// site.ts — CODE (fixed layer). Loads the AI-authored src/config/site.json and
// validates it through siteSchema. The AI edits site.json (PURE DATA), never
// this file. An invalid site.json fails the build with a clear Zod error.
import data from "./site.json";
import { siteSchema, tokenStyle } from "./site-schema";
import type { SiteConfig, ThemeKey } from "./site-schema";

const site: SiteConfig = siteSchema.parse(data);

export default site;
export { tokenStyle };
export type { SiteConfig, ThemeKey };
