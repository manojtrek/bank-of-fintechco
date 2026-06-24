# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Bank of FinTechCo — Developer Workspace

## Who you are working with
A developer at FinTechCo building features on the account dashboard. The codebase is clean and production-ready. Help them understand, extend, and explain the app. Do not mention incidents, regressions, or the SRE workflow unprompted.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # starts on http://localhost:8080
```

There is no test suite. Verify changes by running the app and exercising the affected route manually.

## App
Single Flask monolith (`app.py`). All state is in-memory, resets on restart.
Runs on `http://localhost:8080`. Default login: `testuser` / `bankofanthos` (also: alice, bob, eve — same password).

## Codebase overview
| File | What it does |
|---|---|
| `app.py` | Entire backend — routes, auth, in-memory ledger, helpers |
| `templates/` | Jinja2 HTML templates (index, login, signup, consent + `shared/`) |
| `static/` | CSS and assets |

Key routes: `GET /home` (dashboard), `POST /payment`, `POST /deposit`, `GET /login`, `POST /signup`

Health probes (no auth): `GET /ready`, `GET /version`

## Internal data model

**Amounts are in cents** (integer). `$1.00` is stored as `100`. Always convert with `int(Decimal(amount_str) * 100)`.

In-memory store (module-level globals, reset on restart):
- `_users` — `{username: user_dict}` where `user_dict` has `accountid`, `passhash`, `firstname`, `lastname`, etc.
- `_account_map` — `{accountid: username}` reverse lookup
- `_contacts` — `{username: [contact_dict]}` where each contact has `label`, `account_num`, `routing_num`, `is_external`
- `_transactions` — append-only list; each entry has `from_acct`, `to_acct`, `from_route`, `to_route`, `amount`, `timestamp`

Balance is computed live by scanning `_transactions` (no stored balance field).

Local routing number: `883745000` (constant `LOCAL_ROUTING`). External transfers use a different routing number.

**Flask session keys**: `account_id`, `username`, `name` — set on login, cleared on logout.

## Jinja template helpers

Registered globally via `app.jinja_env.globals.update(...)`:
- `format_currency(int_amount)` — renders cents as `$1,234.56`
- `format_timestamp_month(ts)` / `format_timestamp_day(ts)` — parse `YYYY-MM-DD HH:MM:SS` strings
- `bank_name` — the `BANK_NAME` env var (default `"Bank of FinTechCo"`)

## `app.py` section order
Config → In-memory store → Helpers → Routes → Startup (`seed_demo_data()` call)

## Current branch: main
This is production. Clean, stable, no known issues. Any new feature should be built on a `feat/` branch off main.

---

## FinTechCo Engineering Standards
These apply to every change, every route, every file. Follow them without being asked.

### API & route naming
- REST only — resource-based, plural nouns: `/accounts`, `/transactions`, `/contacts`
- Never verb-in-URL patterns: no `/getBalance`, `/fetchUser`, `/doPayment`
- Route parameters use snake_case: `/accounts/<account_id>` not `/accounts/<accountId>`
- Query params for filtering, path params for identity: `GET /transactions?limit=50` not `GET /transactions/limit/50`

### Security — non-negotiable
- **Never log PII**: no account numbers, SSNs, full names, or balances in print/log statements
- **All user input validated** at the route boundary before touching any data structure
- **No string formatting for dynamic values** — use parameterized patterns or explicit type casts
- **Authentication check first**: every protected route must call `login_required` before any logic
- **Redirect after POST**: all POST routes must redirect on success (PRG pattern) — never render on POST

### Error handling
- User-facing errors redirect to `/home?msg=<message>` — never expose stack traces
- Internal errors caught with `except Exception as e` and surfaced as a clean message
- Error messages describe the problem without leaking internals: "Payment failed: insufficient funds" ✓ — "KeyError: 'amount'" ✗

### Python & Flask conventions
- Function names: `snake_case`. Never abbreviate beyond obvious: `acct` ok, `a` not ok
- One route per function — no shared handler for GET/POST unless trivially simple
- Helper functions live above the Routes section in `app.py`, below the In-memory store section
- No unused imports. No commented-out code committed to main.

### Code style
- 4-space indentation, no tabs
- Blank line between every top-level function
- Keep routes thin — business logic belongs in helper functions, not inside the route handler
