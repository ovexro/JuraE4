# JURA E4 Desktop App — Backlog

Forward-looking list: candidate next tasks, speculative enhancements, and known follow-ups that aren't blocking current work. Claude appends during sessions; user reviews on demand. Git log is authoritative for what has shipped — nothing here is a record of completed work.

## Candidate next tasks

(empty — no high-value tasks remaining)

## Known follow-ups

Small tech debt, edge cases, or minor bugs noticed in passing. Not blocking anything.

### UI & frontend
- Brew phase animation could show distinct grinding vs pouring phases (@TV has phase data in byte 0) — diminishing returns, current "Preparing..." + live progress is functional
- Dead code: `_handle_brew_progress()` in jura_wifi_v2.py:605 — defined but never called, same logic is inline in `_do_brew`
- Tray quick-brew duplicates `_on_card_brew` animation setup logic — could extract shared method

### Backend & infrastructure
(empty)

### Not tested yet
(empty)

### External
(empty)
