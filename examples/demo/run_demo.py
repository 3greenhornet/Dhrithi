#!/usr/bin/env python3
"""A fully simulated Dhriti day — the shipped proof that the core works.

Runs against a SimulatedClock in <home> (default: examples/demo/out):
bootcamp start -> cold ritual -> day opens at 10:00 -> session with
arming gate -> a bounded research pass -> real machine-checked proof
(compile + run a Java-ish snippet with python) -> a blocked-URL event
-> session SUCCESS -> day released early at day_close -> aftermath
report -> chain verification -> PM4Py-style sequence analysis.

Every artifact lands in <home> (ledger DB + reports) so you can open
the aftermath HTML and see exactly what a day looks like.

Usage: python examples/demo/run_demo.py [--home DIR]
"""

import argparse
import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dhriti.constants import DEFAULT_CONFIG  # noqa: E402
from dhriti.daemon import Daemon  # noqa: E402
from dhriti.models import ContractKind  # noqa: E402
from dhriti.timeutil import SimulatedClock  # noqa: E402

UTC = _dt.timezone.utc
START = _dt.datetime(2026, 11, 2, 4, 30, tzinfo=UTC)  # 10:00 IST

CONTRACT = {
    "mandatory_task": "Reverse an array in Java (in-place, then print)",
    "smallest_next_action":
        "open ReverseArray.java and write the swap loop header",
    "evidence": [{"kind": "command"},
                 {"kind": "file", "accept_nonzero_exit": False}],
    "targets": [{"kind": "session_count", "count": 1},
                {"kind": "evidence_accepted", "count": 1}],
    "allowed_tools": ["docs.oracle.com"],
    "blocked_tools": [],
    "core_belief": "I am becoming a backend engineer",
    "identity_statement": "I am someone who ships code daily",
    "work_mode": "closed_world",
    # D-030 main-belief group + IF-THEN plan (schema v2)
    "main_belief": "I want to be a software engineer",
    "main_belief_metric": "pass the CS course; ship a working project",
    "main_belief_current_state": "I am behind on the course and avoiding "
                                 "the compiler",
    "substitute_activities": ["guitar practice", "multiplayer games"],
    "substitute_budget": "3 hours per week",
    "expected_obstacle": "the reverse loop throws IndexOutOfBounds",
    "if_then_response": "check the loop bounds against the array length "
                        "before the swap",
    "return_condition": "rerun the test after the fix",
    "emergency_policy": "medical, family, or the laptop is on fire",
}


def banner(text):
    print("\n" + "=" * 62)
    print(text)
    print("=" * 62)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default=str(
        Path(__file__).parent / "out"))
    args = parser.parse_args()
    home = Path(args.home).resolve()
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True)

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["timezone"] = "Asia/Kolkata"
    config["bridge"]["port"] = 0  # ephemeral; demo does not serve HTTP
    clock = SimulatedClock(START)

    daemon = Daemon(home, config=config, clock=clock, tick_seconds=0.0)

    banner("1/9  bootcamp start (30 days, no ordinary rule changes)")
    daemon.bootcamp.start(30)

    banner("2/9  cold-state ritual: seal today's contract")
    cid = daemon.days.contracts.create_draft(
        ContractKind.DAILY, daemon._local_today().isoformat(), CONTRACT)
    daemon.days.contracts.seal(cid)
    print(f"sealed contract {cid[:8]}: {CONTRACT['mandatory_task']}")

    banner("3/9  daemon tick at 10:00 — the day opens, wall up")
    daemon._tick()
    day = daemon.days.get(daemon._local_today())
    print(f"day state: {day['state']}  window "
          f"{day['window_start_at']} .. {day['window_end_at']} "
          f"(day_close {day['day_close_at']})")

    banner("4/9  session start through the arming gate")
    sess = daemon.start_session(
        "reverse the array", '[{"kind":"command"}]',
        profile_name="coding", condition="D")
    print(f"session {sess['id'][:8]}: {sess['state']}")
    policy = daemon.policy_engine.current_snapshot()
    print(f"policy v{policy['version']} frozen: "
          f"mode={policy['work_mode']} "
          f"taper={policy['taper_stage']}")

    banner("5/9  an obstacle appears -> bounded research pass")
    rp = daemon.research.start(
        dependency="unsure whether Arrays.asList reverses in place",
        sources=["docs.oracle.com"],
        return_condition="back to ReverseArray.java, write the swap "
                         "loop manually",
        session_id=sess["id"], day_id=day["id"], max_minutes=20)
    print(f"pass {rp['id'][:8]} open until {rp['expires_at']} "
          f"(sources: {', '.join(rp['sources'])})")
    daemon.research.return_to_task(rp["id"], "it does not; writing "
                                             "the loop myself")

    banner("6/9  work happens; the browser posts a navigation event")
    code = ("arr = [1, 2, 3, 4, 5]\n"
            "i, j = 0, len(arr) - 1\n"
            "while i < j:\n"
            "    arr[i], arr[j] = arr[j], arr[i]\n"
            "    i += 1; j -= 1\n"
            "print(' '.join(map(str, arr)))\n")
    workdir = home / "work"
    workdir.mkdir(exist_ok=True)
    (workdir / "reverse_array.py").write_text(code, encoding="utf-8")
    # the extension would POST this to the bridge; demo writes it
    # through the same normalization path:
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        session_id=sess["id"],
        observed_payload={"url": "https://docs.oracle.com/en/java/",
                          "title": "Java docs"})

    banner("7/9  proof: machine-checked command (exit code is the fact)")
    ev = daemon.evidence.machine_check_command(
        sess["id"], f"python3 {workdir / 'reverse_array.py'}")
    print(f"evidence [{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev['verdict_reason']}")
    print(f"  stdout: {ev['detail']['stdout_tail'].strip()}")
    daemon.end_session_success(sess["id"])
    print(f"session ended: SUCCESS (accepted evidence = "
          f"{daemon.sessions.accepted_evidence_count(sess['id'])})")

    banner("8/9  20:01 — targets met, day releases early (bounded)")
    clock.advance(hours=10, minutes=1)
    daemon._tick()
    day = daemon.days.get(daemon._local_today())
    print(f"day state: {day['state']} released_at={day['released_at']}")
    stats = daemon.bootcamp.evidence_summary()
    print(f"bootcamp stats: {json.dumps(stats)}")

    banner("8b/9  the evening: declared rest, and one drift (D-046/D-047)")
    from dhriti.leisure import LeisureService
    clock.set(_dt.datetime(2026, 11, 2, 15, 45, tzinfo=UTC))  # 21:15 IST
    LeisureService(daemon.db, clock, daemon.ledger).declare(
        "one episode, chosen", 45, day_date="2026-11-02")
    # 21:30 IST — inside the declared window: declared rest
    clock.set(_dt.datetime(2026, 11, 2, 16, 0, tzinfo=UTC))
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        observed_payload={"url": "https://www.youtube.com/watch?v=x",
                          "title": ""})
    # 23:00 IST — outside it: drift
    clock.set(_dt.datetime(2026, 11, 2, 17, 30, tzinfo=UTC))
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        observed_payload={"url": "https://www.reddit.com", "title": ""})
    print("declared: one episode (45 min); observed: 1 rest, 1 drift")

    banner("9/9  aftermath + verification + sequence analysis")
    paths = daemon.run_aftermath(daemon._local_today().isoformat())
    print(f"report: {paths['markdown']}")
    verify = daemon.ledger.verify_chain()
    print(f"ledger chain: ok={verify['ok']} events={verify['checked']}")
    anchor = daemon.ledger.write_anchor(note="demo end")
    print(f"anchor head: {anchor['head_hash'][:32]}...")

    # export + pure-python process mining
    export = daemon.ledger.export(str(home / "ledger_export.json"))
    print(f"ledger export: {export}")
    daemon.release_lock()
    daemon.db.close()

    # sequence analysis on the demo ledger
    seq = Path(__file__).resolve().parents[2] / "analysis" / "sequence.py"
    if seq.exists():
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(seq), "--db", str(home / "dhriti.sqlite3")],
            capture_output=True, text=True)
        print("\n" + proc.stdout)
    print("DEMO COMPLETE — open "
          f"{home / 'reports'}/aftermath-2026-11-02.html in a browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
