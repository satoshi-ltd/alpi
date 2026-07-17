---
name: competitive-research
description: Browse 3 nearby/segment-peer hotel sites, capture what they do well + badly, ground the starter recommendation in evidence. Sub-procedure of intake-interview, runs before posting the starter call.
category: meta
version: 0.1.0
origin: user
requires_env: []
tools: [browser, web_fetch, web_search, research, write_file, read_file]
keywords: ['research', 'competitive', 'benchmark', 'starter-evidence', 'intake']
created_at: 2026-05-29
---

## When to use

During intake, after the hotel's basic facts are captured (name, location, segment, capacity) but before scout posts the starter recommendation. Lands findings in `projects/<slug>/intake.md § competitive`.

## Sample selection (3 sites)

Pick three that triangulate the segment:

1. **Direct local competitor**: hotel within 1km of similar size + segment
2. **Best-in-class in segment**: the cleanest example of the proposed starter's segment (boutique / budget / business / resort), even if geographically distant
3. **Same-locale leader**: top-ranked hotel website in the source locale's market (Google's first organic result for "[city] hotel boutique" or equivalent)

If the hotel is in an unusual segment (eco-lodge, capsule hotel, pod hostel), substitute the closest segment match and note the divergence.

## Approach

1. **For each of the 3**:
   - Open the site via `browser` (real render, not just HTML)
   - Capture: hero treatment, room presentation, gallery strategy, booking widget vendor, languages offered, price visibility, photography style
   - Lighthouse mobile score (use `browser` JS console: `chrome://lighthouse`)
   - JSON-LD presence (curl + grep for `application/ld+json`)
2. **Triangulate**:
   - What's table stakes in this segment? (e.g. gallery on home is universal for resorts; price-on-card is universal for budget)
   - What's a differentiator one site does well? (worth borrowing for the brief)
   - What's a common failure? (slow hero video, no hreflang, no mobile menu) — note as "avoid"
3. **Cross-check the starter recommendation**:
   - If 3/3 competitors lead with editorial photography + serif type → boutique starter is correct
   - If 3/3 lead with price-from + family-friendly content → budget or resort, depending on amenity density
   - If your hotel doesn't match the 3 competitors' dominant pattern → the hotel is mis-segmented; revisit with mira

## Output format

Append to `projects/<slug>/intake.md`:

```markdown
## Competitive scan · 2026-MM-DD

### <Competitor 1 name> (direct local)
- URL: <https://...>
- Segment fit: ★★★★☆
- Hero: <editorial-still / price-forward / location-led / fullbleed-gallery>
- Languages: ES, EN
- Lighthouse mobile: 87 / 100
- JSON-LD: present (Hotel + AggregateRating)
- Strengths: room-by-room prose, well-shot kitchen
- Weaknesses: slow hero (LCP 3.2s), no hreflang
- Borrow: room name strategy (own-name rooms vs deluxe-suite labels)

### <Competitor 2 name> (best-in-class)
... (same structure)

### <Competitor 3 name> (locale leader)
... (same structure)

## Synthesis
- Starter recommendation: <name>  (rationale: ...)
- Things to do better than the 3 above: <list>
- Risks: <patterns the 3 share that we should resist>
```

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| All 3 competitors are the same starter and yours doesn't fit | Mis-segmented by mira/scout | Revisit segment with intake.md facts, not gut |
| Can't find a direct competitor (rural / very small market) | Sparse market | Use "same-locale leader" + 2 best-in-class; note in synthesis |
| Competitor sites are blocked by Cloudflare / require JS | Browser-stealth needed | Use `browser` (playwright stealth) not `web_fetch` |

## Voice

- Specific over abstract: "Hero LCP 3.2s" beats "slow site"
- Always tag a strength AND a weakness per competitor — even bad sites have one good idea
- The synthesis section is the only one mira reads — make it land
