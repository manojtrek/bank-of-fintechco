#!/usr/bin/env bash
# Window 2 — SRE trigger: merge feat branch, run load test, fire Slack alert.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${BOLD}━━━ Window 2 — SRE Trigger ━━━${NC}"
echo ""

bash "$REPO_DIR/demo_sre.sh"
