---
name: hotel-schema-jsonld
description: Validate the Schema.org Hotel JSON-LD the template emits from site.json — completeness, validity, real facts. The component owns the structure; atlas audits the rendered output in dist/.
category: research
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, search, browser, web_fetch]
keywords: ['seo', 'schema.org', 'jsonld', 'structured-data', 'rich-results']
created_at: 2026-05-29
---

## When to use
In `qa`, when lens flags SEO or you audit structured data. The template's
`Seo.astro` **emits the Hotel JSON-LD automatically** from `site.json` —
name, url, address, telephone, email, geo, sameAs, image — with null fields
omitted. You do NOT write it; you **validate the output**.

## The contract — a valid Hotel entity
```json
{
  "@context": "https://schema.org",
  "@type": "Hotel",
  "name": "...", "url": "https://…/<locale>/",
  "address": "…", "telephone": "+…", "email": "…",
  "geo": { "@type": "GeoCoordinates", "latitude": …, "longitude": … },
  "image": "…", "sameAs": ["…"]
}
```
Fields are present only when the matching `site.json` value exists (the
component guards nulls). `name`, `url`, `address` are the floor.

## Approach
1. Build green → read the rendered `dist/<locale>/index.html`, extract the
   `application/ld+json` block.
2. Validate: required fields present, **no placeholder text** in any value,
   geo/telephone/email present iff `site.json` has them. Paste into Google's
   Rich Results Test → zero errors.
3. Missing facts → they're missing in `site.json` → **block on scout**, never
   invent. starRating is optional (omit if the hotel has none).
4. Hreflang: confirm `<link rel="alternate" hreflang="<lang>">` for every
   locale + `x-default` (also emitted by `Seo.astro`).
5. Want richer structured data (amenityFeature, per-room `HotelRoom`,
   checkin/checkout times)? The component doesn't emit them yet — **propose a
   template change to forge**; never hand-edit a project's components.

## Voice
- Cite the Rich Results result verbatim (URL + the error if a fail).
- Block missing facts to scout. The template owns JSON-LD structure (forge);
  atlas audits + advises, stays out of components.
