# design/

The visual reference for both clients, generated from the code's own values.

- `index.html` · System: tokens from `common/tokens.mjs`, desktop primitives, mobile primitives.
- `desktop.html` · every desktop screen, 1280 wide.
- `mobile.html` · every phone and fold screen.
- `audit.html` · the parity and overlays / view-states tables with their status.

Regenerate after a change to a component or token:

```bash
python3 design/build.py
```

The same run refreshes `design/canvas/project/`, the artboards behind the shared
claude.ai canvas; the pages here are the source, the canvas is the mirror.
`design/src/` holds the generator: one module per family of boards.
