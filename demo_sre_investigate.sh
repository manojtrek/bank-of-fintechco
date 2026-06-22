#!/usr/bin/env bash
# demo_sre_investigate.sh — Window 3 setup: land on stage and open Claude.
# Run this after demo_sre.sh has fired the incident.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

BOLD='\033[1m'; GREEN='\033[0;32m'; NC='\033[0m'

CURRENT=$(git branch --show-current)
if [ "$CURRENT" != "stage" ]; then
    git checkout stage --quiet
fi

# Load SRE persona context
cp "$REPO_DIR/CLAUDE.sre.md" "$REPO_DIR/CLAUDE.md"

echo ""
echo -e "${BOLD}━━━ SRE Investigation — Bank of FinTechCo ━━━${NC}"
echo ""
echo -e "${GREEN}Branch  :${NC} $(git branch --show-current)"
echo -e "${GREEN}Last commit :${NC} $(git log -1 --format='%h %s (%an)')"
echo ""
echo "You received: :rotating_light: INC-... — Account dashboard is responding slowly."
echo ""
echo "Ask Claude: 'We got an incident — dashboard is slow. What changed?'"
echo ""

claude
