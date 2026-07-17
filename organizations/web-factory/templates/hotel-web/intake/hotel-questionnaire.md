# Hotel intake questionnaire

Scout fills this in for every new project. The output lives at
`projects/<slug>/intake.md` (free-form), and the structured facts land
in `src/content/hotel/info.json` once the project is cloned from this
template.

## 1. Identity

- **Name** (legal + commercial, if different):
- **Slug** (lowercase-kebab-case, used in URLs and folder):
- **Segment**: boutique · budget · business · resort · (other, requires `template` wg)
- **Star rating** (1–5, optional):
- **Capacity**: total rooms · total beds
- **Years operating**:
- **Ownership**: independent · chain (which) · franchise

## 2. Location

- **Street address**:
- **City / region / postal code / country**:
- **Geo coordinates** (lat, lng — for map and Schema.org):
- **Distance from key transit** (airport, train, port):
- **Neighbourhood character** (3 lines max):

## 3. Audience

- **Primary guest profile** (1–2 sentences — age, origin, purpose):
- **Languages they speak** (rank by volume):
- **Stay length** (avg nights):
- **Booking lead time** (days):

## 4. Brand assets

- **Logo files** (path or URL):
- **Existing photography** (path + count + style notes):
- **Brand book** (yes / no — path if yes):
- **Existing website** (URL — for what NOT to repeat):

## 5. Competitive landscape

Three to five comparable hotels in the same city/segment:
- [ ] Hotel 1 (URL): strengths / weaknesses
- [ ] Hotel 2:
- [ ] Hotel 3:

Differentiator the new site must surface vs. competitors:

## 6. Booking integration

- **Booking engine**: external URL · Booking.com widget · Expedia ·
  SiteMinder · none
- **Engine URL or widget ID**:
- **PMS** (if relevant for future integrations):

## 7. Locales

Required at launch:
- [ ] es (default source unless overridden)
- [ ] en
- [ ] fr · de · it · pt · ja · zh · …

Rationale per locale (market signal):

## 8. Constraints

- **Deadline**:
- **Budget** (USD lifetime, for `proj-<slug>` workgroup ledger):
- **Hard no's** (e.g. "no booking pop-up", "no chatbot"):
- **Compliance** (GDPR, cookie banner specifics, accessibility level):

## 9. Brand starter recommendation

Scout's pick from {boutique, budget, business, resort}:

Rationale (2–3 sentences referencing intake signals):

## 10. Handoff

- [ ] intake.md committed at `projects/<slug>/intake.md`
- [ ] `src/content/hotel/info.json` populated from §1–6
- [ ] `proj-<slug>` workgroup created by mira (via `new-project.py`)
- [ ] First `#task design` posted in `proj-<slug>` by mira
