#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
[ "$(git branch --show-current)" = main ] || { echo "Switch to main before publishing weekly data."; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Review and commit local edits before updating."; exit 1; }
git pull --ff-only origin main
python3 fpl_dashboard_updater.py
git add dashboard_data.js
if git diff --cached --quiet; then echo "No data changes."; exit 0; fi
git commit -m "Update finalized FPL snapshot"
git push origin main
echo "Data pushed. GitHub Pages will deploy the updated snapshot."
