#!/usr/bin/env bash
# demo_sre.sh — SRE persona trigger:
#   1. Merge feat/audit-signing → main
#   2. Restart the Flask app on the merged code
#   3. Run the load test against the golden baseline
#   4. If regression detected, fire a Slack incident via Claude CLI

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
FEAT_BRANCH="feat/audit-signing"
BASELINE_MS=50
REQUESTS=10
APP_URL="http://localhost:8080"
SLACK_CHANNEL_ID="C0BC495E9D2"   # #all-things-sre

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[SRE]${NC} $*"; }
warn() { echo -e "${YELLOW}[SRE]${NC} $*"; }
die()  { echo -e "${RED}[SRE] ERROR:${NC} $*"; exit 1; }

cd "$REPO_DIR"

# ── 1. Merge ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Step 1 — Merge $FEAT_BRANCH → main ━━━${NC}"
git checkout main --quiet

MERGE_OUT=$(git merge --no-ff "$FEAT_BRANCH" \
    -m "Merge $FEAT_BRANCH into main" 2>&1) && {
    log "Merged successfully."
    echo "$MERGE_OUT"
} || {
    if echo "$MERGE_OUT" | grep -q "Already up to date"; then
        warn "Branch already merged — continuing."
    else
        echo "$MERGE_OUT"
        die "Merge failed. Resolve conflicts and re-run."
    fi
}

# ── 2. Restart app ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Step 2 — Restart Flask app ━━━${NC}"

EXISTING_PID=$(lsof -ti :8080 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    log "Stopping existing app (PID $EXISTING_PID)..."
    kill "$EXISTING_PID" 2>/dev/null || true
    sleep 1
fi

log "Starting app on merged code..."
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
[ "$READY" -eq 1 ] || die "App did not start in time. Check /tmp/bank-app.log"
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

# ── 4. Incident alert ──────────────────────────────────────────────────────────
if [ "$LOADTEST_EXIT" -ne 1 ]; then
    echo ""
    log "All clear — p50 within baseline. No incident."
    exit 0
fi

echo ""
echo -e "${BOLD}━━━ Step 4 — Regression detected — firing Slack alert via Claude ━━━${NC}"

INCIDENT_JSON=$(echo "$LOADTEST_OUTPUT" | grep -A1 "^INCIDENT_DETECTED" | grep "^{")
[ -n "$INCIDENT_JSON" ] || die "Could not parse INCIDENT_DETECTED JSON from loadtest output."

read P50 BASELINE RATIO P95 P99 RPS <<< $(echo "$INCIDENT_JSON" | python3 - <<'PYEOF'
import sys, json
d = json.load(sys.stdin)
print(d["p50_ms"], d["baseline_ms"], d["ratio"], d["p95_ms"], d["p99_ms"], d["rps"])
PYEOF
)

echo -e "${RED}  p50 = ${P50}ms  (${RATIO}x over ${BASELINE}ms baseline)${NC}"
echo ""
log "Invoking Claude CLI to post incident to Slack channel $SLACK_CHANNEL_ID..."
echo ""

claude --print \
"Use the Slack MCP tool to post a performance incident alert to Slack channel ID ${SLACK_CHANNEL_ID} (#all-things-sre).

Incident details:
- Route: GET /home (account dashboard)
- p50 latency: ${P50}ms — that is ${RATIO}x over the ${BASELINE}ms golden baseline
- p95: ${P95}ms | p99: ${P99}ms | throughput: ${RPS} req/sec
- Trigger: merge of branch ${FEAT_BRANCH} into main
- Repo: $(pwd)

Format it as a clear, urgent incident notification with these numbers."

echo ""
echo -e "${RED}[SRE] Incident fired to Slack. Hand off to SRE on-call for investigation.${NC}"
exit 1
