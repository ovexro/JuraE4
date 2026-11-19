# JURA E4 Desktop App — Backlog

Forward-looking list: candidate next tasks, speculative enhancements, and known follow-ups that aren't blocking current work. Claude appends during sessions; user reviews on demand. Git log is authoritative for what has shipped — nothing here is a record of completed work.

## Candidate next tasks

Ideas proposed after the 2026-11-19 audit (none started):
- **Desktop notifications** (tray `showMessage`, with a settings toggle): brew finished while the window is hidden, machine needs water / beans / grounds emptied / tray, cleaning or descaling due, machine went off / came back (auto-off).
- **Single-instance guard** (`QLockFile`) + optional **start at login / start minimized to tray** — two instances fight over the dongle's single connection.
- **Usage history**: snapshot the lifetime counters on each connect -> cups per day/week and "descaling due in ~N cups".
- **Brew finished alert text/sound** and an in-app "what to do" hint for each blocking alert.
- **Romanian UI** option; **Home Assistant / REST** bridge (same idea as the Trellis API).
- **Mid-brew machine errors**: if `@TF` is pushed during a brew (not seen in the one logged brew) abort early instead of waiting for the 120 s timeout — needs a hardware test with a deliberately blocked machine.
- **Machine-started brews** (on the machine / J.O.E.) push `@TB` + 5-byte `@TV:23228F..` messages the app ignores; could show "machine is brewing".

## Known follow-ups

Small tech debt, edge cases, or minor bugs noticed in passing. Not blocking anything.

### UI & frontend
- Brew phase animation could show distinct grinding vs pouring phases (@TV has phase data in byte 0) — diminishing returns, current "Preparing..." + live progress is functional

### Backend & infrastructure
(empty)

### Not tested yet
- Full brew on the real machine with the new ack-driven animation, pre-brew alert check and 54 ms progress path (read-only hardware checks passed 2026-11-19: connect, polling, statistics, disconnect/reconnect; a brew needs a cup under the outlet)
- Mid-brew `@TS` / auto-off behaviour only verified against a fake dongle and the recorded log

### External
(empty)
