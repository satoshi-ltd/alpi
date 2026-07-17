# WCAG 2.1 AA — running checklist

Subset of the WCAG criteria that apply to every hotel website the factory ships.
Lens runs through this top to bottom before greenlighting launch.

## Perceivable
- **1.1.1** Non-text content has text alternative (alt or aria)
- **1.3.1** Info and relationships preserved when CSS is off (semantic HTML)
- **1.3.2** Meaningful sequence (DOM order matches visual order)
- **1.3.4** Orientation not restricted to portrait/landscape
- **1.4.3** Contrast: 4.5:1 normal text, 3:1 large text, 3:1 UI components
- **1.4.4** Text resizable to 200% without loss of content
- **1.4.10** Reflow at 320 CSS pixels without horizontal scroll
- **1.4.11** Non-text contrast (UI components, focus indicators) ≥ 3:1

## Operable
- **2.1.1** All functionality available from keyboard
- **2.1.2** No keyboard trap
- **2.4.1** Skip-to-content link present
- **2.4.2** Page titled (`<title>` per page per locale)
- **2.4.3** Focus order matches reading order
- **2.4.4** Link purpose clear from context (no "click here")
- **2.4.6** Headings and labels descriptive
- **2.4.7** Focus indicator visible
- **2.5.5** Touch targets ≥ 44×44 CSS pixels

## Understandable
- **3.1.1** Page language declared (`<html lang>`)
- **3.1.2** Language of parts declared (e.g. quotes in other locales)
- **3.2.1** Focus doesn't trigger context change
- **3.2.2** Input doesn't trigger context change without warning
- **3.3.1** Error identification (forms)
- **3.3.2** Labels or instructions for user input
- **3.3.3** Error suggestion (forms with constrained input)

## Robust
- **4.1.2** Name, role, value programmatically determinable (use semantic HTML
  before ARIA; ARIA only when no native element fits)

## Tooling Lens uses
- axe DevTools (browser extension) for automated pass
- Lighthouse a11y audit for the smoke score
- Manual keyboard pass (Tab through every page, no surprises)
- Voiceover / NVDA on the main flow (home → rooms → booking) at least once
- Color contrast: Stark plugin or webaim.org checker on every starter-token
  combo before launch

## Not in scope (yet)
- AAA criteria (alpi factory targets AA)
- Forms that go beyond contact / booking (we don't build those today)
- Audio / video content (no media on the standard page set)
