#!/usr/bin/env bash
# Stop hook -- if the JURA E4 repo's local HEAD matches the last-known
# origin/main (i.e. a push likely just happened this turn), remind to
# update FEATURES.md/BACKLOG.md/memory files. Reminder only, never blocks.
# Does NOT fetch (no network call on every Stop event) -- relies on the
# local origin/main tracking ref, which `git push` itself updates on
# success, so this is accurate immediately after a push in this session.
set -u

REPO="/home/ovidiu/jura-desktop"
[ -d "$REPO/.git" ] || exit 0

LOCAL=$(git -C "$REPO" rev-parse HEAD 2>/dev/null) || exit 0
REMOTE=$(git -C "$REPO" rev-parse origin/main 2>/dev/null) || exit 0

if [ -n "$LOCAL" ] && [ "$LOCAL" = "$REMOTE" ]; then
    jq -n '{systemMessage: "jura-desktop: HEAD matches origin/main (a push likely just happened). Reminder: update FEATURES.md/BACKLOG.md and memory files if this turn shipped a feature/fix not yet reflected there."}'
fi

exit 0
