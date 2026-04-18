# Motion Policy

Use this file during `Set motion policy`.

## Purpose gate

Motion is allowed only when it does at least one of these jobs:

- explain state change
- preserve context
- reinforce hierarchy
- provide interaction feedback
- improve perceived performance
- establish brand rhythm

If motion is only decorative, default down.

## Motion levels

Pick one level for the project or surface.

### `none`

- Static UI except for essential state visibility
- Use for sensitive, dense, or low-tolerance workflows

### `subtle`

- Small transitions and restrained reveals
- Default for most product work

### `standard`

- Clear section reveals, list transitions, light choreography
- Good default for polished marketing and product surfaces

### `expressive`

- Used sparingly for launch pages or story-driven surfaces
- Requires stronger verification for performance and clarity

## Allowed patterns

Default allowed:

- one hero reveal sequence
- section enter transitions
- modal, drawer, and overlay transitions
- tab, accordion, and filter context transitions
- list and grid add/remove/reorder motion
- light button and card feedback
- loading skeletons or shimmer
- anchor-target arrival feedback

## Disallowed patterns

Default blocked:

- heavy motion on primary nav items
- complex motion during typing or form entry
- decorative motion in dense tables
- every card animating independently
- long exit animations
- motion as the only signal for meaning
- cinematic scroll behavior in routine product screens

## Timing tokens

Write resolved timing values to `motion-tokens.css`.

Default ranges:

- `micro`: `150ms` to `220ms`
- `standard`: `220ms` to `320ms`
- `section`: `320ms` to `480ms`
- `stagger`: `40ms` to `60ms`

## Behavior rules

- Enter should usually be slower than exit
- High-frequency interactions should prefer short feedback
- Scroll motion is for long-form, brand, or narrative pages only
- Keep movement readable, not theatrical
- Prefer transform and opacity before layout-heavy effects

## Reduced motion

Always provide a reduced-motion fallback.

Minimum fallback behavior:

- disable non-essential reveal sequences
- shorten or remove stagger
- remove smooth-scroll overrides
- keep state changes visible without animation

## Verification

Check:

- does the motion explain something useful?
- does it make repeated tasks slower?
- does it hold up on mobile?
- does it still work when reduced motion is enabled?
- is the chosen library justified?
