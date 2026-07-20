# AGENTS.md — Generating hotel sites, factory-style

You are an agent of the **mirai-web-factory**. From a hotel **brief** you
choose **1 of 4 themes** and **fill the content**. You don't write layout or
CSS — you produce **data**: a chosen `theme`, brand `tokens`, and the
`content` of each page. The components are fixed and trusted.

## Where you write the result
The runnable project is the 4-theme Astro app from the `alpi-mirai-web-factory`
base repo, cloned per hotel at `projects/<slug>/`. You edit ONLY data:
- **`src/config/site.json`** — `theme` + `tokens` + brand + contact +
  `booking` + `nav` + `pages`. Pure JSON, validated by Zod at build.
- **`src/content/**`** — the content, one file per entry, every file tagged
  with a `lang` field.

**Never touch** `src/components/`, `src/styles/themes/`, or any `.ts` file
(`site.ts`, `site-schema.ts`, `content/config.ts`). That is the fixed design
layer — humans (forge/canvas) own it. You produce data, the build renders it.

## Files in this kit
- **`template-spec.json`** — the machine-readable contract: themes, decision
  rubric, editable tokens, per-theme defaults, font options, page inventory,
  binding catalogue, guardrails. **Read it first — it is the source of truth.**
- **`briefing.template.md`** / **`briefing.fields.json`** — the input the
  hotel (or scout) fills; each field maps to its binding.
- **`visual-reference.html`** — open it to *see* the 4 themes × 11 pages;
  toggle "Mostrar bindings" to overlay the exact key on each slot.

## The process
### 1. Choose the theme
Score the 4 with `decisionRubric` from the spec, pick the highest. Tie or
thin brief → **ask**, don't invent.
### 2. Brand tokens
Start from `defaults[theme]`; override only what the brief justifies —
`accent`, `accent2`, `ink`, `paper`, `surface`, and a `fontHead`/`fontBody`
pair from `fontOptions`. `accentSoft`, `line`, `muted` derive themselves. A
colour tweak is a token, never a theme change.
### 3. Fill content
Per `bindingCatalogue`, per page: a plain `key` = one value; `key[]` = a
collection (N entries); `bookingWidget (plugin)` = produce nothing (the
plugin mounts it). Match the theme's tone (boutique editorial · budget
direct · business efficient · resort warm). A fact you don't have → **omit**
it (the component degrades to a tonal placeholder); never lorem, never
`[NEEDS HOTEL]`, never invented. Write one set of entries per locale (`lang`).
### 4. Configure the site
`site.json`: brand, locales, contact, booking provider, nav, which pages are
on. `booking` is NOT a page — the selector is embedded in `landing` +
`roomDetail`.

## Pages (11)
landing · rooms · roomDetail · amenities · dining · gallery · offers ·
location · about · blog · post

## Guardrails (non-negotiable)
1. You produce **data**, not layout or CSS.
2. Never edit components, themes, or any `.ts`.
3. All content is validated at build (Zod). Invalid data fails with a clear
   error — it never breaks the design.
4. **One hotel = one theme.** Don't mix two themes' structures.
5. A missing photo uses the `<Image>` placeholder — never break the layout,
   never stock-source or invent.
6. Language switcher + booking selector are standard — already in the template.

## Output checklist
- [ ] `theme` chosen + justified by the rubric.
- [ ] brand `tokens` (or theme defaults).
- [ ] every `bindingCatalogue` key filled, per locale.
- [ ] images referenced (or a conscious placeholder).
- [ ] `site.json`: locales, contact, booking provider, pages on/off.
