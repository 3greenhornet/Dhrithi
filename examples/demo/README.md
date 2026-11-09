# Demo — a fully simulated Dhriti day

`run_demo.py` executes a complete day against a simulated clock in
`out/` (regenerated each run):

```
python3 examples/demo/run_demo.py            # or: scripts/dev.sh demo
```

The script performs, in order:

1. bootcamp start (30 days)
2. cold-state ritual — seals the daily contract
3. daemon tick at 10:00 — day opens, wall up
4. session start through the arming gate (policy snapshot frozen)
5. a bounded research pass (declared source, expiry, returned)
6. work: a real file is written; a browser navigation event is
   normalized into the ledger
7. machine-checked proof — an actual command runs, exit code 0
   accepted
8. 20:01 with targets met — the day releases early (bounded by the
   21:00 ceiling either way)
9. aftermath report (MD + HTML), hash-chain verification, anchor,
   ledger export, and pure-Python sequence analysis

## Artifacts to open afterwards

- `out/reports/aftermath-2026-11-02.html` — the report a real evening
  would show you: contract vs reality, proof, breaks, loop log with
  honest adapter disclosure, facts separated from interpretation,
  your identity line in your own words.
- `out/dhriti.sqlite3` — the ledger; try
  `python3 -m dhriti.cli --home out verify` (chain check) or
  `python3 analysis/sequence.py --db out/dhriti.sqlite3`.
- `out/ledger_export.json` — the raw normalized events.

The demo doubles as an integration test: if any step of the day model
regresses, it fails loudly.
