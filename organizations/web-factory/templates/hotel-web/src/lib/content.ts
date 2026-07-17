import { getCollection } from "astro:content";

// Locale-filtered, order-sorted collection fetch. Every entry has a `lang`.
export async function byLocale(collection: any, locale: string) {
  const all = await getCollection(collection);
  return all
    .filter((e: any) => e.data.lang === locale)
    .sort((a: any, b: any) => (a.data.order ?? 0) - (b.data.order ?? 0));
}

// Single page-copy entry, e.g. pageCopy("home", "es"). Tolerant to Astro's
// data-collection id format (with or without the .json extension).
export async function pageCopy(name: string, locale: string) {
  const all = await getCollection("pages");
  const hit = all.find((e: any) => {
    const id = String(e.id).replace(/\.json$/, "");
    return e.data.lang === locale && (id === `${name}.${locale}` || id.startsWith(`${name}.`));
  });
  return hit?.data ?? null;
}

// Build a locale-prefixed path: localePath("es", "rooms") → "/es/rooms".
export function localePath(locale: string, ...parts: string[]) {
  return "/" + [locale, ...parts.filter(Boolean)].join("/");
}
