#!/usr/bin/env python3
"""
Bank of FinTechCo - Very Simple Monolith (In-Memory)

Single Flask app. Everything is in-memory with preloaded sample records.
No database, no files, resets on restart.
"""

import os
import re
import random
import datetime
import json
from decimal import Decimal
from functools import wraps

from flask import (
    Flask, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
LOCAL_ROUTING = "883745000"
SECRET_KEY = os.getenv("SECRET_KEY", "fintechco-monolith-dev-secret-change-me")
BANK_NAME = os.getenv("BANK_NAME", "Bank of FinTechCo")
DEFAULT_PASSWORD = "bankofanthos"

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["BANK_NAME"] = BANK_NAME
app.config["LOCAL_ROUTING"] = LOCAL_ROUTING

# Jinja helpers (match original frontend)
def format_currency(int_amount):
    if int_amount is None:
        return "$---"
    val = abs(Decimal(int_amount) / 100)
    s = "${:0,.2f}".format(val)
    return ("-" if int_amount < 0 else "") + s

def format_timestamp_day(ts):
    # Accept 'YYYY-MM-DD HH:MM:SS' or ISO
    try:
        if "T" in ts:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.strptime(ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d")
    except Exception:
        return "??"

def format_timestamp_month(ts):
    try:
        if "T" in ts:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.strptime(ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b")
    except Exception:
        return "???"

app.jinja_env.globals.update(
    format_currency=format_currency,
    format_timestamp_month=format_timestamp_month,
    format_timestamp_day=format_timestamp_day,
    bank_name=BANK_NAME,
)

# -----------------------------------------------------------------------------
# In-memory store (no database at all)
# -----------------------------------------------------------------------------
_users = {}                 # username -> full user dict
_account_map = {}           # accountid -> username
_contacts = {}              # username -> list of contact dicts
_transactions = []          # append-only list of tx dicts

def _now_ts():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def seed_demo_data():
    """Populate in-memory sample data (idempotent if already seeded)."""
    global _users, _account_map, _contacts, _transactions
    if _users:
        return

    pwd_hash = generate_password_hash(DEFAULT_PASSWORD, method="pbkdf2:sha256")

    demo_users = [
        ("1011226111", "testuser", "Test", "User"),
        ("1033623433", "alice", "Alice", "User"),
        ("1055757655", "bob", "Bob", "User"),
        ("1077441377", "eve", "Eve", "User"),
    ]

    for acct, uname, fn, ln in demo_users:
        user = {
            "accountid": acct,
            "username": uname,
            "passhash": pwd_hash,
            "firstname": fn,
            "lastname": ln,
            "birthday": "2000-01-01",
            "timezone": "-5",
            "address": "Bowling Green, New York City",
            "state": "NY",
            "zip": "10004",
            "ssn": "111-22-3333",
        }
        _users[uname] = user
        _account_map[acct] = uname

    # Contacts (same as original demo)
    seed_contacts = [
        ("testuser", "Alice", "1033623433", LOCAL_ROUTING, False),
        ("testuser", "Bob", "1055757655", LOCAL_ROUTING, False),
        ("testuser", "Eve", "1077441377", LOCAL_ROUTING, False),
        ("testuser", "External Bank", "9099791699", "808889588", True),
        ("alice", "Testuser", "1011226111", LOCAL_ROUTING, False),
        ("alice", "Bob", "1055757655", LOCAL_ROUTING, False),
        ("alice", "Eve", "1077441377", LOCAL_ROUTING, False),
        ("alice", "External Bank", "9099791699", "808889588", True),
        ("bob", "Testuser", "1011226111", LOCAL_ROUTING, False),
        ("bob", "Alice", "1033623433", LOCAL_ROUTING, False),
        ("bob", "Eve", "1077441377", LOCAL_ROUTING, False),
        ("bob", "External Bank", "9099791699", "808889588", True),
        ("eve", "Testuser", "1011226111", LOCAL_ROUTING, False),
        ("eve", "Alice", "1033623433", LOCAL_ROUTING, False),
        ("eve", "Bob", "1055757655", LOCAL_ROUTING, False),
        ("eve", "External Bank", "9099791699", "808889588", True),
    ]
    for username, label, acct, route, external in seed_contacts:
        _contacts.setdefault(username, []).append({
            "label": label,
            "account_num": acct,
            "routing_num": route,
            "is_external": external,
        })

    # Sample transactions (external deposits + internal activity)
    now = datetime.datetime.utcnow()
    base = now - datetime.timedelta(days=45)

    seed_txs = [
        # Initial external deposits (everyone starts with $2500 credit)
        ("9099791699", "1011226111", "808889588", LOCAL_ROUTING, 250000, base),
        ("9099791699", "1033623433", "808889588", LOCAL_ROUTING, 250000, base),
        ("9099791699", "1055757655", "808889588", LOCAL_ROUTING, 250000, base),
        ("9099791699", "1077441377", "808889588", LOCAL_ROUTING, 250000, base),

        # Some internal transfers
        ("1011226111", "1033623433", LOCAL_ROUTING, LOCAL_ROUTING, 12500, base + datetime.timedelta(days=5)),
        ("1055757655", "1011226111", LOCAL_ROUTING, LOCAL_ROUTING, 4500, base + datetime.timedelta(days=9)),
        ("1011226111", "1077441377", LOCAL_ROUTING, LOCAL_ROUTING, 3200, base + datetime.timedelta(days=12)),
        ("1033623433", "1011226111", LOCAL_ROUTING, LOCAL_ROUTING, 8900, base + datetime.timedelta(days=20)),

        # Recent activity
        ("1011226111", "1055757655", LOCAL_ROUTING, LOCAL_ROUTING, 2100, now - datetime.timedelta(days=2)),
        ("9099791699", "1011226111", "808889588", LOCAL_ROUTING, 50000, now - datetime.timedelta(days=1)),
    ]

    for fr_ac, to_ac, fr_rt, to_rt, amt, ts in seed_txs:
        _transactions.append({
            "from_acct": fr_ac,
            "to_acct": to_ac,
            "from_route": fr_rt,
            "to_route": to_rt,
            "amount": amt,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        })

    print("Seeded in-memory demo data (users + contacts + sample transactions).")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapper

def current_user():
    return {
        "username": session.get("username"),
        "account_id": session.get("account_id"),
        "name": session.get("name"),
    }

def get_balance(account_id):
    """Compute balance by scanning the in-memory ledger."""
    bal = 0
    for tx in _transactions:
        if tx["to_acct"] == account_id and tx["to_route"] == LOCAL_ROUTING:
            bal += tx["amount"]
        if tx["from_acct"] == account_id and tx["from_route"] == LOCAL_ROUTING:
            bal -= tx["amount"]
    return bal

def get_transactions(account_id, limit=50):
    """Return recent transactions involving this account (newest first)."""
    relevant = []
    for tx in reversed(_transactions):
        if (tx["from_acct"] == account_id and tx["from_route"] == LOCAL_ROUTING) or \
           (tx["to_acct"] == account_id and tx["to_route"] == LOCAL_ROUTING):
            relevant.append({
                "fromAccountNum": tx["from_acct"],
                "toAccountNum": tx["to_acct"],
                "fromRoutingNum": tx["from_route"],
                "toRoutingNum": tx["to_route"],
                "amount": tx["amount"],
                "timestamp": tx["timestamp"],
            })
            if len(relevant) >= limit:
                break
    return relevant

def get_contacts(username):
    return list(_contacts.get(username, []))

def add_contact(username, label, account_num, routing_num, is_external):
    """Add contact if not duplicate for this user."""
    existing = _contacts.setdefault(username, [])
    for c in existing:
        if c["account_num"] == account_num and c["routing_num"] == routing_num:
            return
    existing.append({
        "label": label or "Saved Account",
        "account_num": account_num,
        "routing_num": routing_num,
        "is_external": bool(is_external),
    })

def create_user(form):
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    password_repeat = form.get("password-repeat") or ""
    firstname = (form.get("firstname") or "").strip()
    lastname = (form.get("lastname") or "").strip()
    birthday = form.get("birthday") or "2000-01-01"
    timezone = form.get("timezone") or "-5"
    address = form.get("address") or "123 Main St"
    state = form.get("state") or "NY"
    zipc = form.get("zip") or "10004"
    ssn = form.get("ssn") or "111-22-3333"

    if not username or not password:
        raise ValueError("Username and password are required")
    if password != password_repeat:
        raise ValueError("Passwords do not match")
    if not re.match(r"^[a-zA-Z0-9_]{2,15}$", username):
        raise ValueError("Username must be 2-15 alphanumeric/underscore characters")

    if username in _users:
        raise ValueError("Username already exists")

    # Generate unique-ish 10-digit account id
    while True:
        acct = str(random.randint(1000000000, 9999999999))
        if acct not in _account_map:
            break

    ph = generate_password_hash(password, method="pbkdf2:sha256")
    user = {
        "accountid": acct,
        "username": username,
        "passhash": ph,
        "firstname": firstname,
        "lastname": lastname,
        "birthday": birthday,
        "timezone": timezone,
        "address": address,
        "state": state,
        "zip": zipc,
        "ssn": ssn,
    }
    _users[username] = user
    _account_map[acct] = username

    return acct, f"{firstname} {lastname}".strip() or username

def authenticate(username, password):
    user = _users.get(username)
    if not user:
        return None
    if not check_password_hash(user["passhash"], password):
        return None
    return {
        "username": user["username"],
        "account_id": user["accountid"],
        "name": f"{user['firstname']} {user['lastname']}".strip(),
    }

def record_transaction(from_acct, to_acct, from_route, to_route, amount):
    """amount in cents (positive int). Append to in-memory ledger."""
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if from_acct == to_acct and from_route == to_route:
        raise ValueError("Cannot send to yourself")
    _transactions.append({
        "from_acct": from_acct,
        "to_acct": to_acct,
        "from_route": from_route,
        "to_route": to_route,
        "amount": int(amount),
        "timestamp": _now_ts(),
    })

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def root():
    if "account_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login_page"))

@app.route("/home")
@login_required
def home():
    user = current_user()
    balance = get_balance(user["account_id"])
    history = get_transactions(user["account_id"])
    contacts = get_contacts(user["username"])

    # populate labels like original
    contact_map = {c["account_num"]: c["label"] for c in contacts}
    for t in history:
        if t["toAccountNum"] == user["account_id"]:
            t["accountLabel"] = contact_map.get(t["fromAccountNum"])
        else:
            t["accountLabel"] = contact_map.get(t["toAccountNum"])

    msg = request.args.get("msg")

    return render_template(
        "index.html",
        account_id=user["account_id"],
        balance=balance,
        contacts=contacts,
        cymbal_logo="false",
        history=history,
        message=msg,
        name=user["name"],
        platform="local",
        platform_display_name="Local",
        bank_name=BANK_NAME,
    )

@app.route("/login", methods=["GET"])
def login_page():
    if "account_id" in session:
        return redirect(url_for("home"))
    return render_template(
        "login.html",
        bank_name=BANK_NAME,
        cymbal_logo="false",
        default_password=DEFAULT_PASSWORD,
        default_user="testuser",
        message=request.args.get("msg"),
        platform="local",
    )

@app.route("/login", methods=["POST"])
def login():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    user = authenticate(username, password)
    if not user:
        return render_template(
            "login.html",
            bank_name=BANK_NAME,
            cymbal_logo="false",
            default_password=DEFAULT_PASSWORD,
            default_user=username,
            message="Login failed. Please try again.",
            platform="local",
        )
    session["username"] = user["username"]
    session["account_id"] = user["account_id"]
    session["name"] = user["name"]
    return redirect(url_for("home"))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/signup", methods=["GET"])
def signup_page():
    if "account_id" in session:
        return redirect(url_for("home"))
    return render_template("signup.html", bank_name=BANK_NAME, cymbal_logo="false")

@app.route("/signup", methods=["POST"])
def signup():
    try:
        acct, full_name = create_user(request.form)
        # auto-login
        username = request.form.get("username")
        user = authenticate(username, request.form.get("password"))
        if user:
            session["username"] = user["username"]
            session["account_id"] = user["account_id"]
            session["name"] = user["name"]
        return redirect(url_for("home", msg="Account created successfully"))
    except Exception as e:
        return render_template(
            "signup.html",
            bank_name=BANK_NAME,
            cymbal_logo="false",
            message=str(e),
        )

@app.route("/payment", methods=["POST"])
@login_required
def payment():
    user = current_user()
    try:
        recipient = request.form.get("account_num") or ""
        if recipient == "add":
            recipient = (request.form.get("contact_account_num") or "").strip()
            label = (request.form.get("contact_label") or "").strip() or "New Contact"
            if recipient:
                add_contact(user["username"], label, recipient, LOCAL_ROUTING, False)

        amount_str = request.form.get("amount") or "0"
        amount = int(Decimal(amount_str) * 100)

        if not recipient or len(recipient) != 10 or not recipient.isdigit():
            return redirect(url_for("home", msg="Payment failed: bad account"))

        # balance check
        current_bal = get_balance(user["account_id"])
        if amount > current_bal:
            return redirect(url_for("home", msg="Payment failed: insufficient funds"))

        record_transaction(
            user["account_id"], recipient,
            LOCAL_ROUTING, LOCAL_ROUTING,
            amount
        )
        return redirect(url_for("home", msg="Payment successful"))
    except Exception as e:
        return redirect(url_for("home", msg=f"Payment failed: {e}"))

@app.route("/deposit", methods=["POST"])
@login_required
def deposit():
    user = current_user()
    try:
        acct_field = request.form.get("account") or ""
        ext_acct = None
        ext_route = None
        if acct_field == "add":
            ext_acct = (request.form.get("external_account_num") or "").strip()
            ext_route = (request.form.get("external_routing_num") or "").strip()
            ext_label = (request.form.get("external_label") or "").strip() or "External"
            if ext_route == LOCAL_ROUTING:
                return redirect(url_for("home", msg="Deposit failed: external routing cannot be local"))
            if ext_acct:
                add_contact(user["username"], ext_label, ext_acct, ext_route, True)
        else:
            # JSON string value from the external contact <select>
            try:
                details = json.loads(acct_field)
                ext_acct = details.get("account_num")
                ext_route = details.get("routing_num")
            except Exception:
                ext_acct = (request.form.get("external_account_num") or "").strip()
                ext_route = (request.form.get("external_routing_num") or "").strip()

        amount_str = request.form.get("amount") or "0"
        amount = int(Decimal(amount_str) * 100)

        if not ext_acct or not ext_route:
            return redirect(url_for("home", msg="Deposit failed: missing external account"))

        # For deposit, we record "external -> my account"
        record_transaction(ext_acct, user["account_id"], ext_route, LOCAL_ROUTING, amount)
        return redirect(url_for("home", msg="Deposit successful"))
    except Exception as e:
        return redirect(url_for("home", msg=f"Deposit failed: {e}"))

# Simple health endpoints (useful for docker later if wanted)
@app.route("/ready")
def ready():
    return "ok", 200

@app.route("/version")
def version():
    return "monolith-v1", 200

# -----------------------------------------------------------------------------
# Startup - seed sample data in memory
# -----------------------------------------------------------------------------
seed_demo_data()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting Bank of FinTechCo monolith (in-memory) on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "false").lower() == "true")
