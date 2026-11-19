# Tests

Self-contained checks that run **without a coffee machine**: most start a fake
WiFi-V2 dongle on localhost (`127.0.0.1`, ports 51992-51999) that replays the
timings measured from a real dongle (`@TF` at once, `@tg` ~200 ms later, `@TV`
progress pushes, `@TS` session end ...). The GUI tests render widgets offscreen
(`QT_QPA_PLATFORM=offscreen`) and never open a connection.

```bash
source .venv/bin/activate
./tests/run_all.sh            # everything (~4-5 min; the link-death tests wait for real timeouts)
python3 tests/edge_test.py    # or one file; each line is PASS/FAIL
```

| File | Covers |
|------|--------|
| `edge_test.py` | `_recv_all`: expect/grace, split messages, bundles, close-after-data, garbage |
| `timing_test.py` | connect / poll / statistics / brew-progress latency numbers |
| `cooldown_test.py` | cooldown from brew END; failed start doesn't arm it |
| `filter_test.py` | "Filter alert" hidden only when the filter is N/A |
| `ts_test.py` | unsolicited `@TS` in a poll and mid-brew |
| `linkdead_test.py` | closed link vs silent dongle detection, socket options |
| `lockstarve_test.py` | `is_brewing` never blocks during a brew |
| `refuse_test.py` | refused connects are retried, then the J.O.E. hint |
| `dash_test.py` | brew animation starts only on ack; rejected/no-ack/stray cases |
| `stats_guard_test.py` | statistics blocked while brewing/disconnected |
| `preflight_test.py` | pre-brew alert check, product-aware |
| `reconnect_test.py` | never-give-up reconnect, Disconnect mid-reconnect |

Tests never talk to a real dongle and never contain the auth hash (the module's
`AUTH_HASH` is whatever your local copy has; the fake dongle accepts anything).
