# Example hotel briefs

Realistic inputs used to exercise Web Factory manually. Each case is a
directory with an immutable `brief.md` and, when the client supplied media, an
`assets/` folder. Nothing here is copied into a project automatically: a run
receives the brief as its text input, and media lands in the clone's
`assets/source/` through the project's own git.

```bash
alpi -p mira workgroup launch \
  --recipe organizations/web-factory/recipes/hotel.yaml \
  --param slug=<case> \
  --input brief=organizations/web-factory/briefings/<case>/brief.md
```

Media, when the case has it, is copied into `projects/<slug>/assets/source/`
after launch and picked up with `@muse #task #media-update`:

```bash
cp organizations/web-factory/briefings/<case>/assets/* \
   ../web-factory/projects/<slug>/assets/source/
```

Every photo set was harvested from the hotel's own public site at the largest
resolution it publishes, deduplicated by content hash, and trimmed to about
thirty files — enough for a hero, one shot per room type, the amenity and
dining spaces, and a gallery. Each set includes the hotel's logo when the site
publishes one.

Only images the hotel itself owns are kept, and ownership is judged by what the
photo shows, never by the folder it sits in. Two sites here publish someone
else's photography as their own: roma illustrates an offer with a stock photo,
and maestranza's media folder is shared with 175 files belonging to its
platform's demo tenant. The stock photo and the demo tenant's rooms are not in
this set — but maestranza's logo, facade, reception and function rooms are,
because they are unmistakably its own despite sharing that folder. Discarding by
folder would have thrown them away.

A case's asset count is what the hotel actually has, which is sometimes
uncomfortably small; that is the input the factory has to work with, so it is
the input the fixture carries.

## Reference cases (measured)

| Case | Brief | Media | What it exercises |
|---|---:|---:|---|
| `roma-nueve-dos/` | 523 w | 33 files | The canonical case: a real commercial sheet with engine id, category, corporate data and 5 room types. Scored 64/80 against the hotel's own production site (49/80). Its full photo catalogue is the media-flow fixture. |
| `hotel-abad/` | 900 w | 34 files | The best-formed brief received so far: engine id, category, structured address, complete corporate block, 5 room types, parking price, check-in/out, pet policy, tone (`tú`), attractions and transport. It also carries the two mismatches worth rehearsing — the engine (`49561039`) publishes **ten** room types including apartments and a `Casa Valmardón` the brief never names, and the brief's contact email sits on a different domain (`hotelabad.com`) from the site (`hotelabadtoledo.com`). Both are gaps to record, never to reconcile by guessing. Room photos come from the engine at up to 6016×3384 and are named by room type. |
| `hotel-regio-cadiz/` | 670 w | 31 files | Six room types — the case where a room type went missing from content. Photos carry the hotel's own descriptive names (`buffet`, `cafeteria`, `entrada-nueva`, `doble-matrimonial-detalle`). |
| `hotel-oasis-plaza/` | 470 w | 31 files | Eight room types on a thin brief; gallery and nav wiring. Gallery filenames are generic (`galeria-N`) on purpose: it exercises Muse choosing slots by looking at the images rather than reading names. |
| `hotel-maestranza/` | 495 w | 20 files | **The reference format** — the brief `../BRIEFING.md` documents and the one to copy when writing a new case. Every required datum in eight sections, nothing the factory already knows. Its media set is the smallest here and the only one whose logo is reversed-only (white artwork, no light-ground variant), so it exercises the single-variant brand path. `hotel-maestranza/brief-original.md` keeps the sheet it replaced, for comparison. |

## Counter-examples — read before using

| Case | Why it is here |
|---|---|
| `roma-nueve-dos/brief-full-content.md` | The same hotel's entire published website reorganized as a brief (4,627 w, ×9 the commercial sheet). It produced a WORSE site — 52/80 — in two independent rounds: at that volume the intake agent transcribed the company name wrong (`MUCH` for `MUUCH`), flattened a structured address it had written correctly from the short brief, and the offer chain broke. Kept as the evidence behind the "short and dense, never long and narrative" rule in `../BRIEFING.md`. Do not use it as a model for new briefs. |
| `beachmate-resorts/` | Five independent hotels — each with its own category, address, legal entity and domain — sharing a brand and a loyalty programme. The template is single-property by contract, so this brief must be SPLIT into one project per property before launching. Kept as the multi-property policy example. |

## Model-format cases

These two were written before the measured rounds and, as it turns out, they
already follow the format those rounds proved right: short, dense, and opening
with a `## Project metadata` block that puts the operational data first —
booking property id, domain, tourism licence, booking fields — instead of
scattering it through the prose. Their photos also carry descriptive filenames
and a separate logo, which is exactly what the media flow needs.

| Case | Brief | Media | Notes |
|---|---:|---:|---|
| `jaime-primero/` | 885 w | 13 files | Family resort, content-rich: pools, splash park, show cooking. Engine id `100033800`. The widest amenity inventory of any case. |
| `kivir/` | 971 w | 11 files | City hotel with supplied photography and per-room images. Engine id `100376355`. |

Use their metadata block as the shape to ask clients for — see
`../BRIEFING.md`. `hotel-abad/` reaches the same shape from the other
direction: it keeps numbered prose sections but opens section 1 with the engine
id, so the operational data still arrives first. Either layout works; burying
the id in paragraph nine does not.

## Harvesting a new case

Two traps cost real time and are worth knowing before writing the crawler:

- **Extension-less CDNs.** `cdn2.paraty.es/<tenant>/images/<hash>` serves
  photos with no `.jpg` in the URL and an optional `=sNNN` size suffix, so a
  regex anchored on file extensions reports a site as having no images when it
  has plenty. Match on the host, not the extension.
- **Demo tenants on live sites.** The same host serves several tenants, and the
  tenant slug in the path — not the domain — says who owns the file. Check it
  before keeping anything.

On Mirai-hosted sites, `images.mirai.com/INFOROOMS/<engineId>/<id>/<id>_large.jpg`
also answers to `_original.jpg` at full resolution, and the surrounding markup
names each photo's room type. `static-resources*.mirai.com/wp-content/uploads/sites/<n>/`
paths carry WordPress resize suffixes (`-1024x683`); strip them to get the
original.
