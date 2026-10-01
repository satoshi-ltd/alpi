# design/ — agent instructions

The design kit is the visual reference for desktop and mobile, generated from the repository's own tokens, components and
screens. It is not a document: it shows what ships and what is proposed. The root `AGENTS.md` carries the code-time rules;
this file is the whole contract of the kit.

## Generator

- `python3 design/build.py` rewrites every `design/*.html`, `boards.css`, `favicon.svg` and the canvas artboards under
  `design/canvas/project/`. It needs `node` on PATH to read the shared icons in `common/`.
- `design/src/` is the source, one module per family of boards: `build.py` (page shell and nav), `gen.py` (canvas index, mobile screens),
  `system_boards.py`, `desktop_boards.py`, `desktop_overlays.py`, `conversation_boards.py`, `mobile_overlays.py` and
  `proposals.py` (the proposal boards). Never edit a generated file by hand.
- `design/drift.py` runs the build and exits 1 naming every file it had to regenerate; `scripts/validate.py` runs it as the
  `design` step. `scripts/` holds no design file.
- `design/README.md` is the human note; this file owns the contract.

## Tabs

- `System` (tokens and components of both clients), `Desktop`, `Mobile`, `Proposals`, in that order.
- The Fold is rendered inside Mobile, not on a tab of its own.
- A new interface adds its tab before Proposals.
- There is no Open work page: `docs/ROADMAP.md` already is the list of what is left.

## Proposals

The Proposals page holds purely visual ideas, only while they are proposals; it shows an empty state when there are none.
Each idea is one board in `design/src/proposals.py`, an entry of `PROPOSALS` with these fields:

- `id` — stable, never reused; the ROADMAP task takes the same ID.
- `client` — `desktop` or `mobile`.
- `area` — the screen or field it touches.
- `title` — what the board proposes.
- `why` — the evidence and the recommendation.
- `now` — a function drawing what exists, with the kit's own classes.
- `proposed` — a function drawing the proposal, with the kit's own classes.
- `accept` — what proves it done.
- `h` — the board height in pixels.

## Lifecycle

One place per state:

- **Idea:** a board only, never a Proposed entry in the ROADMAP.
- **Approved:** the creator moves it into Queue as one `ui` entry with the same ID, whose accept is the board.
- **Shipped:** the board and the ROADMAP entry are deleted together, the changelog and the ARCHITECTURE section record it,
  and `design/` is regenerated.

Tasks with no visual component (behaviour, data, infrastructure) live only in the ROADMAP and get no board.

### Split rule

A task that mixes logic and a screen is split. The screen is board `UI-<TASKID>`; the logic stays under its own ID with the
line "the interface follows board UI-<TASKID>" in its accept. A board ID never equals a non-`ui` task ID.

## Views in sync

The views (System and every interface tab) show what ships; Proposals shows what is proposed. Any change to what desktop or
mobile shows or how it behaves updates every affected board in the same change, regenerated and rendered in light and dark.
Shipping a proposal is one change: the code, the views regenerated to show the new design, the board deleted, its `ui` line
deleted, and the changelog and ARCHITECTURE updated. A board left standing after its change shipped, or a view that still
draws the old look, fails the adversarial review before the commit.

## Favicon

Every page carries the project's icon: `design/favicon.svg` is a copy of `site/assets/alpi-favicon.svg` made by the
generator, and every page, including the canvas artboards, links it by a relative path, so the kit stays self-contained.

## Canvas mirror

`design/canvas/project/` holds one `<Page>-<Board>.dc.html` artboard per board plus `canvas.json`, the artboards behind the
shared claude.ai canvas. The pages in `design/` are the source and the canvas is the mirror; the same build refreshes both,
and a stale or orphaned artboard fails the tests.

## Tests

- `tests/test_design_kit.py` builds the kit into a temporary directory and fails until `design/` is regenerated. It enforces:
  every page carries the shipped tokens and the version banner; the nav is exactly System, Desktop, Mobile, Proposals and no
  Open work page exists; the committed files equal what the generator writes and the canvas holds the same artboards;
  every page and artboard links the favicon copy inside `design/`; boards follow the theme except the literal swatches;
  every ROADMAP task of type `ui` has a board with its ID, names the board in its accept, and a board without a task is a
  valid pending proposal carrying its parts; board IDs are unique and a split task names its `UI-<TASKID>` board; the
  parser counts raw markers against parsed ones; `design/AGENTS.md` exists and `scripts/` holds no design file.
- Design drift is `design/drift.py`, covered by `tests/test_release_scripts.py`, and `python3 scripts/validate.py` runs it
  with the kit test whenever a path under `design/`, `common/`, the client sources or the kit test changes.

## Particulars of alpi

- Colour, type, space and radius come from `common/tokens.mjs` and `desktop/src/styles/tokens.css`; the System page draws
  them and shows `desktop <version> · mobile <version>` read from the two `package.json` files.
- `design/` releases no product: a design-only commit does not bump a version, and rides with the first client commit when
  a task also changes a client.
- Boards are drawn in the light palette and the build rewrites those literals to the kit's tokens so the theme switch
  reaches them; only the swatches of `System-Tokens.dc.html` stay literal.
- Mobile boards show the phone's own grammar; a fold or tablet renders the desktop layout at scale.
- `CLAUDE.md`, here and at the root, is a local pointer listed in `.gitignore` and never committed; tests read it only where it exists.
