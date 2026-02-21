#!/usr/bin/env bash
# Run this in your terminal (sudo will prompt for password).
# Then run: gh auth login
# Then run: ./scripts/github-pages-setup.sh

set -e
cd "$(dirname "$0")/.."
REPO_OWNER="${GITHUB_REPO_OWNER:-Vinayak-Agarwal-2004}"
REPO_NAME="${GITHUB_REPO_NAME:-Mars-Eye-View}"

echo "Installing gh..."
sudo apt-get update -qq && sudo apt-get install -y gh

echo "Checking gh auth..."
if ! gh auth status &>/dev/null; then
  echo "Run: gh auth login"
  exit 1
fi

echo "Enabling GitHub Pages (deploy from branch gh-pages)..."
gh api "repos/${REPO_OWNER}/${REPO_NAME}/pages" -X PUT -f build_type=legacy -f 'source[branch]=gh-pages' -f 'source[path]=/'

echo "Setting VITE_API_BASE secret (paste your backend URL when prompted, e.g. https://your-oracle-ip:8000)..."
gh secret set VITE_API_BASE --repo "${REPO_OWNER}/${REPO_NAME}"

echo "Done. Push to main to trigger the deploy workflow."
