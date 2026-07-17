// site-schema.ts — CODE (fixed layer; the AI never edits this).
// The AI authors src/config/site.json (PURE DATA). site.ts loads that JSON and
// validates it through siteSchema here, so an invalid config fails the build
// with a clear Zod error — the same safety gate the content collections use.
import { z } from "astro/zod";

export type ThemeKey = "boutique" | "budget" | "business" | "resort";

export const siteSchema = z.object({
  theme: z.enum(["boutique", "budget", "business", "resort"]),
  tokens: z
    .object({
      accent: z.string().optional(),
      accent2: z.string().optional(),
      ink: z.string().optional(),
      paper: z.string().optional(),
      surface: z.string().optional(),
      fontHead: z.string().optional(),
      fontBody: z.string().optional(),
    })
    .optional(),
  brand: z.object({
    name: z.string(),
    tagline: z.string().optional(),
    logo: z.string().optional(),
  }),
  // Canonical site origin (e.g. "https://casabahia.com"). Drives canonical,
  // hreflang, sitemap, robots, JSON-LD. astro.config reads it as `site`.
  // Omit only if the domain is genuinely unknown — preflight then blocks the
  // placeholder so it can't ship.
  url: z.string().url().optional(),
  locales: z.array(z.string()).min(1),
  defaultLocale: z.string(),
  contact: z.object({
    phone: z.string().optional(),
    email: z.string().optional(),
    address: z.string().optional(),
    coords: z.object({ lat: z.number(), lng: z.number() }).optional(),
  }),
  booking: z.object({
    provider: z.string(),
    propertyId: z.string(),
    fields: z.array(z.string()),
  }),
  nav: z.object({
    primary: z.array(z.string()),
    // i18n key suffix rendered as t(`cta.${cta}`) — free text would print the raw key in the header.
    cta: z.enum(["book", "reserve"]),
    showLangSwitcher: z.boolean(),
  }),
  pages: z.record(z.boolean()),
  social: z.array(z.object({ label: z.string(), href: z.string() })).optional(),
});

export type SiteConfig = z.infer<typeof siteSchema>;

// Maps token overrides → inline CSS custom properties for <html>.
export function tokenStyle(t: SiteConfig["tokens"]): string {
  if (!t) return "";
  const map: Record<string, string> = {
    accent: "--color-accent", accent2: "--color-accent-2", ink: "--color-ink",
    paper: "--color-paper", surface: "--color-surface",
    fontHead: "--font-head", fontBody: "--font-body",
  };
  return Object.entries(t)
    .filter(([, v]) => v)
    .map(([k, v]) => `${map[k]}:${v}`)
    .join(";");
}
