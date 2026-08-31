# JURA E4 Desktop App — Backlog

Forward-looking list: candidate next tasks, speculative enhancements, and known follow-ups that aren't blocking current work. Claude appends during sessions; user reviews on demand. Git log is authoritative for what has shipped — nothing here is a record of completed work.

## Candidate next tasks

Remaining findings from the 2026-08-31 concurrency/animation audit (7-dimension, adversarially
verified) not yet fixed — the two critical brew-animation bugs and 3 related correctness bugs
already shipped (commits 79e7eda, f99093c, 3bbd57f) and are hardware-verified.

- **Statistics screen hangs on "Loading…" if opened during a brew** — 100% reproducible: start
  any brew, click Statistics. `read_statistics()` no-ops without spawning a thread while
  `is_brewing`, but `_on_show_stats()` never checks that or disables the button first. Fix:
  check `self._wifi.is_brewing` in `_on_show_stats()`, show "Cannot read statistics while
  brewing" instead of a spinner that never resolves.
- **A rejected brew request still plays the full success animation** — `_on_card_brew` and
  `_tray_brew` both start the live-progress animation unconditionally, before knowing whether
  `WiFiV2Manager.brew()` actually accepted the request. A brew rejected for being inside the 10s
  cooldown (buttons can already be re-enabled by then) shows a fully simulated "live" fill and
  "Enjoy your coffee!" for a brew that was never sent to the machine. Same underlying code also
  duplicates the card-animation-setup block between the two call sites instead of sharing a
  helper — worth fixing together (move the setup into `_on_brew_started`, which only fires once
  the machine has actually ack'd the command).

## Known follow-ups

Small tech debt, edge cases, or minor bugs noticed in passing. Not blocking anything.

### UI & frontend
- Brew phase animation could show distinct grinding vs pouring phases (@TV has phase data in byte 0) — diminishing returns, current "Preparing..." + live progress is functional
- `disconnect_machine()`/`disconnect_and_wait()` run synchronous blocking socket I/O (+ a hardcoded 0.2s sleep) directly on the GUI thread instead of a background thread — freezes repaint/input briefly on every Disconnect click and app quit. `disconnect_and_wait`'s `timeout` param is also unused/vestigial.
- Mid-brew critical-alert abort branch in `_on_status` (jura_app.py) is unreachable dead code — status polling is paused for the whole brew and `_do_brew`'s listen loop doesn't forward `@TF` pushes either, so it never fires. Either wire `@TF` forwarding during brew, or just delete the branch.
- Unused imports in jura_app.py: `QSpacerItem`, `QSizePolicy`, `QSize`; redundant self-import of `BrewConfirmDialog` at jura_app.py:2091

### Backend & infrastructure
(empty)

### Not tested yet
(empty)

### External
(empty)
