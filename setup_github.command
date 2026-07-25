#!/bin/bash
# ONE-TIME SETUP - connects this folder to GitHub so you can push updates.
# Double-click this file to run it (or run it in Terminal).
set -e
cd "$(dirname "$0")"

echo "=== Adael Invoice App - GitHub setup ==="
echo

if ! command -v git >/dev/null 2>&1; then
    echo "Git isn't installed. On a Mac, run this in Terminal first, then re-run this script:"
    echo "    xcode-select --install"
    read -p "Press Enter to close..."
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "Recommended: install the GitHub CLI so pushing never asks you for a password."
    echo "  1. Install Homebrew (if you don't have it): https://brew.sh"
    echo "  2. Run: brew install gh"
    echo "  3. Run: gh auth login   (choose GitHub.com, HTTPS, login with a web browser)"
    echo
    echo "You can skip this and continue - git will ask you to sign in the first time you push instead."
    read -p "Press Enter to continue with setup..."
else
    if ! gh auth status >/dev/null 2>&1; then
        echo "Signing in to GitHub via the GitHub CLI..."
        gh auth login --hostname github.com --git-protocol https --web
    fi
    gh auth setup-git
fi

echo
echo "Setting up the local Git repo..."
rm -rf .git
git init -b main
git config user.name "Thiago Chabla"
git config user.email "tcha4058@icloud.com"
git remote add origin https://github.com/jshmrdaaa/Invoice-App.git

git add -A
git commit -m "Initial commit: Adael invoice/estimate desktop app"

echo
echo "Merging with what's already on GitHub..."
git fetch origin
git merge origin/main --allow-unrelated-histories -X ours -m "Merge existing GitHub repo contents" || true

echo
echo "Pushing to GitHub (you may be asked to sign in)..."
git push -u origin main

echo
echo "Tagging v1.0.0 so GitHub builds the first release..."
git tag -f v1.0.0
git push -f origin v1.0.0

echo
echo "=== Done! ==="
echo "GitHub is building the app now: https://github.com/jshmrdaaa/Invoice-App/actions"
echo "In a couple minutes, grab the .exe from: https://github.com/jshmrdaaa/Invoice-App/releases"
echo "Give your dad that first .exe. After this, use push_update.command for every future change."
echo
read -p "Press Enter to close this window..."
