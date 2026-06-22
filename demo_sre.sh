#!/usr/bin/env bash
# demo_sre.sh — SRE persona trigger:
#   1. Create/reset the stage branch and merge feat/audit-signing into it
#   2. Restart the Flask app on the staged code
#   3. Run the load test against the golden baseline
#   4. If regression detected, post a Slack incident via curl

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load secrets from ~/.env (survives repo deletion)
[ -f "$HOME/.env" ] && set -a && source "$HOME/.env" && set +a

FEAT_BRANCH="feat/audit-signing"
STAGE_BRANCH="stage"
BASELINE_MS=50
REQUESTS=10
APP_URL="http://localhost:8080"
SLACK_CHANNEL_ID="C0BC495E9D2"          # #all-things-sre
SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-}"  # export SLACK_BOT_TOKEN=xoxb-... before running

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[SRE]${NC} $*"; }
warn() { echo -e "${YELLOW}[SRE]${NC} $*"; }
die()  { echo -e "${RED}[SRE] ERROR:${NC} $*"; exit 1; }

[ -n "$SLACK_BOT_TOKEN" ] || die "SLACK_BOT_TOKEN is not set. Run: export SLACK_BOT_TOKEN=xoxb-..."

cd "$REPO_DIR"

# Discard any local working tree changes before starting
git restore . 2>/dev/null || true

# ── 1. Merge feat → stage (main stays untouched) ──────────────────────────────
echo ""
echo -e "${BOLD}━━━ Step 1 — Merge $FEAT_BRANCH → $STAGE_BRANCH (main untouched) ━━━${NC}"

git fetch origin --quiet

if git show-ref --verify --quiet "refs/heads/$STAGE_BRANCH"; then
    log "Resetting existing $STAGE_BRANCH to main..."
    git checkout "$STAGE_BRANCH" --quiet
    git reset --hard main --quiet
else
    log "Creating $STAGE_BRANCH from main..."
    git checkout -b "$STAGE_BRANCH" main --quiet
fi

MERGE_OUT=$(git merge --no-ff "origin/$FEAT_BRANCH" \
    -m "Merge $FEAT_BRANCH into $STAGE_BRANCH [staging deploy]" 2>&1) && {
    log "Merged $FEAT_BRANCH into $STAGE_BRANCH."
    echo "$MERGE_OUT"
} || {
    if echo "$MERGE_OUT" | grep -q "Already up to date"; then
        warn "Already up to date — continuing."
    else
        echo "$MERGE_OUT"
        die "Merge failed. Resolve conflicts and re-run."
    fi
}

# ── 2. Restart app on staged code ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Step 2 — Restart Flask app on $STAGE_BRANCH ━━━${NC}"

EXISTING_PID=$(lsof -ti :8080 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    log "Stopping existing app (PID $EXISTING_PID)..."
    kill "$EXISTING_PID" 2>/dev/null || true
    sleep 1
fi

log "Starting app..."
python app.py > /tmp/bank-app.log 2>&1 &
APP_PID=$!

log "Waiting for app to be ready..."
READY=0
for _ in $(seq 1 20); do
    if curl -sf "$APP_URL/ready" > /dev/null 2>&1; then
        READY=1; break
    fi
    sleep 0.5
done
[ "$READY" -eq 1 ] || die "App did not start. Check /tmp/bank-app.log"
log "App is ready (PID $APP_PID)."

# ── 3. Load test ───────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Step 3 — Load test (baseline: ${BASELINE_MS}ms p50) ━━━${NC}"
echo ""

set +e
LOADTEST_OUTPUT=$(python loadtest.py --requests "$REQUESTS" --baseline-ms "$BASELINE_MS" 2>&1)
LOADTEST_EXIT=$?
set -e
echo "$LOADTEST_OUTPUT"

# ── 4. Incident? Post to Slack via curl ───────────────────────────────────────
if [ "$LOADTEST_EXIT" -ne 1 ]; then
    echo ""
    log "All clear — p50 within baseline. Safe to promote $STAGE_BRANCH → main."
    exit 0
fi

echo ""
echo -e "${BOLD}━━━ Step 4 — Regression detected — posting Slack incident ━━━${NC}"

INCIDENT_ID="INC-$(date +%Y%m%d-%H%M)"

echo -e "${RED}  Incident ID : $INCIDENT_ID${NC}"
echo ""
log "Posting to Slack #all-things-sre..."

SLACK_PAYLOAD=$(python3 - <<PYEOF
import json
payload = {
    "channel": "${SLACK_CHANNEL_ID}",
    "text": ":rotating_light: *${INCIDENT_ID}* — Account dashboard is responding slowly. Needs investigation."
}
print(json.dumps(payload))
PYEOF
)

SLACK_RESPONSE=$(curl -s -X POST https://slack.com/api/chat.postMessage \
    -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$SLACK_PAYLOAD")

SLACK_OK=$(echo "$SLACK_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok','false'))")

if [ "$SLACK_OK" = "True" ] || [ "$SLACK_OK" = "true" ]; then
    log "Incident ${INCIDENT_ID} posted to #all-things-sre."
else
    SLACK_ERR=$(echo "$SLACK_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','unknown'))")
    warn "Slack post failed: $SLACK_ERR"
    warn "Raw response: $SLACK_RESPONSE"
fi

echo ""
echo -e "${RED}[SRE] ${INCIDENT_ID} open. main is clean — $STAGE_BRANCH blocked from promotion.${NC}"
exit 1
