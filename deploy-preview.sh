#!/usr/bin/env bash
# Publishes the demo copy (banner, noindex) to GitHub Pages: branch gh-pages of fabien-lopes/le-bistrot-du-theatre.
set -euo pipefail
cd "$(dirname "$0")"
REPO=fabien-lopes/le-bistrot-du-theatre
PREVIEW=1 BASE_PATH=/le-bistrot-du-theatre BASE_URL=https://fabien-lopes.github.io/le-bistrot-du-theatre python3 build.py
tmp=$(mktemp -d)
cp -R dist/. "$tmp"
git -C "$tmp" init -q -b gh-pages
git -C "$tmp" add -A
git -C "$tmp" commit -q -m "Preview $(date +%Y-%m-%d)"
git -C "$tmp" push -q -f "https://github.com/$REPO.git" gh-pages
rm -rf "$tmp"
python3 build.py >/dev/null   # put the production build back in dist/
echo "https://fabien-lopes.github.io/le-bistrot-du-theatre/"
