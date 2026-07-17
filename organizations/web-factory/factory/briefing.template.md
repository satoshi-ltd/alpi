# Hotel briefing — input for the factory

> Fill in what you know. Fields marked **★ decision** help pick the template
> (boutique / budget / business / resort). The rest feeds the content.
> Anything you leave empty is **omitted or recorded as a gap** — the factory
> never invents facts to fill a hole. Only the **visual** layer may fall back to
> an on-brand tonal placeholder; a missing room price, address, or review stays
> blank (and may block launch QA) until you provide it. You don't write code or
> pick a template — the factory does that from this briefing.

---

## 0. Meta
- **Site languages:** (e.g. ES, EN) →
- **Primary language:** →
- **Domain / project name:** →

---

## 1. The hotel — who you are  ★ decision
> This weighs most when picking the template. Be concrete.

- **Hotel name:** →
- **Type / category:** (boutique, hostel, urban business, resort, apart-hotel…) →
- **Stars / level:** →
- **Number of rooms:** →
- **Location:** (city, coast, mountain, island, near airport/station…) →
- **Who is it for?** (couples, families, business traveller, backpacker, luxury…) →
- **Price level:** (budget / mid / high / luxury) →
- **In one sentence, what makes you special?** →
- **You compete mainly on…** (price / design / location / experiences / service) →
- **3 words that describe the brand's feel:** →

---

## 2. Brand and visual style
> Optional. If you leave it empty, the factory uses the chosen template's defaults.

- **Do you have a logo?** (attach file or path) →
- **Slogan / tagline:** →  *(→ used in the hero)*
- **Brand colours** (hex if you have them): primary → · secondary →
- **Typography preference:** (elegant serif / modern sans / rounded / let the factory decide) →
- **Writing tone:** (warm, sober, evocative, playful, premium…) →
- **Reference sites you like:** →

---

## 3. Contact and booking
- **Phone:** →
- **Email:** →
- **Full address:** →  *(→ location / footer)*
- **Coordinates (lat,lng) if you have them:** →
- **Booking engine / plugin:** (Cloudbeds, Mirai, SiteMinder…) + ID →  *(the factory does NOT build the booking flow, only configures the plugin)*
- **Social media:** →

---

## 4. Content by section
> Maps to each page's bindings. Fill per language where it applies.

### 4.1 Hero (cover)
- **Main headline:** →  *(hero.title)*
- **Subtitle / support line:** →  *(hero.subtitle)*
- **Small top text (kicker):** →  *(hero.eyebrow)*
- **Main photo:** →  *(hero.image)*

### 4.2 About the hotel / story
- **Headline:** →  *(about.title)*
- **Text (1–2 paragraphs):** →  *(about.body)*
- **Photo:** →  *(about.image)*

### 4.3 Rooms  *(repeat the block per room type)*
Per room:
- **Name:** →  *(rooms[].name)*
- **Short summary:** →  *(rooms[].summary)*
- **Long description:** →  *(rooms[].description)*
- **m² / capacity / bed / views:** →
- **Room amenities:** →  *(rooms[].amenities[])*
- **Price from:** →  *(rooms[].priceFrom)*
- **Photos:** →  *(rooms[].image, rooms[].gallery[])*

### 4.4 Services / facilities (amenities)
- **List of services** (wifi, spa, pool, parking, breakfast, gym…) →
- Per featured service: **title + description + photo** →  *(amenities[].title / .description / .image)*

### 4.5 Restaurant / dining
- **Restaurant name / concept:** →  *(dining.title)*
- **Description:** →  *(dining.description)*
- **Hours:** →  *(dining.hours)*
- **Sample menu (dishes):** →  *(dining.menu[])*
- **Photos:** →  *(dining.image)*
- *(Multiple venues: list name + description + photo → venues[])*

### 4.6 Experiences / things to do  *(mostly resort)*
- List of experiences (pool, beach, spa, excursions, kids club…) → *(experiences[].image + name)*

### 4.7 Offers / packages
Per offer:
- **Title / package name:** →  *(offers[].title)*
- **Description:** →  *(offers[].description)*
- **What's included:** →  *(offers[].includes[])*
- **Price / % discount:** →  *(offers[].priceFrom)*
- **Photo:** →  *(offers[].image)*

### 4.8 Gallery
- **Hotel photos** (the more the better, categorised if you can) →  *(gallery[])*

### 4.9 Reviews / testimonials
Per review:
- **Guest quote:** →  *(testimonials[].quote)*
- **Name / origin:** →  *(testimonials[].author)*
- **External scores** (Booking, Google, TripAdvisor) →

### 4.10 Location / how to get there
- **"How to get there" text:** →  *(location.directions)*
- **Key distances** (airport, station, beach, centre…) →
- **Map / coordinates:** →  *(location.map)*

### 4.11 Blog / articles  *(optional)*
Per article:
- **Title:** →  *(posts[].title)*
- **Category:** →  *(posts[].category)*
- **Excerpt:** →  *(posts[].excerpt)*
- **Body:** →  *(post.body)*
- **Cover:** →  *(posts[].cover)*

---

## 5. Assets
- **Folder / link to the photos:** →
- **Any brand material** (manual, palette, licensed fonts): →

---

## 6. SEO (optional)
- **Meta title / description per page:** →
- **Keywords:** →

---

### Notes for the factory when reading this briefing
1. Score the 4 styles with the `decisionRubric` in `template-spec.json` using **section 1**. On a tie or missing key info, **ask** before deciding.
2. Take `defaults[template]` and override with the tokens in **section 2** only when given.
3. Fill each page's bindings from **sections 3–4**, per language. A missing fact is **omitted and recorded as a gap** — never invented. Only a missing **image** may fall back to an on-brand tonal placeholder (Muse); text/data slots stay empty and may block launch QA.
4. Enable only the pages with enough content (e.g. no articles → no blog).
