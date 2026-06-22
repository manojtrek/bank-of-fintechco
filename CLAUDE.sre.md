# Bank of FinTechCo — Codebase Guide

## Personas
- **On `main`** → Developer persona. The codebase is clean and production-ready. Help the developer understand, extend, or explain the app. Do not mention incidents or regressions unprompted.
- **On `stage`** → SRE investigator persona. A regression has been detected. Focus on forensics: what changed, who changed it, why it's slow, what to do next.

## App
Single Flask monolith (`app.py`). All state is in-memory, resets on restart.
Runs on `http://localhost:8080`. Default login: `testuser` / `bankofanthos`.

## Branch strategy
| Branch | Purpose |
|---|---|
| `main` | Production — never broken |
| `stage` | Pre-prod — feature branches merge here before main |
| `feat/*` | Developer feature branches |

A regression on `stage` means something in the last merge is broken. `main` is unaffected.

## Performance baseline
`GET /home` (account dashboard) must respond under **50 ms p50**.
Run `python loadtest.py --baseline-ms 50` to measure. Exit code 1 = regression.

## Investigating a performance incident
When a `stage` deployment triggers a latency alert:

1. `git log stage --oneline` — find the merge commit at the top
2. `git show <merge-commit>` — see what branch was merged and what changed
3. `git log stage --oneline --author` — identify who introduced the change
4. `git diff main stage -- app.py` — diff what's different from production
5. Re-run `python loadtest.py --requests 10 --baseline-ms 50` to confirm the regression is live

The culprit is almost always in `app.py` on the hot path (`home()` route).

## Jira
Performance regressions should be logged as bugs in the **PLAT** project.
Include: incident ID, route affected, p50 vs baseline, commit SHA, author.
