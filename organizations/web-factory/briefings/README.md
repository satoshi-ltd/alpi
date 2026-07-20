# Briefings

One folder per hotel — its brief and the photos the hotel supplied, together:

```
briefings/<slug>/
  brief.md            # the raw client brief (immutable; agents read, never edit)
  assets/             # hotel-supplied photos, named after their slot where possible
```

Run a hotel through the pipeline:

```bash
alpi -p mira workgroup launch \
  --recipe organizations/web-factory/recipes/hotel.yaml \
  --param slug=<slug> \
  --input brief=briefings/<slug>/brief.md \
  --assets briefings/<slug>/assets
```

`--input brief=<file>` seeds `projects/<slug>/brief.md` (the recipe's declared
`brief` input) before kickoff. `--assets <dir>` copies the hotel's photos into
`projects/<slug>/assets/` before kickoff; muse triages and restores them
(`kind: restored`). Drop `--assets` when the hotel supplied no photos.

## What's here

- `golden/`, `visual/`, `restore/` — the three automated acceptance fixtures
  (`tools/acceptance.py golden|visual|restore`).
- `boutique/`, `budget/`, `business/`, `resort/` — one rough sales-note brief
  per theme, for manual theme testing.
- `jaime-primero/` — a real hotel (Hotel Jaime I, Salou).

## Photos: tracked vs ignored

Tiny fixture photos (e.g. `restore/assets/`) are **committed** — they're part
of acceptance and must be reproducible. Real-client photo folders carry a local
`assets/.gitignore` (`*` + `!.gitignore`) so the binaries stay out of the repo
while the folder itself is self-documenting. Copy that `.gitignore` into any new
real-client `assets/`.
