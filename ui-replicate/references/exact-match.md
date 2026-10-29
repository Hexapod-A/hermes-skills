# Exact-match checklist

A diff score catches big differences. These are the small ones people still notice. Check each against
the reference (zoomed crops side by side), not from memory.

## Measure, don't eyeball
- [ ] Viewport and zoom the same as the reference (CSS px, DPR); compare at 1440, 768, 390.
- [ ] Every colour read with `palette.py --at` or `extract_styles.mjs`; no "close enough" hex.
- [ ] Every gap and box measured with `grid_overlay.py` (zoom 2-3x for small parts).
- [ ] Live site: `compare_styles.mjs` at ≥ 95% and the "most common fixes" list is empty.

## Type
- [ ] Same font family (or the closest free match, noted), same weights per element.
- [ ] Font size, line height and letter spacing per text style; uppercase/capitalize the same.
- [ ] Same line breaks in headings at each width (adjust max-width, not font size).
- [ ] Font smoothing and rendering: same weight looks bolder on dark backgrounds; check both.

## Boxes
- [ ] Radius per component (pills vs 8px vs 16px), border width and colour (1px vs 0.5px hairline).
- [ ] Shadows: offset, blur, spread, colour and opacity; layered shadows counted.
- [ ] Padding inside buttons, inputs, cards; equal heights in rows.
- [ ] Backgrounds: gradients (angle, stops), noise/grain, blur (`backdrop-filter`), overlays on images.

## Icons and images
- [ ] Same icon set or a very close one; stroke width (1.5 vs 2), size, alignment with text.
- [ ] Images: same crop, focal point, aspect ratio, rounded corners, object-fit.
- [ ] Logos as SVG, sharp at 2x/3x.

## States and motion
- [ ] Hover, focus-visible, active, disabled for every interactive element (record the reference with `screenshot.mjs` after `page.hover()` when it is a live site).
- [ ] Transitions: property, duration, easing (open the reference's CSS: `transition`, `animation`, keyframes).
- [ ] Scroll: sticky headers and where they stick, scroll-triggered animations, parallax, smooth scroll.
- [ ] Menus, accordions, tabs, modals, carousels open and close the same way.

## Page level
- [ ] Same section order and spacing between sections at each width.
- [ ] Same breakpoints (where the layout changes); check just above and below each.
- [ ] Title, favicon, Open Graph image if the user wants the whole site cloned.
- [ ] No horizontal scroll at any width; no console errors (`software-engineering-qa/scripts/ui_check.mjs`).

## Allowed differences (say them in the report)
- Content swapped on purpose, licensed photos instead of the reference's, a free font instead of a paid one, icons from a free set. Never ship the reference's paid assets.
