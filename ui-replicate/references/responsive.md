# Desktop design to a 390px phone

Most Dribbble dashboards are desktop-only. The phone version should look like the same product, not like a different template.

## Keep

- The tokens: same colours, font, radii, shadows, icon set. Only the type scale steps down (page title about 0.75x, body never below 15px).
- The signature details (a notched top bar, tilted card, flow path, emoji badges, dock). Shrink them; do not drop them.
- Card shapes and inner padding ratios. A 24px card radius stays 20 to 24px.

## Change

1. **Grid:** columns stack in reading order: summary stats, the main task of the screen, then side panels. Write the order in the spec before coding.
2. **Stat rows:** 3 or 4 stat cards become a 2-column grid, or one horizontal scroll row with snap points. Never squeeze 4 into 390px.
3. **Wide charts and timelines:** horizontal scroll inside the card (`overflow-x: auto`, scroll snap), with the first item fully visible.
4. **Sidebars and top bars:** move navigation to a bottom dock or a menu sheet. Keep the brand mark and one primary action in the top bar.
5. **Tables:** turn rows into cards with the 2 or 3 fields that matter; put the rest behind a tap.
6. **Touch:** targets at least 44px tall; hover-only details get a tap state.
7. **Page padding:** 16px sides, 12 to 16px gaps.

## Check

- `screenshot.mjs URL --widths 390 --out DIR`: the printed `horizontal_overflow` must be `false`.
- Look at the 390px PNG next to the desktop reference (`side_by_side.py` scales both to one width). Ask: same colours, same card shapes, same details? Then it reads as the same product.
- There is no phone reference to score against, so do not report a phone diff score. Report the overflow check and show the screenshot.
- Also check 768px (tablet) once; layouts often break between the two breakpoints.
