#!/usr/bin/env python3
"""A fully simulated Dhriti day — the shipped proof that the core works.

Runs against a SimulatedClock in <home> (default: examples/demo/out):
bootcamp start -> cold ritual (contract file + seal) -> day opens at
10:00 -> session with arming gate -> a bounded, topic-locked research
pass -> real machine-checked proof -> a blocked-URL event -> session
SUCCESS -> day released early at day_close -> Vidura ingest of the
pass answer -> aftermath report -> backup -> chain verification.

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
from dhriti.timeutil import SimulatedClock  # noqa: E402

UTC = _dt.timezone.utc
START = _dt.datetime(2026, 11, 2, 4, 30, tzinfo=UTC)  # 10:00 IST

CONTRACT = {
    "identity_statement": "I am someone who ships code daily",
    "contract_line": "reverse the array in Java, in place",
    "main_belief": {"label": "compiler practice"},
    "main_belief_metric": "parse_decl passes its test",
    "main_belief_current_state": "behind on the C book chapters",
    "substitute_activities": ["reading about parsers",
                              "watched talks"],
    "substitute_budget": "2 hours per week",
    "profile": "coding",
    "targets": [
        {"label": "reversal passes its test",
         "evidence": {"class": "machine",
                      "command": "python3 -c \"print('5 4 3 2 1')\""}},
        {"label": "notes written",
         "evidence": {"class": "file", "path": "notes.md"}},
    ],
    "allowed_tools": ["docs.oracle.com"],
    # IF-THEN obstacle plan (optional group; complete when present)
    "expected_obstacle": "the reverse loop throws IndexOutOfBounds",
    "if_then_response": "check the loop bounds against the array "
                        "length before the swap",
    "return_condition": "rerun the test after the fix",
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

    banner("1/10  bootcamp start (30 days, no ordinary rule changes)")
    daemon.bootcamp.start(30)

    banner("2/10  cold-state ritual: write + seal today's contract")
    today = daemon._local_today().isoformat()
    contract_path = home / f"contract-{today}.json"
    contract_path.write_text(json.dumps(CONTRACT, indent=2),
                             encoding="utf-8")
    sealed = daemon.days.contracts.seal(today, CONTRACT)
    print(f"sealed contract {sealed['id'][:8]}: {CONTRACT['contract_line']}")

    banner("3/10  daemon tick at 10:00 — the day opens, wall up")
    daemon._tick()
    day = daemon.days.get(daemon._local_today())
    print(f"day state: {day['state']}  window "
          f"{day['window_start_at']} .. {day['window_end_at']} "
          f"(day_close {day['day_close_at']})")

    banner("4/10  session start through the arming gate")
    sess = daemon.start_session("reverse the array",
                                profile_name="coding")
    print(f"session {sess['id'][:8]}: {sess['state']}")
    policy = daemon.policy_engine.current_snapshot()
    print(f"policy v{policy['version']} frozen: "
          f"mode={policy['work_mode']} "
          f"taper={policy['taper_stage']}")

    banner("5/10  an obstacle appears -> bounded, topic-locked pass")
    rp = daemon.passes.open(
        sess["id"],
        "does Arrays.asList reverse in place, or do I write the loop?",
        minutes=20, sources=["docs.oracle.com"])
    print(f"pass {rp['id'][:8]} open until {rp['expires_at']} "
          f"(question: {rp['question'][:50]}...)")
    daemon.passes.return_pass(
        "it does not; writing the swap loop myself, bounds checked")

    banner("6/10  work happens; the browser posts a navigation event")
    code = ("arr = [1, 2, 3, 4, 5]\n"
            "i, j = 0, len(arr) - 1\n"
            "while i < j:\n"
            "    arr[i], arr[j] = arr[j], arr[i]\n"
            "    i += 1; j -= 1\n"
            "print(' '.join(map(str, arr)))\n")
    workdir = home / "work"
    workdir.mkdir(exist_ok=True)
    (workdir / "reverse_array.py").write_text(code, encoding="utf-8")
    (workdir / "notes.md").write_text(
        "swap loop: bounds checked against length before each swap\n",
        encoding="utf-8")
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        session_id=sess["id"],
        observed={"url": "https://docs.oracle.com/en/java/",
                  "title": "Java docs"})

    banner("7/10  proof: machine-checked command (exit code is the fact)")
    ev = daemon.evidence.machine_check_command(
        sess["id"], "reversal passes its test",
        f"python3 {workdir / 'reverse_array.py'}")
    print(f"evidence [{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev['verdict_reason']}")
    print(f"  stdout: {ev['detail']['stdout_tail'].strip()}")
    ev2 = daemon.evidence.submit_file(
        sess["id"], "notes written", str(workdir / "notes.md"))
    print(f"evidence [{ev2['verdict']}] {ev2['class']}/{ev2['kind']}: "
          f"{ev2['verdict_reason']}")
    daemon.end_session_success(sess["id"])
    print(f"session ended: SUCCESS (accepted evidence = "
          f"{daemon.sessions.accepted_evidence_count(sess['id'])})")

    banner("8/10  20:01 — targets met, day releases early (bounded)")
    clock.advance(hours=10, minutes=1)
    daemon._tick()
    day = daemon.days.get(daemon._local_today())
    print(f"day state: {day['state']} released_at={day['released_at']}")
    stats = daemon.bootcamp.evidence_summary()
    print(f"bootcamp stats: {json.dumps(stats)}")

    banner("8a/10  a curiosity appears mid-session -> parked, not followed")
    from dhriti.review import ParkingLotService
    parking = ParkingLotService(daemon.db, clock, daemon.ledger)
    parked = parking.park(
        "why does the JVM verifier exist at all",
        kind="question", source="demo",
        sparked_by_url="https://youtube.com/watch?v=some-talk")
    print(f"parked ({parked['id'][:8]}) [{parked['kind']}]: "
          f"{parked['question']}")

    banner("8b/10  the evening: declared rest, drift, and the parked list")
    from dhriti.leisure import LeisureService
    clock.set(_dt.datetime(2026, 11, 2, 15, 45, tzinfo=UTC))  # 21:15 IST
    LeisureService(daemon.db, clock, daemon.ledger).declare(
        "one episode, chosen", 45, day_date="2026-11-02")
    # 21:30 IST — inside the declared window: declared rest
    clock.set(_dt.datetime(2026, 11, 2, 16, 0, tzinfo=UTC))
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        observed={"url": "https://www.youtube.com/watch?v=x",
                  "title": ""})
    # 23:00 IST — outside it: drift
    clock.set(_dt.datetime(2026, 11, 2, 17, 30, tzinfo=UTC))
    daemon.ledger.record(
        "browser_navigation", source_adapter="extension",
        observed={"url": "https://www.reddit.com", "title": ""})
    print("declared: one episode (45 min); observed: 1 rest, 1 drift")
    # the earned evening: the day's targets were met, so the parked
    # items are handed back (surface_evening)
    clock.set(_dt.datetime(2026, 11, 2, 16, 0, tzinfo=UTC))
    evening_items = parking.surface_evening("2026-11-02")
    for item in evening_items:
        print(f"evening: [{item['kind']}] {item['question']}")

    banner("9/10  Vidura: the day's pass answer becomes a spaced item")
    from dhriti.vidura import ViduraService
    vidura = ViduraService(daemon.db, daemon.config, clock,
                           daemon.ledger)
    items = vidura.ingest_pass_answers("2026-11-02")
    for item in items:
        print(f"vidura: [{item['kind']}] {item['front'][:60]}")
        print(f"         due {item['due_at']}")

    banner("10/10  aftermath + backup + health + verification")
    from dhriti.journal import JournalService
    journal = JournalService(home, clock)
    journal.add("the demo day ran clean; the wall held")
    print(f"journal: entry stored in {journal.path}")
    journal.close()
    paths = daemon.run_aftermath(daemon._local_today().isoformat())
    print(f"report: {paths['markdown']}")
    from dhriti.backup import BackupService
    backup = BackupService(home, daemon.db, daemon.ledger, clock)
    manifest = backup.create(home / "backups")
    print(f"backup: {manifest['dest']} "
          f"(chain verified: {manifest.get('chain_verified_after')})")
    verify = daemon.ledger.verify_chain()
    print(f"ledger chain: ok={verify['ok']} events={verify['checked']}")
    from dhriti.health import build_health
    report = build_health(home, config, clock, db=daemon.db,
                          ledger=daemon.ledger)
    for line in report.lines:
        if line.startswith("[ok  ]"):
            print(f"health: {line}")
    print(f"health: Overall: {report.overall}")
    anchor = daemon.ledger.write_anchor(note="demo end")
    print(f"anchor head: {anchor['head_hash'][:32]}...")

    # export + pure-python process mining
    export = daemon.ledger.export(str(home / "ledger_export.json"))
    print(f"ledger export: {export}")
    daemon.release_lock()
    daemon.db.close()

    seq = Path(__file__).resolve().parents[2] / "analysis" / "sequence.py"
    if seq.exists():
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(seq), "--db", str(home / "dhriti.sqlite3")],
            capture_output=True, text=True)
        print("\n" + proc.stdout)
    print("DEMO COMPLETE — open "
          f"{home / 'reports'}/aftermath-2026-11-02.html in a browser")


if __name__ == "__main__":
    main()
