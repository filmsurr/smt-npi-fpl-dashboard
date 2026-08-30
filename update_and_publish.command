#!/bin/bash
set -u
cd "$(dirname "$0")"
BRANCH="main"

fail(){ echo; echo "ERROR: $1"; echo; read -n 1 -s -r -p "Press any key to close..."; echo; exit 1; }
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed."
command -v git >/dev/null 2>&1 || fail "Git is not available."
[ -d .git ] || fail "Git is not configured in this folder. Run setup_github.command first."
git remote get-url origin >/dev/null 2>&1 || fail "No GitHub remote is configured. Run setup_github.command first."

python3 - <<'PY' >/dev/null 2>&1 || fail "No internet connection or FPL API is unavailable."
import urllib.request
urllib.request.urlopen('https://fantasy.premierleague.com/api/bootstrap-static/', timeout=12).read(32)
PY

# Protect user edits and avoid hiding conflicts.
DIRTY=$(git status --porcelain | grep -v '^?? \.fpl_cache/' || true)
if [ -n "$DIRTY" ]; then
  # dashboard_data.js may be dirty from a previous local update; all other changes should be reviewed.
  OTHER=$(echo "$DIRTY" | grep -v 'dashboard_data.js' || true)
  [ -z "$OTHER" ] || fail "Uncommitted project changes were found. Commit/review them before publishing to avoid a conflict."
fi

echo "Synchronizing with GitHub..."
git pull --rebase origin "$BRANCH" || fail "Git conflict detected. Resolve it first, then run this updater again."

BEFORE=""
[ -f dashboard_data.js ] && BEFORE=$(shasum dashboard_data.js | awk '{print $1}')

echo "Downloading latest FPL data..."
python3 fpl_dashboard_updater.py || fail "FPL update failed. The existing published dashboard was not changed."
AFTER=$(shasum dashboard_data.js | awk '{print $1}')

if [ "$BEFORE" = "$AFTER" ]; then
  echo
echo "No new data. dashboard_data.js is unchanged."
  read -n 1 -s -r -p "Press any key to close..."; echo; exit 0
fi

GW=$(python3 - <<'PY'
import json,re
s=open('dashboard_data.js',encoding='utf-8').read()
m=re.search(r'window\.FPL_DASHBOARD_DATA\s*=\s*(\{.*\});\s*$',s,re.S)
if not m: print('unknown')
else:
    try: print(json.loads(m.group(1)).get('latest_gw','unknown'))
    except Exception: print('unknown')
PY
)

git add dashboard_data.js || fail "Could not stage updated data."
git commit -m "Update FPL dashboard GW${GW}" || fail "Git commit failed."
git push origin "$BRANCH" || fail "GitHub push failed. Authentication may be required."

echo
echo "SUCCESS: GW${GW} dashboard published."
echo "GitHub Pages will redeploy automatically. Friends can refresh the same permanent URL."
echo
read -n 1 -s -r -p "Press any key to close..."
echo
