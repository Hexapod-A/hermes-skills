# Brand kit format

One folder per brand under `flyer-studio/brands/<brand>/` (or under `$FLYER_BRANDS_DIR/<brand>/`):

```
brands/<brand>/
├── brand.json          # required
├── logo.svg            # preferred: vector logo for dark backgrounds
├── logo-interim.png    # optional raster fallback
└── fonts/              # .ttf/.otf/.woff2 files + their licence files
```

## brand.json

```json
{
  "name": "3xAgentic",
  "website": "3xagentic.xyz",
  "colors": { "bg": "#000000", "fg": "#F1F1F1", "accent": "#FF9900", "muted": "#A6A6A6", "on_accent": "#000000" },
  "fonts": {
    "heading": { "family": "DM Sans", "file": "fonts/DMSans-Variable.ttf", "weight_range": "100 1000", "weight": 400, "fallback": "Helvetica, Arial, sans-serif" },
    "body":    { "family": "Plus Jakarta Sans", "file": "fonts/PlusJakartaSans-Variable.ttf", "weight_range": "200 800" }
  },
  "logo": { "file": "logo.svg", "fallback": "logo-interim.png", "alt": "3xAgentic" },
  "cta": { "style": "pill", "burst": true },
  "decor": { "style": "pixel-blocks", "stairs": true },
  "voice": { "tone": "…", "do": ["…"], "dont": ["…"] },
  "css": "optional extra CSS applied to every flyer of this brand"
}
```

| Field | Meaning |
|---|---|
| `colors.bg` / `fg` | canvas and main text colour. Keep their contrast ≥ 7:1. |
| `colors.accent` | the one highlight colour: `*word*` highlights, prices, stats, decor blocks. |
| `colors.muted` | secondary text (labels, sources). Must still pass 4.5:1 on `bg`. |
| `colors.on_accent` | text placed on the accent (tags, list numbers). |
| `fonts.*.family` | the CSS family name the file is registered under. |
| `fonts.*.file` | path relative to the brand folder. Variable fonts are fine; set `weight_range`. |
| `fonts.heading.weight` | default headline weight (3xAgentic: 400, matching the samples). |
| `logo.file` | SVG preferred. A file containing `data-placeholder="true"` is treated as a placeholder and `fallback` is used instead (with a warning). |
| `cta.style` | `pill` (white pill + accent starburst) or `url` (plain text). |
| `voice` | read by the agent when writing copy; not used by the renderer. |

## Adding a new brand

1. `cp -r brands/_template brands/<new>` and edit `brand.json`.
2. Get the fonts as files (Google Fonts: download from `https://github.com/google/fonts/tree/main/ofl/<family>`; keep the `OFL.txt`). Never hotlink fonts; renders must work offline.
3. Drop the logo in as `logo.svg` (light version for dark backgrounds). Rasters need ≥ 4× the display size for 4K output (logo shows ~64px tall on a 1080 canvas → ≥ 256px tall).
4. Render `examples/announcement.json` with `"brand": "<new>"` and fix anything the report flags.

## Replacing the 3xAgentic logo

Save John's SVG over `brands/3xagentic/logo.svg` (same filename). Make sure it is the version that reads on black (white/orange). Delete nothing else; the placeholder warning disappears on the next render.
