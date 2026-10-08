# Contributing / agent operational notes

## Pushing to `origin` from an AI agent sandbox

This repo is owned by GitHub user **GeirMagnusPettersen**. Some agent sandboxes
have a *different* default git/GitHub identity baked into the environment
(e.g. a `GH_TOKEN` env var pointing at a `geirp_microsoft`-style service
account). That default identity has **no write access** to this repo, so a
plain `git push` will fail with a 403, even though `gh auth status` may show
`GeirMagnusPettersen` as already logged in (via keyring) alongside the
service account.

If `git push` returns 403 here, don't assume push is impossible — check
whether the right account is simply shadowed:

```powershell
gh auth status
```

If `GeirMagnusPettersen` is listed as logged in (just not "active" because a
`GH_TOKEN`/`GITHUB_TOKEN` env var is overriding it), use this pattern in a
**single** PowerShell command (env var changes do not persist across
separate tool/process invocations, so all of this must run together):

```powershell
$env:GH_TOKEN = ''; $env:GITHUB_TOKEN = ''
$tok = gh auth token --user GeirMagnusPettersen
$url = "https://x-access-token:$tok@github.com/GeirMagnusPettersen/geir-life-hub.git"
git push $url HEAD:<branch-name>
$tok = $null
```

Notes:
- Clearing `GH_TOKEN`/`GITHUB_TOKEN` is required because their presence
  overrides `gh auth switch` — switching the "active" account alone does not
  work while the env var is set.
- Never print `$tok` or otherwise leak it into logs/output.
- This whole sequence must be re-run for every push in a fresh shell process,
  since env vars and shell state don't carry over between separate command
  invocations in this sandbox.
- If `GeirMagnusPettersen` isn't logged in at all, fall back to generating a
  patch/diff for the user to apply and push themselves from their own
  machine.
