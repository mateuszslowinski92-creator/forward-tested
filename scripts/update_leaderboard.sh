#!/bin/bash
# update_leaderboard.sh — regeneruje publiczny ranking i publikuje na GitHub Pages.
# Uruchamiane przez launchd co 6h (com.pmverify.leaderboard).
set -euo pipefail

SITE="/Users/mateuszslowinski/pm-verify"
GEN="/Users/mateuszslowinski/polybot/scripts/build_public_leaderboard.py"
PY="/opt/homebrew/bin/python3.11"
LOG="$HOME/Library/Logs/polybot/forward-tested.log"

mkdir -p "$(dirname "$LOG")"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] start"
  cd "$SITE"

  # 1) regeneracja danych (bootstrap CI; ~20 s)
  "$PY" "$GEN" --out "$SITE/data" 2>&1 | sed 's/^/  /'

  # 2) commit tylko gdy dane faktycznie się zmieniły
  git add -A
  if git diff --cached --quiet; then
    echo "  brak zmian — nic nie publikuję"
  else
    git -c user.name="Forward Tested" -c user.email="noreply@github.com" \
        commit -q -m "data: refresh $(date -u +%Y-%m-%dT%H:%MZ)"
    if git push -q origin main 2>&1; then
      echo "  opublikowano na GitHub Pages"
    else
      echo "  BŁĄD push — dane zacommitowane lokalnie, publikacja nieudana"
    fi
  fi
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] koniec"
} >> "$LOG" 2>&1
