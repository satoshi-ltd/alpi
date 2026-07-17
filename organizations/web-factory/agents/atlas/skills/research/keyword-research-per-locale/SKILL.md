---
name: keyword-research-per-locale
description: Research the keywords that anchor each locale's meta title/description + on-page copy, and advise quill on the per-page seo field. Advisory — atlas owns no build phase; the words land in the content.
category: research
version: 0.2.0
origin: user
requires_env: []
tools: [browser, web_fetch, web_search, research, read_file]
keywords: ['seo', 'keywords', 'i18n', 'search-intent', 'serp-analysis']
created_at: 2026-05-29
---

## When to use
When a project needs sharper search targeting. Atlas **advises**; quill
authors the `seo` field in the page content. The SEO *structure* — sitemap,
hreflang, JSON-LD, per-page `<title>`/meta — is baked into the template;
this skill is about the *words*.

## Inputs
- `projects/<slug>/intake.md` — segment, location, audience.
- `projects/<slug>/src/config/site.json` — name, geo, locales.

## Approach
Per locale (no cross-locale dependency):
1. Seed terms from intake: type + locality ("hotel boutique <city>"),
   amenity-led ("<city> hotel con piscina"), intent-led ("dónde dormir
   <city>").
2. Locale-pinned SERP analysis (`browser` / `web_search` with `hl`/`gl`) —
   real local SERPs, not US defaults. Note dominant intent + SERP features.
3. Score each: intent fit · competition · locale fit.
4. Shortlist 5–7 per locale; map 1 primary + 2–3 secondary **per page**.

## Output — advisory, no file
Post in `proj-<slug>`: per page, the primary + secondary keywords per locale.
- **quill** writes them into `content/pages/<page>.<lang>.json` →
  `seo { title, description, keywords }`.
- **lingua** keeps locale-native phrasing — never translate keywords across;
  re-research per locale.
There is no `keywords-<locale>.yaml`; the data lives in the page entries.

## Voice
- Honest about uncertainty — don't claim a search volume you can't verify.
- One primary per page; native phrasing always beats "translatable" phrasing.
