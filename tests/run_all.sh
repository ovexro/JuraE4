#!/bin/bash
# Run every test file and summarise PASS/FAIL counts. Exit 1 if anything failed.
cd "$(dirname "$0")/.."
fail=0
for t in tests/*_test.py; do
  out=$(timeout 180 python3 -u "$t" 2>&1)
  p=$(printf '%s\n' "$out" | grep -c '^PASS'); f=$(printf '%s\n' "$out" | grep -c '^FAIL')
  printf '%-28s PASS=%-3s FAIL=%s\n' "$t" "$p" "$f"
  [ "$f" -gt 0 ] || [ "$p" -eq 0 ] && { fail=1; printf '%s\n' "$out" | grep -E '^FAIL|Traceback|Error' | head -5; }
done
exit $fail
