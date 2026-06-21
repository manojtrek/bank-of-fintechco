# Payment Processing

How money movement works in the Bank of FinTechCo monolith (`app.py`).

## Overview

There is no ledger database, no separate payments service, and no double-entry
bookkeeping. A **single in-memory list**, `_transactions`, is the entire system
of record. Every transfer — internal payment or external deposit — is just one
dict appended to that list. There is no concept of an account "balance" field;
balance is always *derived* by replaying the list.

```python
_transactions = []   # append-only list of tx dicts, oldest first
```

Each entry has the shape:

```python
{
    "from_acct":  "1011226111",   # sender account number
    "to_acct":    "1033623433",   # recipient account number
    "from_route": "883745000",    # sender routing number
    "to_route":   "883745000",    # recipient routing number
    "amount":     12500,          # cents, always positive
    "timestamp":  "2026-06-21 16:30:00",
}
```

Amounts are stored as **integer cents** to avoid floating point rounding
issues; the UI/forms work in dollars and convert via `Decimal`.

## Two payment flows

### 1. Internal payment — `POST /payment`

Used for the "Send Payment" modal (money to another FinTechCo customer).

`templates/index.html` renders a recipient `<select>` from the user's saved
contacts (`account.is_external == False`) plus an **"add new recipient"**
option. `static/scripts/index.js` toggles extra fields (account number,
label) when "New Recipient" is chosen and client-side validates the form
(required fields, amount > 0) before submit.

Server-side (`app.py:payment()`):

1. Read `account_num` from the form. If it's the literal string `"add"`,
   pull the new account number/label from `contact_account_num` /
   `contact_label` instead, and save it via `add_contact()` for next time.
2. Convert `amount` (dollars string) to integer cents:
   `int(Decimal(amount_str) * 100)`.
3. **Validate the recipient**: must be exactly 10 digits, numeric.
4. **Validate funds**: call `get_balance(sender)` and reject if
   `amount > current_bal`.
5. Call `record_transaction()`, which appends a `from_acct=sender,
   to_acct=recipient, from_route=to_route=LOCAL_ROUTING` row.
6. Redirect to `/home` with a success/failure flash message.

There is no transaction atomicity: the balance check and the append happen
as two separate steps with no lock, so concurrent requests from the same
account could theoretically overdraw (acceptable for a demo, not for real
money).

### 2. Deposit — `POST /deposit`

Used for the "Deposit Funds" modal (money coming in from an external bank).

The form lets the user pick a saved **external** contact
(`account.is_external == True`) or add a new one. The selected option's
value is a JSON string `{"account_num": ..., "routing_num": ...}` (see
`templates/index.html:227`), which `deposit()` parses with `json.loads()`.
If parsing fails or "add" was chosen, it falls back to the raw
`external_account_num` / `external_routing_num` form fields.

Server-side (`app.py:deposit()`):

1. Resolve the external account/routing number (existing contact, new
   contact, or raw form fields as above).
2. Reject if the "external" routing number is actually the local routing
   number (`883745000`) — prevents disguising an internal transfer as a
   deposit.
3. Convert amount to cents.
4. Call `record_transaction(from_acct=external, to_acct=me,
   from_route=external_route, to_route=LOCAL_ROUTING, amount)`.
5. Redirect to `/home` with a flash message.

Deposits have **no funds check** (there's nothing to check — the money is
"arriving" from outside) and no real external bank integration; the
"External Bank" contact and routing number are just seeded fake data.

## Balance and history derivation

Nothing is precomputed. Every time `/home` loads:

```python
def get_balance(account_id):
    bal = 0
    for tx in _transactions:
        if tx["to_acct"] == account_id and tx["to_route"] == LOCAL_ROUTING:
            bal += tx["amount"]
        if tx["from_acct"] == account_id and tx["from_route"] == LOCAL_ROUTING:
            bal -= tx["amount"]
    return bal
```

Only transactions where the *local* leg (`to_route`/`from_route ==
LOCAL_ROUTING`) matches `account_id` count — this is what lets the same
ledger represent both sides of a deposit (external leg ignored, local leg
credited) and both sides of an internal payment (debit sender, credit
recipient), using one shared list.

`get_transactions()` does a reverse scan of the same list to build the
transaction history table, then `home()` annotates each row with a contact
label by looking up the other party's account number in the user's
contacts.

## Validation summary

| Check | Where | Rule |
|---|---|---|
| Recipient format | `payment()` | exactly 10 numeric digits |
| Sufficient funds | `payment()` | `amount <= get_balance(sender)` |
| External routing ≠ local | `deposit()` | rejects routing == `883745000` |
| Amount > 0 | `record_transaction()` | raises `ValueError` |
| No self-transfer | `record_transaction()` | same acct+route on both sides rejected |
| Client-side | `index.js` | HTML5 required fields, amount min 0.01, max = current balance (payment) / $500,000 (deposit) |

## Known limitations (acceptable for a demo, not production)

- No locking/transactions — concurrent requests can race past the balance check.
- `get_balance`/`get_transactions` are O(n) full-list scans; fine at demo
  scale, would not scale to a real bank's transaction volume.
- Exceptions in `/payment` and `/deposit` are caught broadly and turned into
  a flash message, which would hide real bugs in a production system.
- No idempotency: the client generates a `uuid` hidden field per form
  submission, but the server never reads or checks it, so a double-submit
  would create a duplicate transaction.
