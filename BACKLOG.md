# JURA E4 Desktop App — Backlog

Forward-looking list: candidate next tasks, speculative enhancements, and known follow-ups that aren't blocking current work. Claude appends during sessions; user reviews on demand. Git log is authoritative for what has shipped — nothing here is a record of completed work.

## Candidate next tasks

Ideas proposed after the 2026-11-19 audit (notifications and single-instance/autostart have shipped):
- **Usage history**: snapshot the lifetime counters on each connect -> cups per day/week and "descaling due in ~N cups".
- **Notification extras**: optional sound, "what to do" hint per blocking alert, click-to-open from the balloon (QSystemTrayIcon.messageClicked -> `_tray_show`).
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
- Mid-brew `@TS` / machine switched off in the MIDDLE of a brew: only verified against a fake dongle (a real brew was verified end to end on 2026-11-19, see below)
- Deliberately blocked machine (no water / no beans) to see what the machine itself pushes and whether the pre-brew check matches reality

### Verified on the real machine (2026-11-19, first brew with the new code)
- Espresso 45 ml through the GUI: confirm dialog -> cards locked -> ack in 166 ms -> "Brewing started!" -> heating 57->60 C (~16 s at 0%) -> 10..100% in ~14 s -> done, 32 s total; every `@TV` handled 50 ms after arrival (was 300 ms). Cards unlocked afterwards.
- The dongle sent `@TS` 13 s after completion; the app noticed in ~110 ms and reconnected in 2.5 s (first attempt got `Connection reset by peer` during `@HP` because the dongle still held the old session; the 2 s backoff retry succeeded). Old code needed ~30 s.
- During the heating phase the machine pushes 5-byte `@TV:21028F0x08` messages (byte 3 counts 01->08) that the app ignores; could drive a real "heating" progress.
- Possible polish: treat `ConnectionResetError` during `@HP` like a refused connect (retry inside `_do_connect`) to save the 2 s backoff.

### External
(empty)
