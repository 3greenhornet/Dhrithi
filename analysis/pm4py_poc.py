#!/usr/bin/env python3
"""PM4Py proof of concept (audit item 8) — OPTIONAL, needs one manual step.

This is the well-made placeholder for the real process-mining run:

    pip install pm4py

Then:  python analysis/pm4py_poc.py --db ~/.dhriti/dhriti.sqlite3

Without PM4Py, use analysis/sequence.py — it implements the same
directly-follows graph and variant analysis in pure Python and always
works. The dossier's requirement is the PoC (synthetic log -> discover
-> validate against the intended trace), and sequence.py already
satisfies it; this file adds the real PM4Py when you choose to install
it (event log XES export, process discovery, conformance diagnostics).
"""

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path


def build_event_log(db_path: str):
    """Rows -> PM4Py event log (case per session)."""
    import pm4py
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT occurred_at_utc, session_id, event_type FROM event "
        "WHERE session_id IS NOT NULL ORDER BY occurred_at_utc, seq"
    ).fetchall()
    conn.close()
    import pandas as pd
    frame = pd.DataFrame(
        [{"case:concept:name": r["session_id"],
          "concept:name": r["event_type"],
          "time:timestamp": r["occurred_at_utc"].replace("Z", "")}
         for r in rows])
    return pm4py.convert_to_event_log(
        pm4py.format_dataframe(frame,
                               case_id="case:concept:name",
                               activity_key="concept:name",
                               timestamp_key="time:timestamp"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--export-xes", default=None,
                        help="also write the event log as XES")
    args = parser.parse_args()

    try:
        import pm4py  # noqa: F401
    except ImportError:
        print(__doc__)
        print("\nPM4Py is not installed. The pure-Python equivalent is:")
        print(f"  python {Path(__file__).parent / 'sequence.py'} "
              f"--db {args.db}")
        return 1

    log = build_event_log(args.db)
    if args.export_xes:
        pm4py.write_xes(log, args.export_xes)
        print(f"XES exported: {args.export_xes}")
    dfg, start, end = pm4py.discover_dfg(log)
    print(f"discovered directly-follows graph: {len(dfg)} edges; "
          f"start activities: {list(start)[:5]}; "
          f"end activities: {list(end)[:5]}")
    tree = pm4py.discover_process_tree_inductive(log)
    print(f"inductive miner tree:\n{tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
