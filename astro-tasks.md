# astro template — pending work

Asks for `satoshi-ltd/alpi-mirai-web-factory`, in template vocabulary only, priority order. Each item carries its evidence and an executable acceptance criterion.

## Product decision, not a defect — footer-only pages are reachable from header chrome

The header BAR renders `nav.primary` only. The header DRAWER additionally
aggregates the `navigation.footer` groups on all three tiers, so `gallery`,
`practical` and `faq` are reachable from header chrome. Defensible as designed —
the drawer is labelled "all pages" — but **on mobile the drawer IS the
navigation**, so "footer-only" has no meaning there. Three options, awaiting the
creator: leave it, exclude the `explore` group from the drawer, or add a
per-page footer-only flag the drawer respects.
