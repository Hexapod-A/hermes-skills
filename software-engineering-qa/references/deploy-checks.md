# Deploy checks (Vercel and similar)

## Before pushing

- `npm ci && npm run build` passes locally with production env vars (copy names from `.env.example`).
- `npm run lint` and `tsc --noEmit` clean (Next.js build fails on type errors by default).
- Framework on a current patch release; check `npm audit --omit=dev`. Hosts can block deploys of versions with known critical advisories.
- Node version pinned (`"engines": {"node": "20.x"}` or `.nvmrc`) and matching the host setting.
- Lockfile committed; only one lockfile type in the repo.
- Fonts self-hosted or loaded at runtime; build steps that fetch from the internet can fail on the build machine.
- Large files out of git (videos, datasets): use storage/CDN.

## Env vars

- Every var in `.env.example` is set in the host for Production (and Preview if previews must work).
- Only browser-safe values use the `NEXT_PUBLIC_` prefix; service keys stay server-only.
- After changing env vars, **redeploy**: running deployments keep the old values.
- Values with newlines (private keys) pasted exactly; URLs without trailing spaces.

## After deploy

- Deployment state READY; open the build log for warnings.
- Run `ui_check.mjs https://your-app.vercel.app/ ... --links` at all widths.
- Check API routes return 200 with real data (`curl -i`), auth redirects work, webhooks reach the deployed URL.
- Images load from the production domain (`next.config` `images.remotePatterns`).
- Custom domain: DNS points to the host, HTTPS certificate issued, `www` redirect set.

## Common failures

| Symptom | Usual cause | Fix |
|---|---|---|
| `Module not found` on the host only | file name case (`Header.tsx` vs `header`) | rename with `git mv`, match imports |
| Build OK, page 500 | missing env var at runtime | set it, redeploy, read function logs |
| `Dynamic server usage` error | server-only API in a static page | `export const dynamic = 'force-dynamic'` or move the call |
| Hydration mismatch | dates/random/`window` used during render | compute in `useEffect`, or render the same on server and client |
| Images broken in prod | remote host not allowed / wrong path case | add `remotePatterns`, fix paths |
| Deploy blocked or not triggered | commit author not allowed on the team, wrong branch, ignored build step | commit as an allowed author, check the production branch and "Ignored Build Step" |
| Cron not running | plan limits (daily only on free plans), wrong path | check plan, `vercel.json` crons, route responds to GET |
| Function timeout | slow external API | cache, move to background job, raise `maxDuration` within plan |
