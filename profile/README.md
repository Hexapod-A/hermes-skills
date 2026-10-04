# Profile for Hermes memory

`USER.md` is in Hermes' built-in memory format (entries separated by `§`, limit 1,375 characters; this one is ~480).

Install (default profile):

```bash
mkdir -p ~/.hermes/memories
# if you have no USER.md yet:
cp profile/USER.md ~/.hermes/memories/USER.md
# if you already have one, append instead (keep the § separator between entries):
printf '\n§\n' >> ~/.hermes/memories/USER.md && cat profile/USER.md >> ~/.hermes/memories/USER.md
```

Named profile: use `~/.hermes/profiles/<name>/memories/USER.md`. Memory is loaded at session start, so start a new session afterwards. Check with `hermes chat -q "What do you know about me?"`.
