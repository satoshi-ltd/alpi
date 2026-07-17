import { defineCollection, z } from "astro:content";

// All content the AI fills lives here, validated at build time (the safety gate).
// `lang` on every entry drives i18n. Repeating things = collections; per-locale
// page copy = the `pages` collection keyed by `{page}.{locale}`.

const localized = { lang: z.string() };

const rooms = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    name: z.string(),
    slug: z.string(),
    order: z.number().default(0),
    summary: z.string(),
    description: z.string().optional(),
    sizeM2: z.number().optional(),
    capacity: z.number().optional(),
    bed: z.string().optional(),
    view: z.string().optional(),
    amenities: z.array(z.string()).default([]),
    priceFrom: z.number().optional(),
    currency: z.string().default("EUR"),
    image: z.string().optional(),
    gallery: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
  }),
});

const amenities = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    title: z.string(),
    description: z.string().optional(),
    category: z.string().optional(),
    image: z.string().optional(),
    order: z.number().default(0),
  }),
});

const meetings = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    name: z.string(),
    capacity: z.number(),
    av: z.string().optional(),
    sizeM2: z.number().optional(),
    order: z.number().default(0),
  }),
});

const dining = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    name: z.string(),
    summary: z.string().optional(),
    description: z.string().optional(),
    hours: z.string().optional(),
    menu: z.array(z.string()).default([]),
    image: z.string().optional(),
    order: z.number().default(0),
  }),
});

const offers = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    title: z.string(),
    description: z.string().optional(),
    includes: z.array(z.string()).default([]),
    priceFrom: z.number().optional(),
    discountPct: z.number().optional(),
    code: z.string().optional(),
    currency: z.string().default("EUR"),
    image: z.string().optional(),
    order: z.number().default(0),
  }),
});

const testimonials = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    quote: z.string(),
    author: z.string(),
    rating: z.number().min(1).max(5).default(5),
    order: z.number().default(0),
  }),
});

const experiences = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    name: z.string(),
    image: z.string().optional(),
    order: z.number().default(0),
  }),
});

const legal = defineCollection({
  type: "content", // URL slug comes from the filename stem: `<slug>.<lang>.md` (localized slugs via localized filenames)
  schema: z.object({
    ...localized,
    title: z.string(),
    order: z.number().default(0),
  }),
});

const posts = defineCollection({
  type: "content", // markdown body
  schema: z.object({
    ...localized,
    title: z.string(),
    category: z.string().optional(),
    excerpt: z.string().optional(),
    cover: z.string().optional(),
    date: z.coerce.date().optional(),
    readingTime: z.string().optional(),
  }),
});

// Per-locale page copy (hero, intro, about, dining lead, location text, gallery).
const pages = defineCollection({
  type: "data",
  schema: z.object({
    ...localized,
    seo: z.object({
      title: z.string().optional(),
      description: z.string().optional(),
      keywords: z.array(z.string()).default([]),
    }).optional(),
    hero: z.object({
      eyebrow: z.string().optional(),
      title: z.string(),
      subtitle: z.string().optional(),
      image: z.string().optional(),
    }).optional(),
    intro: z.object({ title: z.string().optional(), body: z.string().optional() }).optional(),
    about: z.object({
      eyebrow: z.string().optional(), title: z.string().optional(),
      body: z.string().optional(), image: z.string().optional(),
      values: z.array(z.object({ title: z.string(), body: z.string().optional() })).default([]),
    }).optional(),
    dining: z.object({ title: z.string().optional(), description: z.string().optional() }).optional(),
    location: z.object({
      directions: z.string().optional(),
      map: z.string().optional(),
      distances: z.array(z.object({ label: z.string(), value: z.string() })).default([]),
    }).optional(),
    gallery: z.array(z.string()).default([]),
    body: z.string().optional(),
  }),
});

export const collections = {
  rooms, amenities, meetings, dining, offers, testimonials, experiences, posts, pages, legal,
};
