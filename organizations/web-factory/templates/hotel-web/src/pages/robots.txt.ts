import type { APIRoute } from "astro";

// Self-owned robots.txt — emits from Astro.site (driven by site.json `url`),
// never a hardcoded domain. Points crawlers at the real sitemap.
export const GET: APIRoute = ({ site }) => {
  const origin = (site ?? new URL("https://example-hotel.com"))
    .toString()
    .replace(/\/$/, "");
  const body = `User-agent: *\nAllow: /\n\nSitemap: ${origin}/sitemap.xml\n`;
  return new Response(body, { headers: { "Content-Type": "text/plain" } });
};
