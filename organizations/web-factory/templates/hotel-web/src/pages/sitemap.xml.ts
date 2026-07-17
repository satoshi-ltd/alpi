import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import site from "../config/site";

// Self-owned sitemap (no @astrojs/sitemap dependency). Enumerates every
// locale × enabled page + room/post detail URLs. Read SITE_URL via Astro.site.
const PAGE_SEGMENT: Record<string, string | null> = {
  landing: "",
  rooms: "rooms",
  amenities: "amenities",
  dining: "dining",
  gallery: "gallery",
  offers: "offers",
  location: "location",
  about: "about",
  blog: "blog",
  roomDetail: null, // detail URLs come from the rooms collection below
};

export const GET: APIRoute = async ({ site: configured }) => {
  const origin = (configured ?? new URL("https://example-hotel.com"))
    .toString()
    .replace(/\/$/, "");
  const enabled = Object.entries(site.pages)
    .filter(([, on]) => on)
    .map(([k]) => k);

  const urls = new Set<string>();
  for (const lang of site.locales) {
    urls.add(`${origin}/${lang}/`);
    for (const page of enabled) {
      const seg = PAGE_SEGMENT[page];
      if (seg === null || seg === undefined || seg === "") continue;
      urls.add(`${origin}/${lang}/${seg}/`);
    }
  }

  if (enabled.includes("roomDetail")) {
    for (const r of await getCollection("rooms"))
      urls.add(`${origin}/${r.data.lang}/rooms/${r.data.slug}/`);
  }
  for (const e of await getCollection("legal")) {
    if (!(e.body ?? "").trim()) continue;
    urls.add(`${origin}/${e.data.lang}/legal/${String(e.id).split("/").pop()!.split(".")[0]}/`);
  }

  if (enabled.includes("blog")) {
    for (const p of await getCollection("posts")) {
      // `<slug>.<lang>.md` → slug is the part before the first dot.
      const slug = String(p.id).split("/").pop()!.split(".")[0];
      urls.add(`${origin}/${p.data.lang}/blog/${slug}/`);
    }
  }

  const body =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    [...urls].map((u) => `  <url><loc>${u}</loc></url>`).join("\n") +
    `\n</urlset>\n`;

  return new Response(body, { headers: { "Content-Type": "application/xml" } });
};
