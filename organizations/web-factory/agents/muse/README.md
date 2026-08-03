# Muse — asset producer

Owns the media decision, not the pixels: maps every required slot in
`assets/manifest.yaml` to a supplied file (`kind: supplied`, always
`assets/source/<file>` root-relative paths), a descriptive local placeholder,
or explicitly authorized generation. Slot names come from Scout's canonical
slug table (`<prefix>-<slug>`) — never invented. Deliberately offline: never
fetches media from the web.

- Writes: `assets/manifest.yaml` and nothing else. `assets/source/` is client
  input and read-only here — the output is decisions about files, never files.
- Skills: `analyze-image`; `generate-image` and `make-logo-svg` only on explicit
  written authorization naming them. A hotel with no logo is not authorization:
  the template's typographic lockup is the intended fallback.
- Operative contract: `agent.md`.
