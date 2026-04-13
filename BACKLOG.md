# JURA E4 Desktop App — Backlog

Forward-looking list: candidate next tasks, speculative enhancements, and known follow-ups that aren't blocking current work. Claude appends during sessions; user reviews on demand. Git log is authoritative for what has shipped — nothing here is a record of completed work.

## Candidate next tasks

Concrete enough to pick up in a future session. Each has scope + what it unblocks. Not a priority order.

- **Fix brew animation lifecycle** — Animation disappears after ~1 second instead of tracking full brew cycle. Needs investigation of @TB/@TV progress handling and QTimer/animation state management. Also verify animation phases match real machine timing (grinding phase before water pouring). Touches: `jura_app.py` brew animation code, signal handling from `jura_wifi_v2.py`. Reported 2026-04-13.
- **Investigate cancel-then-brew state** — User cancelled brew confirmation dialog, then brewed successfully, but animation was broken. Check if cancelling the dialog leaves stale state that affects the next brew attempt. Touches: `jura_app.py` brew confirmation dialog + animation state.

## Known follow-ups

Small tech debt, edge cases, or minor bugs noticed in passing. Not blocking anything.

### UI & frontend
- Brew phase animation could show distinct grinding vs pouring phases (@TV has phase data in byte 0)

### Backend & infrastructure
(empty)

### Not tested yet
(empty)

### External
(empty)
