#!/usr/bin/env python3
"""Offline sequence analysis — pure Python (no dependencies).

Implements the dossier's PM4Py experiment (audit item 8 / dossier 4.2)
without requiring PM4Py: directly-follows graphs, trace variants, and a
simple conformance comparison against an intended flow. If PM4Py is
installed, pm4py_poc.py uses the real thing; this file always works.

Usage:
  python analysis/sequence.py --db ~/.dhriti/dhriti.sqlite3 \\
      --intended contract_sealed session_active browser_navigation \\
      evidence_submitted session_success
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_events(db_path: str, since: str = None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = ("SELECT event_id, occurred_at_utc, session_id, case_id, "
           "event_type, source_adapter, action_taken FROM event")
    params = []
    if since:
        sql += " WHERE occurred_at_utc>=?"
        params.append(since)
    sql += " ORDER BY occurred_at_utc, seq"
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()
    return rows


def directly_follows_graph(events):
    """Edges (a -> b) between consecutive events per case."""
    edges = Counter()
    by_case = defaultdict(list)
    for event in events:
        by_case[event["case_id"] or "uncased"].append(event)
    for case_events in by_case.values():
        for first, second in zip(case_events, case_events[1:]):
            edges[(first["event_type"], second["event_type"])] += 1
    return edges, by_case


def variants(by_case):
    """Trace variant frequency: which event sequences recur?"""
    traces = Counter()
    for case_events in by_case.values():
        traces[tuple(e["event_type"] for e in case_events)] += 1
    return traces


def conformance(by_case, intended):
    """How far observed sequences drift from the intended flow.

    Returns per-case alignment: the longest intended subsequence found
    in order within the observed trace (a simple LCS, not full
    conformance checking — enough to rank cases for manual review).
    """
    results = []
    intended = list(intended)
    for case_id, case_events in by_case.items():
        trace = [e["event_type"] for e in case_events]
        # longest common subsequence length
        dp = [[0] * (len(trace) + 1) for _ in range(len(intended) + 1)]
        for i in range(1, len(intended) + 1):
            for j in range(1, len(trace) + 1):
                if intended[i - 1] == trace[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        lcs = dp[len(intended)][len(trace)]
        results.append({
            "case_id": case_id,
            "events": len(trace),
            "intended_alignment": round(
                lcs / len(intended), 3) if intended else 1.0,
        })
    return sorted(results, key=lambda r: r["intended_alignment"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--since", default=None,
                        help="YYYY-MM-DDTHH:MM:SSZ")
    parser.add_argument("--intended", nargs="*", default=[
        "contract_sealed", "session_active", "evidence_submitted",
        "session_success"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    events = load_events(args.db, args.since)
    if not events:
        print("no events found")
        return 0
    edges, by_case = directly_follows_graph(events)
    traces = variants(by_case)
    conf = conformance(by_case, args.intended)

    if args.json:
        print(json.dumps({
            "events": len(events),
            "cases": len(by_case),
            "dfg": [
                {"from": a, "to": b, "count": n}
                for (a, b), n in edges.most_common()],
            "variants": [
                {"trace": list(t), "count": n}
                for t, n in traces.most_common()],
            "conformance": conf,
        }, indent=2))
        return 0

    print(f"events: {len(events)}  cases: {len(by_case)}")
    print("\nDirectly-follows graph (top 20):")
    for (a, b), n in edges.most_common(20):
        print(f"  {a:<32} -> {b:<32} {n:>5}")
    print("\nTrace variants (top 10):")
    for trace, n in traces.most_common(10):
        print(f"  {n:>3} x {' > '.join(trace)}")
    print("\nLowest alignment with intended flow:")
    for row in conf[:10]:
        print(f"  {row['case_id'][:8] if row['case_id'] else '-':<10} "
              f"alignment={row['intended_alignment']:<6} "
              f"events={row['events']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # being piped into head/less is normal for a CLI; exit quietly
        sys.exit(0)
