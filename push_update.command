#!/bin/bash
# Run this EVERY TIME you've made changes and want to push an update to your dad.
# Double-click this file to run it (or run it in Terminal).
set -e
cd "$(dirname "$0")"

if [ ! -d .git ]; then
    echo "This folder isn't set up with GitHub yet."
    echo "Run setup_github.command first (one time only)."
    read -p "Press Enter to close..."
    exit 1
fi

CURRENT=$(grep -oE 'CURRENT_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"' adael_desktop.py | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$CURRENT" ]; then
    echo "Couldn't find CURRENT_VERSION in adael_desktop.py - check it wasn't renamed or edited."
    read -p "Press Enter to close..."
    exit 1
fi

MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"

echo "=== Adael Invoice App - push update ==="
echo "Current version: $CURRENT  ->  New version: $NEW_VERSION"
echo
read -p "One-line description of what changed (for your own records): " MSG
if [ -z "$MSG" ]; then
    MSG="Update"
fi

# Bump the version number in the code (macOS sed syntax)
sed -i '' "s/CURRENT_VERSION = \"$CURRENT\"/CURRENT_VERSION = \"$NEW_VERSION\"/" adael_desktop.py

git add -A
git commit -m "v$NEW_VERSION: $MSG"
git push origin main
git tag "v$NEW_VERSION"
git push origin "v$NEW_VERSION"

echo
echo "=== Pushed! ==="
echo "GitHub is now building the update: https://github.com/jshmrdaaa/Invoice-App/actions"
echo "Takes about 2-3 minutes. Once it's done, your dad's app will pick it up automatically"
echo "the next time he opens it while online - he doesn't need to do anything."
echo
read -p "Press Enter to close this window..."
