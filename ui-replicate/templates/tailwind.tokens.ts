// Tailwind (v3) theme for a replicated UI. Paste into tailwind.config.ts `theme.extend`.
// Every value comes from the spec. Components use these names only, never raw hex.
import type { Config } from "tailwindcss";

export const tokens: NonNullable<Config["theme"]>["extend"] = {
  colors: {
    bg: "#F8F8F7",
    surface: "#FFFFFF",
    ink: "#000000",
    muted: "#5C5C5C",
    line: "#E3E6E4",
    lilac: { DEFAULT: "#F4D6FF", soft: "#FAE5FF" },
    mint: { DEFAULT: "#DBFADD", deep: "#CDF9D1" },
    aqua: { DEFAULT: "#EDFAFC" },
  },
  fontFamily: {
    // self-hosted with scripts/google_font.py; never next/font/google on Vercel builds
    sans: ["Outfit", "system-ui", "sans-serif"],
  },
  fontSize: {
    xs: ["13px", { lineHeight: "16px" }],
    sm: ["15px", { lineHeight: "22px" }],
    base: ["16px", { lineHeight: "24px" }],
    lg: ["20px", { lineHeight: "26px" }],
    xl: ["30px", { lineHeight: "36px", letterSpacing: "-0.01em" }],
    "2xl": ["40px", { lineHeight: "48px", letterSpacing: "-0.02em" }],
  },
  borderRadius: {
    card: "24px",
    pill: "9999px",
    button: "9999px",
  },
  spacing: {
    page: "24px",
  },
};
