# URL conventions

Atlas owns these rules; they apply to every project. Deviations require a
`template` workgroup ADR.

## Structure

- Locale prefix: `/<locale>/...` for every locale, including the source one.
  No "default locale at root" — keeps the routing rule uniform.
- Trailing slash: always on (`/es/rooms/`, not `/es/rooms`). Astro config
  enforces `trailingSlash: "always"`.
- Lowercase, kebab-case slugs.

## Per-locale slug strategy

Slugs are **locale-native** — they're SEO-relevant signals and should be
translated, not transliterated.

| Page key | es | en | fr | de | it | pt |
|---|---|---|---|---|---|---|
| home | `/` (`/es/`) | `/` (`/en/`) | `/` (`/fr/`) | `/` (`/de/`) | `/` (`/it/`) | `/` (`/pt/`) |
| rooms | `/es/habitaciones/` | `/en/rooms/` | `/fr/chambres/` | `/de/zimmer/` | `/it/camere/` | `/pt/quartos/` |
| amenities | `/es/servicios/` | `/en/amenities/` | `/fr/services/` | `/de/ausstattung/` | `/it/servizi/` | `/pt/servicos/` |
| gallery | `/es/galeria/` | `/en/gallery/` | `/fr/galerie/` | `/de/galerie/` | `/it/galleria/` | `/pt/galeria/` |
| location | `/es/ubicacion/` | `/en/location/` | `/fr/emplacement/` | `/de/lage/` | `/it/posizione/` | `/pt/localizacao/` |
| booking | `/es/reservar/` | `/en/booking/` | `/fr/reservation/` | `/de/buchen/` | `/it/prenota/` | `/pt/reservar/` |
| contact | `/es/contacto/` | `/en/contact/` | `/fr/contact/` | `/de/kontakt/` | `/it/contatti/` | `/pt/contato/` |

> Day 1 the template ships English slugs for every page across all locales.
> Lingua + atlas swap to locale-native slugs as a per-project step (one
> `astro:get-static-paths` mapping change) during the **build** state of the
> state machine.

## Canonical + hreflang

- Canonical: per-locale, points to the absolute URL for that locale's page.
- hreflang: every page declares an alternate for every locale shipped, plus
  `x-default` pointing to the source locale.

## Redirects

- `/` → `/<source-locale>/` (301)
- Trailing-slash normalisation (handled by Astro static export + CDN).
- Old URLs from legacy site: list them in `seo/legacy-redirects.yaml` per
  project; atlas owns the migration map.
