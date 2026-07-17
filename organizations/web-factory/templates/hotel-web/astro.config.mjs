import { defineConfig } from "astro/config";
import site from "./src/config/site.json" with { type: "json" };

// One codebase, four themes. The active theme + brand tokens live in
// src/config/site.json — that's the only file the AI rewrites per hotel.
// The canonical origin comes from site.json `url` (the hotel's real domain);
// SITE_URL env can override for previews; the placeholder is last-resort and
// preflight blocks it from shipping. Sitemap is a self-owned endpoint
// (src/pages/sitemap.xml.ts), not the @astrojs/sitemap integration.
export default defineConfig({
  site: site.url || process.env.SITE_URL || "https://example-hotel.com",
  // i18n routing: /es/… /en/… — defaultLocale is NOT prefixed-redirected away,
  // we generate every locale under [lang].
  build: { format: "directory" },
});
