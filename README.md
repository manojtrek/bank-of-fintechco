# Bank of FinTechCo (Monolith)

A **very simple monolith** version of the banking demo app.

Originally a complex microservices + Java + Docker + Kubernetes setup.  
This version consolidates everything into a **single Python Flask app with pure in-memory state** (sample records preloaded). No database, no Docker required. Data resets on restart.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080

**Login:** `testuser` / `bankofanthos`

Other demo users also work: alice, bob, eve (same password).

Stop with Ctrl-C.

## What works

- Login / Signup (new users get a random 10-digit account #)
- View current balance (computed live from ledger)
- Transaction history (credits/debits with contact labels)
- Send payments (to existing contacts or new internal recipients)
- Deposit funds (from external accounts)
- Add contacts on-the-fly during send/deposit
- Logout

## Features kept simple

- **Everything in memory** (dicts + lists) — preloaded sample records
- All logic in one process
- Flask sessions for auth (no JWT microservice)
- No tracing, metrics, Loki, Grafana
- No Kubernetes / Skaffold / Istio / Docker / database
- Minimal dependencies (just Flask)

## Project layout

```
app.py                 # The entire monolith (in-memory users/contacts/transactions)
requirements.txt
static/                # Copied frontend assets (css, js, img)
templates/             # Jinja templates (adapted)
```

## Notes

- Amounts stored internally in cents.
- Sample data (4 users + contacts + transactions) is loaded in memory on startup.
- Testuser starts with a positive balance from demo transactions.
- Routing numbers are simulated (local = 883745000).
- Everything resets when the process restarts.
- This is for demo / learning purposes only.

Based on Bank of Anthos concepts, rebranded for FinTechCo.
