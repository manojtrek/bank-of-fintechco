#!/usr/bin/env bash
# Window 3 — SRE investigation: land on stage, open Claude for forensics.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${BOLD}━━━ Window 3 — SRE Investigation ━━━${NC}"
echo ""

bash "$REPO_DIR/demo_sre_investigate.sh"
