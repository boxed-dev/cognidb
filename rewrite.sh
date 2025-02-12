#!/bin/bash
# ==========================================
# WARNING: This script will rewrite your repository's commit history!
# It will update all commit history (commits, branches, and tags)
# with the following details:
#
#   Username: adrienckr
#   Email:    adrienicohen@gmail.com
#
# Additionally, it will add the following remote address (if not present):
#
#   https://github.com/adrienckr/CREWAI-powered-AGENTIC-Blood-Report-Analysis.git
#
# After running this script, you will need to force-push your changes:
#   git push --force --all
#   git push --force --tags
#
# Make sure to back up your repository before running this script.
# ==========================================

set -e  # Exit immediately if any command fails

# New commit details
NEW_NAME="adrienckr"
NEW_EMAIL="adcohen650@icloud.com"
REMOTE_URL="https://github.com/adrienckr/Zero-and-Few-Shot-Visual-Question-Answering.git"

# Function to print push instructions after rewriting history
function push_changes() {
    echo ""
    echo "=========================================="
    echo "History rewrite complete."
    echo "Force-push your changes with the following commands:"
    echo "  git push --force --all"
    echo "  git push --force --tags"
    echo "=========================================="
}

# Add remote 'origin' if it doesn't exist
if git remote | grep -q "^origin$"; then
    echo "Remote 'origin' already exists."
else
    echo "Adding remote 'origin' with URL: $REMOTE_URL"
    git remote add origin "$REMOTE_URL"
fi

# Check if git-filter-repo is installed and use it if available
if command -v git-filter-repo >/dev/null 2>&1; then
    echo "Using git-filter-repo to rewrite commit history..."
    git filter-repo --force --commit-callback '
commit.author_name = b"'"$NEW_NAME"'"
commit.author_email = b"'"$NEW_EMAIL"'"
commit.committer_name = b"'"$NEW_NAME"'"
commit.committer_email = b"'"$NEW_EMAIL"'"
'
    push_changes
else
    echo "git-filter-repo not found. Falling back to git filter-branch..."
    git filter-branch --env-filter '
export GIT_AUTHOR_NAME="'"$NEW_NAME"'"
export GIT_AUTHOR_EMAIL="'"$NEW_EMAIL"'"
export GIT_COMMITTER_NAME="'"$NEW_NAME"'"
export GIT_COMMITTER_EMAIL="'"$NEW_EMAIL"'"
' --tag-name-filter cat -- --branches --tags

    # Cleanup backup refs created by filter-branch
    rm -rf .git/refs/original/
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive

    push_changes
fi