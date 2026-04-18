---
name: cli-des
description: Create and apply reusable web design systems across projects. Use when the user wants pages or products to feel more polished, more consistent, more premium, more "tech", or governed by explicit style and motion rules. Audit existing tokens and animation patterns, materialize project snapshots into fixed files, and adapt output to CSS or Tailwind CSS without binding to a frontend framework.
metadata:
  short-description: Reusable web design workflow
---

# CLI DES

Turn one-off "make it look better" requests into a reusable project design system.

## Core rules

- Be framework-agnostic. Never assume React, Vue, Nuxt, Next, or a component library.
- Only adapt the style layer. Supported adapters: `CSS` and `Tailwind CSS`.
- Systematize first, page edits second.
- Reuse an existing design system if present. Extend it; do not replace it blindly.
- Keep context lean. Read only the reference file needed for the current step.

## Fast path

If the project already has `design-theme.json` and `DESIGN_GUIDE.md`, read them first and use them as the source of truth before changing any page.

## Workflow

1. `Audit project`
   Inspect style entrypoints, tokens, fonts, radii, shadows, component primitives, animation libraries, page types, content language, and density.
   If an existing design system exists, inherit and extend it.

2. `Classify surface`
   Read `references/page-patterns.md`.
   Pick one surface: `marketing`, `docs`, `product`, `dashboard`, or `settings`.

3. `Choose style direction`
   Read `references/style-framework.md`.
   Pick exactly one primary direction. Do not blend multiple primaries.
   Resolve token roles, type hierarchy, surface language, spacing rhythm, and page cadence.

4. `Set motion policy`
   Read `references/motion-policy.md`.
   Pick one level: `none`, `subtle`, `standard`, or `expressive`.
   Only add motion when it explains change, preserves context, reinforces hierarchy, gives feedback, improves perceived performance, or establishes brand rhythm.

5. `Pick adapter`
   Read `references/adapter-rules.md`.
   Pick `CSS` or `Tailwind CSS`.
   Keep framework-specific implementation out of the design system unless the project context explicitly requires it.

6. `Pick library only if needed`
   Default order:
   - `CSS` for simple transitions and local reveals
   - `Motion` for layout, stagger, gestures, section reveals, and scroll-triggered work
   - `GSAP` for timelines, complex hero choreography, and heavy scroll narratives
   - `Lenis` only on explicit smooth-scroll or immersive-scroll requirements, and only when the project can absorb its tradeoffs
   If the project already has a suitable animation library, reuse it instead of adding another.

7. `Materialize snapshot`
   Create or update:
   - `design-theme.json`
   - `DESIGN_GUIDE.md`
   - `design-tokens.css`
   - `motion-tokens.css`
   - `tailwind.design.preset.js` only if the project uses Tailwind CSS
   Use the files in `templates/` as starting points.

8. `Apply page changes`
   Any page rewrite must read the snapshot files first.
   Page work should inherit the project system, not reinvent it.

9. `Verify`
   Check consistency, contrast, interaction clarity, reduced-motion behavior, mobile behavior, and dependency fit.

## Output contract

Every run should leave behind:

- one chosen surface
- one chosen style direction
- one motion level
- one adapter
- fixed snapshot files with stable names

When the user only asks for ideas, still respond in this structure:

- surface
- direction
- motion level
- adapter
- snapshot files to create or update

## Anti-patterns

- default purple/blue gradient answers
- global glassmorphism as the only visual idea
- glow everywhere
- one different style per section
- heavy animation on high-frequency interactions
- animation as the only way to communicate state
- binding the system to a framework without evidence
- adding multiple animation libraries in parallel without a clear reason

## References

- `references/style-framework.md` for directions, token roles, hierarchy, surfaces, cadence, and anti-patterns
- `references/motion-policy.md` for motion levels, allowed use, timing, behavior rules, and reduced-motion policy
- `references/page-patterns.md` for surface classification
- `references/adapter-rules.md` for CSS vs Tailwind CSS and library selection
- `templates/` for fixed snapshot file starters

This is a workflow skill. It should make future design work cheaper, not just make one page prettier.
