# Reference spec: <screen name>

Fill this in before writing code. Numbers come from the tools, not from guessing.

## Source

- Reference: <URL or file>, downloaded <date>, original size <w x h>
- Prepared reference: `refs/<name>_1440.png`, crop <x0,y0,x1,y1 in raw px>, scale <factor>
- **Viewport to render at:** <width> x <height> (from `prep_ref.py`)
- Mode: restyle (our content) | clone (same content)

## Layout grid (px, in the prepared reference)

| Area | x | y | w | h | Notes |
|---|---|---|---|---|---|
| page padding | | | | | outer margin, frame radius |
| top bar | | | | | |
| sidebar / left column | | | | | |
| main column | | | | | |
| right column | | | | | |
| gaps | | | | | column gap, card gap |

Columns: <n> columns, <gap>px gaps. Base unit: 4 / 8 px.

## Palette (`palette.py`, `--at` on each element)

| Token | Hex | Where |
|---|---|---|
| bg | | page background |
| surface | | cards |
| ink | | primary text |
| muted | | secondary text |
| accent-1 | | |
| accent-2 | | |
| line | | borders, dividers |

## Type scale

Font: <family> (identified how: page CSS / visual match / closest free font because ...)

| Role | Size | Weight | Line height | Letter spacing | Case |
|---|---|---|---|---|---|
| page title | | | | | |
| card title | | | | | |
| big number | | | | | |
| body | | | | | |
| label / pill | | | | | |

## Shape tokens

- Radius: card <px>, pill <px or full>, button <px>, avatar <full / px>. Buttons all share one radius.
- Shadow: <none / css value>
- Borders: <width colour>
- Icons: <set and stroke weight, e.g. Iconsax linear 1.5px>

## Components (every item on screen)

1. <name>: size <w x h>, bg <token>, radius <token>, content <...>, states <hover / active>
2. ...

## Signature details (what makes it look like this design)

- <e.g. notch in the top bar, tilted card, dashed flow path, emoji badges, dock at the bottom>

## Content swap (restyle only)

| Reference content | Ours |
|---|---|
| | |

## Mobile (390px) plan

- <columns become ..., top bar becomes ..., dock becomes ...>
