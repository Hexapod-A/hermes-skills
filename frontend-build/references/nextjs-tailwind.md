# Next.js + Tailwind patterns

## Structure (App Router)

    src/
      app/
        layout.tsx          # html/body, fonts, header/footer, metadata defaults
        page.tsx            # home
        (marketing)/pricing/page.tsx
        dashboard/layout.tsx  # its own shell, auth check on the server
        api/contact/route.ts  # server-only API
        globals.css         # Tailwind layers + CSS variables (tokens)
      components/
        ui/                 # Button, Input, Card, Badge, Dialog - small, styled with tokens
        sections/           # Hero, Features, Pricing, Footer - page building blocks
      lib/                  # data fetching, utils, validation schemas
      content/              # copy and data as TS/JSON/MDX, not hard-coded in JSX

Server components by default. Add `"use client"` only to the small parts that need state, effects or browser APIs (a menu toggle, a form), not to whole pages.

## Tokens in Tailwind

Tailwind v4 (CSS-first):

    /* globals.css */
    @import "tailwindcss";
    @theme {
      --color-brand: #ff7a00;
      --color-ink: #141414;
      --color-muted: #5c5c5c;
      --font-sans: "Inter", system-ui, sans-serif;
      --radius-card: 20px;
    }
    /* usage: bg-brand text-ink rounded-card font-sans */

Tailwind v3: put the same values in `tailwind.config.ts` under `theme.extend` (colors, fontFamily, borderRadius, boxShadow). `ui-replicate/templates/tailwind.tokens.ts` is a starter.

Fluid type in Tailwind: `text-[clamp(2.25rem,1.6rem+2.8vw,4.25rem)]` or add the `--text-*` sizes from `base.css` to the theme.

## Images

    import Image from "next/image";
    <Image src="/hero.webp" alt="Team reviewing a dashboard" width={1600} height={1200}
           sizes="(min-width: 1024px) 50vw, 100vw" priority className="rounded-3xl object-cover" />

- `sizes` must match the layout, or phones download the desktop file.
- `priority` only on the LCP image. Remote images need `images.remotePatterns` in `next.config`.
- Background-style images: `fill` + a parent with `relative` and an aspect ratio.

## Fonts

    import localFont from "next/font/local";
    const inter = localFont({ src: [{ path: "../fonts/Inter-Var.woff2", weight: "100 900" }], display: "swap", variable: "--font-sans" });
    // <html className={inter.variable}>

`next/font/google` downloads at build time; if builds run without internet or fail on it, self-host with `next/font/local`.

## Metadata

    export const metadata = { title: { default: "Brand", template: "%s | Brand" }, description: "...",
      openGraph: { images: ["/og.png"] }, metadataBase: new URL("https://example.com") };

## Forms

Server action or `app/api/*/route.ts`; validate with zod on the server; return field errors; show success in an `aria-live` region; disable the button while sending.

## Performance habits

- Keep client components small; pass data from server components as props.
- `next/dynamic` for heavy below-the-fold widgets (maps, charts, video players).
- Load third-party scripts with `next/script` `strategy="afterInteractive"` or `"lazyOnload"`.
- Check `next build` output: first-load JS per route; investigate anything over ~200 KB.
