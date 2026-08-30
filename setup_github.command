#!/bin/bash
set -u
cd "$(dirname "$0")"
REPO_URL="https://github.com/filmsurr/smt-npi-fpl-dashboard.git"
BRANCH="main"

fail(){ echo; echo "ERROR: $1"; echo; read -n 1 -s -r -p "Press any key to close..."; echo; exit 1; }

command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed. Install Python 3, then run this file again."
command -v git >/dev/null 2>&1 || fail "Git is not available. On macOS, run 'xcode-select --install' once, then retry."

python3 - <<'PY' >/dev/null 2>&1 || fail "No internet connection or GitHub is unavailable."
import urllib.request
urllib.request.urlopen('https://github.com', timeout=10).read(32)
PY

echo "SMT NPI FPL — first-time GitHub setup"
echo "Repository: $REPO_URL"
echo

if [ ! -d .git ]; then
  git init >/dev/null || fail "Could not initialize Git in this folder."
  git branch -M "$BRANCH" >/dev/null 2>&1 || true
fi

if git remote get-url origin >/dev/null 2>&1; then
  CURRENT=$(git remote get-url origin)
  if [ "$CURRENT" != "$REPO_URL" ]; then
    echo "Changing origin from: $CURRENT"
    git remote set-url origin "$REPO_URL" || fail "Could not update Git remote."
  fi
else
  git remote add origin "$REPO_URL" || fail "Could not add GitHub remote."
fi

if [ -z "$(git config user.name || true)" ]; then
  echo "Git needs your name for commits."
  read -r -p "Name: " GIT_NAME
  [ -n "$GIT_NAME" ] || fail "Git name cannot be blank."
  git config user.name "$GIT_NAME"
fi
if [ -z "$(git config user.email || true)" ]; then
  echo "Git needs your email for commits."
  read -r -p "Email: " GIT_EMAIL
  [ -n "$GIT_EMAIL" ] || fail "Git email cannot be blank."
  git config user.email "$GIT_EMAIL"
fi

# Pull existing remote history first when possible. If histories conflict, stop rather than overwrite.
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "Existing main branch found on GitHub. Synchronizing safely..."
  git fetch origin "$BRANCH" || fail "Could not fetch the GitHub repository. Check authentication/internet."
  if git rev-parse HEAD >/dev/null 2>&1; then
    git pull --rebase --autostash origin "$BRANCH" || fail "Git conflict detected. Resolve the conflict in the repository, then run setup again."
  else
    # Preserve this new package, check out the existing remote history, then overlay the package.
    TMPDIR_SETUP=$(mktemp -d)
    tar --exclude='.git' --exclude='.fpl_cache' -cf "$TMPDIR_SETUP/package.tar" . || fail "Could not back up the dashboard package during setup."
    find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
    git checkout -B "$BRANCH" "origin/$BRANCH" || fail "Could not check out the existing GitHub main branch."
    tar -xf "$TMPDIR_SETUP/package.tar" -C . || fail "Could not restore the new dashboard files over the repository."
    rm -rf "$TMPDIR_SETUP"
  fi
fi

echo "Updating FPL data before first publish..."
python3 fpl_dashboard_updater.py || fail "FPL update failed. Check internet/FPL API availability, then retry."

git add . || fail "Could not stage dashboard files."
if git diff --cached --quiet; then
  echo "No file changes need committing."
else
  git commit -m "Set up SMT NPI FPL dashboard" || fail "Git commit failed."
fi

git push -u origin "$BRANCH" || fail "GitHub push failed. Authentication may be required. Sign in to GitHub/Git Credential Manager, then retry."

echo
echo "Published to GitHub."
echo "One final GitHub Pages setting may be required the first time."
echo "Opening Repository Settings > Pages..."
open "https://github.com/filmsurr/smt-npi-fpl-dashboard/settings/pages" >/dev/null 2>&1 || true

echo
echo "In Pages, choose GitHub Actions as the publishing source if it is not already enabled."
echo "After that, all future updates can use update_and_publish.command."
echo
read -n 1 -s -r -p "Press any key to close..."
echo
