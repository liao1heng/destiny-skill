# Adapter Rules

Use this file during `Pick adapter` and `Pick library only if needed`.

## Framework rule

- Stay framework-agnostic by default
- Do not assume React, Vue, Nuxt, Next, or a component library
- Only adapt the style layer unless project context explicitly requires framework code

## Choose adapter

### `CSS`

Pick `CSS` when:

- the project has plain CSS, CSS modules, Sass, or bespoke styling
- the project has no utility framework
- you need the most portable output

### `Tailwind CSS`

Pick `Tailwind CSS` when:

- the project already uses Tailwind CSS
- the user explicitly wants Tailwind CSS
- the team prefers utility-first styling

Rules:

- Never introduce Tailwind CSS into a non-Tailwind project just for aesthetics
- `design-tokens.css` remains the canonical token source even when Tailwind CSS is present
- `tailwind.design.preset.js` should map to CSS variables, not replace them

## Snapshot materialization

Stable project files:

- `design-theme.json`
- `DESIGN_GUIDE.md`
- `design-tokens.css`
- `motion-tokens.css`
- `tailwind.design.preset.js` when Tailwind CSS is in use

Apply order:

1. Read existing snapshot files if present
2. Update snapshot files first
3. Apply page changes second

## Library selection

### `CSS`

Use for:

- hover and focus states
- simple enter or exit fades
- local reveals
- lightweight state transitions

### `Motion`

Default JS animation library.

Use for:

- layout transitions
- staggered reveals
- gesture-driven interactions
- section reveals
- scroll-triggered transitions

Why:

- works across JavaScript, React, and Vue
- covers most modern product and marketing needs

### `GSAP`

Escalate only when needed.

Use for:

- multi-step timelines
- complex hero choreography
- dense scroll-driven narratives
- advanced Flip or ScrollTrigger work

### `Lenis`

Do not enable by default.

Use only when all are true:

- the surface is brand-led or narrative-heavy
- the user explicitly wants smooth or immersive scrolling
- the page benefits from parallax, scroll sync, or cinematic pacing
- the project can absorb nested-scroll, Safari, and mobile tradeoffs

## Dependency rule

- Reuse an existing suitable animation library before adding another
- Do not add parallel animation stacks without a clear split in responsibility
- If the project only needs local transitions, stay with `CSS`
