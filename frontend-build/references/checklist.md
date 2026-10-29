# Front-end finish checklist

Go through this before calling a page done.

## Layout
- [ ] No sideways scroll at 320, 375, 414, 768, 1440 (`ui_check.mjs`).
- [ ] Content width capped (about 1100-1280 px); text lines 45-75 characters.
- [ ] Consistent section spacing (one `--section-y`), consistent gutters.
- [ ] Grids collapse cleanly: 1 column on phones, 2 on tablets, 3-4 on desktop.
- [ ] Sticky header does not cover anchor targets (`scroll-margin-top`).
- [ ] Nothing important hidden on mobile without another way to reach it.

## Type
- [ ] 2 font families max, 2-4 weights, self-hosted woff2.
- [ ] Body 16-18 px on phones, line height 1.5-1.7; headings tighter (1.05-1.25).
- [ ] Headings balanced (`text-wrap: balance`), no single-word last lines in big titles.
- [ ] One `h1` per page, headings in order.

## Colour
- [ ] Text contrast 4.5:1 (3:1 for large text), checked on every background including images.
- [ ] One accent colour used for actions; not for decoration everywhere.
- [ ] Hover/active/focus states visible.

## Spacing and shape
- [ ] All spacing from the scale; equal padding inside similar cards.
- [ ] Same radius family everywhere; shadows subtle and consistent.
- [ ] Optical alignment: icons centred with text, buttons the same height in a row.

## Images and media
- [ ] Every image has `width`/`height` or `aspect-ratio`, `alt` text (empty `alt=""` for decoration).
- [ ] Served near the size shown (no 3000 px image in a 400 px box); WebP/AVIF.
- [ ] Hero image eager + high priority; everything below the fold lazy.
- [ ] Real photos, consistent crop and colour; no stretched or blurry images at 2x/3x.

## Components and states
- [ ] Buttons: hover, focus-visible, active, disabled, loading.
- [ ] Forms: labels (not placeholder-only), input types (`email`, `tel`), `autocomplete`, inline errors, success message, double-submit prevented.
- [ ] Empty, loading and error states for every data view.
- [ ] Mobile menu opens/closes with keyboard and screen reader; focus is trapped while open.
- [ ] Tap targets 44 x 44 px.

## Accessibility basics
- [ ] `lang` on `<html>`, page `<title>`, landmarks (`header`, `nav`, `main`, `footer`).
- [ ] Everything works with the keyboard; focus order makes sense; visible focus ring.
- [ ] Icons-only buttons have `aria-label`.
- [ ] Motion respects `prefers-reduced-motion`.

## SEO and sharing
- [ ] Unique title and description per page; canonical URL.
- [ ] Open Graph image (1200x630), title, description; favicon and apple-touch-icon.
- [ ] `robots.txt` and `sitemap.xml` for sites.

## Performance
- [ ] `web_vitals.mjs` phone profile: LCP < 2.5 s, CLS < 0.1, TBT < 300 ms.
- [ ] First-load JS < 350 KB compressed; no unused libraries.
- [ ] Fonts preloaded only if used above the fold; `font-display: swap`.
- [ ] Third-party scripts (chat, analytics) loaded after the page (`defer`, `afterInteractive`).
