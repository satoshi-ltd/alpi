# Briefings

One folder per hotel — its brief and the photos the hotel supplied, together:

```
briefings/<slug>/
  brief.md            # the raw client brief (immutable; agents read, never edit)
  assets/             # hotel-supplied photos, named after their slot where possible
```

Run a hotel through the pipeline:

```bash
new-project.py <slug> --brief briefings/<slug>/brief.md --assets briefings/<slug>/assets/
```

`new-project.py` copies the brief to `projects/<slug>/brief.md` and the photos
into the project; muse triages and restores them (`kind: restored`).

## What's here

- `golden/`, `visual/`, `restore/` — the three automated acceptance fixtures
  (`acceptance.py golden|visual|restore`).
- `boutique/`, `budget/`, `business/`, `resort/` — one rough sales-note brief
  per theme, for manual theme testing.
- `jaime-primero/` — a real hotel (Hotel Jaime I, Salou).

## Photos: tracked vs ignored

Tiny fixture photos (e.g. `restore/assets/`) are **committed** — they're part
of acceptance and must be reproducible. Real-client photo folders carry a local
`assets/.gitignore` (`*` + `!.gitignore`) so the binaries stay out of the repo
while the folder itself is self-documenting. Copy that `.gitignore` into any new
real-client `assets/`.
