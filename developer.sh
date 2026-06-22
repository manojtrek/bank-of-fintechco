#!/usr/bin/env bash
# Window 1 — Developer persona: clean production codebase on main.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

BOLD='\033[1m'; GREEN='\033[0;32m'; NC='\033[0m'

git checkout main --quiet

# Load developer persona context
cp "$REPO_DIR/CLAUDE.developer.md" "$REPO_DIR/CLAUDE.md"

echo ""
echo -e "${BOLD}━━━ Developer Workspace — Bank of FinTechCo ━━━${NC}"
echo ""
echo -e "${GREEN}Branch      :${NC} $(git branch --show-current)"
echo -e "${GREEN}Last commit :${NC} $(git log -1 --format='%h %s (%an)')"
echo ""

claude
