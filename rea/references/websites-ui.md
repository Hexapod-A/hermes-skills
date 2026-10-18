# Websites and UI

For pixel-level design copies use the `ui-replicate` skill (screenshots, palette, diff score). Use
REA when you also need behaviour: what the page does after clicks, typing, errors and resizes.

## Observe

- Render at fixed viewports (at least 1440x900 and 390x844), DPR 1, reduced motion, same fonts.
- Read the live DOM, computed styles (`getComputedStyle`), network calls (DevTools / HAR), local
  storage and cookies your own session sets, and the JS bundle when it is public.
- List interactions: every button, input, state (empty, loading, error, success, disabled), and
  the keyboard path. Note what changes after each one.

## Specify

Per state: visible text, element boxes, key computed styles (colour, radius, font, spacing),
attributes (`disabled`, `aria-*`), and URL. Per interaction: the sequence and the expected change.

## Test

- `target-ui.json` + `ui_probe.mjs`. A case = path + viewport + actions + capture list.
- `selector_map` in the replica's target maps the original's selectors to yours, so the outputs
  compare key by key even when your markup is different.
- Capture `text`, `boxes` (allow 1 px with `tol`), `styles`, `attrs`, `screenshot` and
  `element_shots` (per-part screenshots). Compare images with `images` rules.
- Lesson from the demo: a whole-viewport pixel threshold missed a button radius change at 1440 px
  (only 0.03% of pixels changed). Computed styles and per-part shots caught all 16 cases.
- Use the `factors` matrix: viewports x action sequences, `combine: full` when small.
- The UI demo has 16 deliberate cases and no independent random cases, so its 100% check rate
  is not a population confidence claim. Generate more states (viewports and random action paths)
  with a predeclared distribution, then use a fresh holdout for a stronger claim.

## Pitfalls

- Fonts: a missing font changes every box. Self-host the font in both, or test on one box.
- Animations: use reduced motion and wait for `document.fonts.ready`.
- Live data (dates, counters, ads): freeze with a fixed test account or mask by format.
