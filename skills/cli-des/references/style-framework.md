# Style Framework

Use this file during `Audit project` and `Choose style direction`.

## Audit checklist

Inspect and record:

- style entrypoints and theme files
- token files or hard-coded color clusters
- font loading and type pairings
- radius, border, shadow, blur, and spacing patterns
- component primitives and icon systems
- existing animation libraries and motion idioms
- page language, audience, trust level, and information density

Answer these before resolving style:

- Is the current system explicit or implicit?
- Is the product brand-led, utility-led, or content-led?
- Is the interface sparse, balanced, or dense?
- Does the project need trust, excitement, precision, or editorial voice first?

## Choose one style direction

Pick exactly one primary direction.

### `future-brand`

- High-trust, forward-looking, polished, precise
- Layered depth, controlled accents, luminous but restrained surfaces
- Good for AI brands, launch pages, premium product marketing

### `signal-minimal`

- Quiet, sparse, premium, highly legible
- Typography and spacing do most of the work
- Good for settings, pricing, product detail, mature brands

### `editorial-tech`

- Narrative, contrast-heavy, asymmetrical, idea-first
- Strong section rhythm, larger headlines, deliberate art direction
- Good for docs landing pages, narratives, product storytelling

### `industrial-data`

- Utilitarian, modular, crisp, evidence-heavy
- Hard edges, mono accents, denser signals, lower decoration
- Good for dashboards, admin surfaces, ops products

## Resolve token roles

Write resolved roles to `design-theme.json` and `design-tokens.css`.

Stable role names:

- `bg.canvas`
- `bg.elevated`
- `surface.primary`
- `surface.secondary`
- `text.default`
- `text.muted`
- `text.inverse`
- `accent.primary`
- `accent.secondary`
- `border.soft`
- `border.strong`
- `shadow.soft`
- `shadow.focus`

Rules:

- Keep role names stable across projects
- Choose values from project context, not from fixed brand defaults
- Prefer semantic meaning over "pretty color matching"
- Keep one primary accent and at most one supporting accent

## Type hierarchy

Resolve these roles for every project:

- `display`: hero or keynote statements
- `title`: page and section titles
- `section`: module headers and card titles
- `body`: default reading text
- `meta`: labels, helpers, captions
- `mono`: code, metrics, dense utility text

Rules:

- `display` and `body` should not fight each other
- `meta` must stay readable at small sizes
- `mono` is a support voice, not the whole system

## Surface language

Choose one primary surface language and at most one secondary.

Available languages:

- `clean`
- `frosted`
- `hard-edge`
- `gloss`
- `industrial`
- `paper`

Rules:

- Primary language defines most surfaces
- Secondary language is for emphasis only
- Do not mix more than two surface languages
- Do not let special surfaces dominate all modules

## Spacing rhythm

Pick one rhythm:

- `compact`
- `neutral`
- `airy`

Rules:

- Keep it consistent across cards, sections, and layout gutters
- Dense UI can still have strong hierarchy; do not fix density with random spacing

## Page cadence

Resolve the order and intensity of these blocks:

- `hero`
- `proof`
- `features`
- `detail`
- `cta`

Rules:

- `hero` states the promise
- `proof` earns trust early
- `features` explain capability
- `detail` handles depth and objections
- `cta` closes with one clear next move

## Anti-patterns

- default purple/blue gradient answers
- global glassmorphism
- glow as the only depth cue
- random section-by-section style changes
- more than one primary accent
- decorative typography that reduces readability
- swapping direction mid-page without a strong reason
