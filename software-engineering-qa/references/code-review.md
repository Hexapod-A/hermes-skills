# Code review and reading a repo fast

## Read an unfamiliar repo in 15 minutes

1. `README.md`, then the scripts in `package.json` / `pyproject.toml` / `Makefile`: they tell you how it is run, tested and built.
2. Tree: `git ls-files | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -40` shows where the code lives.
3. Entry points: Next.js `app/` (routes = folders, `page.tsx`, `route.ts` for APIs, `layout.tsx`), `pages/`, Express `app.listen`, Python `main.py` / `manage.py` / `__main__`.
4. Data: schema files (`prisma/schema.prisma`, `supabase/migrations`, `models.py`), API clients, env vars (`.env.example`, `grep -rn "process.env\." --include=*.ts`).
5. History: `git log --oneline -20`, `git log -p --follow path/file` for the file you will touch; `git blame` explains odd code.
6. Search instead of reading everything: `rg -n "functionName|route-name|error text"`.
7. Write down: purpose, stack, run/test commands, where your change goes, what could break.

## Review checklist

Correctness
- Does it do what the task asked, including edge cases (empty, null, very long, many items, slow network, double click)?
- Errors handled and shown to the user in plain words; no swallowed exceptions.
- Money in integer minor units (kobo/cents), dates with time zones, IDs not guessable.

Security
- No secrets in code, logs, or client bundles (`NEXT_PUBLIC_*` is public!).
- Server checks auth and roles on every protected route and API, not just the UI.
- Inputs validated on the server (zod/pydantic); SQL via parameters/ORM; no `dangerouslySetInnerHTML` with user data.
- Webhooks verify signatures; uploads check type and size; CORS not `*` with credentials.
- Dependencies from the registry, pinned by a lockfile, no unknown postinstall scripts.

Malware red flags (in someone else's repo)
- `postinstall`/`preinstall` that downloads or runs code; `.vscode/tasks.json` with `runOn: folderOpen`.
- Long base64/hex strings, `eval(atob(...))`, `new Function(...)`, `_0x` variable names in source files.
- Requests to Discord/Telegram webhooks, paste sites, raw IP addresses.
- Code reading `~/.ssh`, browser profiles, crypto wallet extension folders, environment variables in bulk.
- Script code inside `.woff`/`.png` files; "test" or "config" files that are minified.
- Fake job/interview "take-home" repos asking you to run them: scan first, run in a throwaway VM.

Quality
- Follows existing patterns and naming; no dead code or commented-out blocks; no copy-pasted logic that should be shared.
- Types precise (no `any` without reason); functions small; names say what things are.
- Tests for new logic and for the bug that was fixed.

Front end
- Works at 320-1440 px; no sideways scroll; images sized; no layout shift; keyboard and screen-reader basics.
- Loading, empty and error states exist.

## Minimal-diff rules

- Change only what the task needs. Separate refactors into their own commit.
- Match the file's style (quotes, semicolons, formatting tool). Run the project's formatter, not yours.
- Prefer editing an existing function over adding a parallel one.
- Every new dependency needs a reason (size, maintenance, licence).
- Commit message: what and why in one line (`fix(cart): keep quantity when page reloads`).
