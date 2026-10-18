# Font matching

Get the font right before anything else: a wrong font changes every width, wrap and line height, and the diff never settles.

## 1. Find the real name

1. Live site: `extract_styles.mjs` lists the fonts used by visible text (by character count) and the `@font-face` sources. That is the answer.
2. Dribbble/Behance: read the shot description and tags (`fetch_ref.py` reads the page through r.jina.ai; the text is in the same response). Designers often name the font.
3. Image only: crop a line of large text (`grid_overlay.py --crop ... --zoom 2`) and compare letter shapes. Check these letters first: `a g y R G Q 1 4 7`, the dot on `i`, the tail of `t`, and how round `o` is.
4. Still unknown: pick the closest free font from the table below and write the reason in the spec.

## 2. Closest free fonts (starting points; confirm with an overlay)

| Seen in designs | Licence | Try first | Then |
|---|---|---|---|
| SF Pro (Apple UI) | Apple only | Inter | Figtree |
| Helvetica Neue / Arial | paid / system | Inter | Arimo (Arial metrics) |
| Circular | paid | DM Sans | Figtree |
| Gilroy, Euclid Circular, Product Sans style geometrics | paid | Outfit | Plus Jakarta Sans |
| Proxima Nova | paid | Figtree | Montserrat (wider) |
| Gotham | paid | Montserrat | Figtree |
| Avenir / Avenir Next | paid | Nunito Sans | Figtree |
| Futura | paid | Jost | Outfit |
| Graphik, Neue Haas Grotesk | paid | Inter | Hanken Grotesk |
| Aeonik, Neue Montreal | paid | Manrope | Inter Tight |
| TT Commons, TT Norms | paid | Plus Jakarta Sans | DM Sans |
| Satoshi, General Sans, Clash Display, Cabinet Grotesk | free (Fontshare ITF FFL) | use the real font | |
| Urbanist, Outfit, Manrope, Plus Jakarta Sans, DM Sans, Inter, Poppins | free (Google, OFL) | use the real font | |

## 3. Confirm

Render one heading and one paragraph from the reference in the candidate font at the measured size, screenshot it, and put it next to the crop with `side_by_side.py`. Check width of the same word (within 2%), x-height, and the shape of `a`, `g`, `y`. Then tune `letter-spacing` (headings in many dashboards use −0.01 to −0.02em) and line height.

## 4. Ship

- Self-host the font: `google_font.py "<Family>" --out public/fonts --css src/app/fonts.css`. Do not fetch fonts at build time.
- A paid font from a live site is for identification only. Use it only if the user owns a licence and gives you the files.
