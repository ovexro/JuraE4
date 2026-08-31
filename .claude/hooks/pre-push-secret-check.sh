#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) -- blocks `git push` if the JURA E4 repo's
# jura_wifi_v2.py has the real AUTH_HASH secret in a commit about to be
# pushed. AUTH_HASH is normally protected via `git update-index
# --assume-unchanged`, but the commit workflow requires temporarily
# un-marking it, swapping the real hash for the empty placeholder, then
# committing -- if that swap-back step is ever skipped, this catches it
# before the secret reaches GitHub (the repo is public).
#
# Scoped to this repo specifically (hardcoded absolute path) rather than
# to the invoking shell's cwd, so it fires correctly regardless of how the
# git push command is phrased (bare, or prefixed with `cd ... &&`, etc.).
set -u

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

case "$CMD" in
    *"git push"*) ;;
    *) exit 0 ;;
esac

REPO="/home/ovidiu/jura-desktop"
[ -d "$REPO/.git" ] || exit 0

# Real hash shape: AUTH_HASH = "<64 hex chars>" (the repo placeholder is
# AUTH_HASH = "" -- empty, so this pattern only matches a real secret).
PATTERN='AUTH_HASH = "[0-9A-Fa-f]{64}"'

# What's about to be pushed: commits on HEAD not yet on origin/main.
FOUND=$(git -C "$REPO" diff origin/main..HEAD -- jura_wifi_v2.py 2>/dev/null \
    | grep -E "^\+.*${PATTERN}")

if [ -n "$FOUND" ]; then
    jq -n '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "BLOCKED: jura_wifi_v2.py'\''s real AUTH_HASH secret appears to be committed and about to be pushed to the public JuraE4 repo. The assume-unchanged swap-back-to-placeholder step was likely skipped. Set AUTH_HASH back to the empty placeholder, amend/recommit, then push."
        }
    }'
    exit 0
fi

exit 0
