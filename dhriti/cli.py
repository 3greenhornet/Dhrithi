"""Dhriti command line.

Wall Principle in the CLI: during an ACTIVE session, `dhriti status`
shows state, task and elapsed time. No coaching copy, no philosophy, no
"return to task!", no shame. The user's own contract is the only voice.
"""

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from . import __version__
from .bootcamp import BootcampService
from .break_glass import BreakGlassError, BreakGlassService
from .constants import default_home, load_config
from .daemon import Daemon
from .db import Database
from .day_window import DayService, resolve_window
from .errors import DhritiError
from .evidence import EvidenceService
from .ledger import Ledger
from .policy import PolicyEngine
from .profiles import DEFAULT_PROFILES, load_profiles
from .research_pass import ResearchService
from .review import (ParkingLotService, ColdReviewService,
                     REVIEW_QUESTIONS, build_digest)
from .leisure import LeisureService
from .session import SessionService
from .timeutil import Clock, RealClock, local_tz, to_iso
from .contract import ContractService
from .aftermath import AftermathService


def _home(args) -> Path:
    return Path(args.home).expanduser().resolve() if args.home \
        else default_home()


def _open_core(home: Path, clock: Clock = None):
    """Lightweight wiring for non-daemon commands."""
    clock = clock or RealClock()
    config = load_config(home)
    db = Database(home / "dhriti.sqlite3")
    ledger = Ledger(db, clock, int(
        config.get("ledger", {}).get("anchor_interval_events", 100)))
    services = {
        "config": config, "db": db, "ledger": ledger, "clock": clock,
        "contracts": ContractService(db, clock),
        "days": DayService(db, config, clock),
        "sessions": SessionService(db, clock),
        "evidence": EvidenceService(db, clock),
        "research": ResearchService(db, config, clock),
        "bootcamp": BootcampService(db, config, clock),
        "break_glass": BreakGlassService(db, config, clock, ledger),
        "aftermath": AftermathService(db, config, clock, ledger),
        "policy": PolicyEngine(db, clock),
        "parking": ParkingLotService(db, clock, ledger),
        "review": ColdReviewService(db, clock, ledger),
        "leisure": LeisureService(db, clock, ledger),
    }
    return services


# ---------------------------------------------------------------- commands
def cmd_init(args):
    home = _home(args)
    home.mkdir(parents=True, exist_ok=True)
    config = load_config(home)
    config_path = home / "dhriti.config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2),
                               encoding="utf-8")
        print(f"config written: {config_path}")
    (home / "profiles").mkdir(exist_ok=True)
    # bridge token is created lazily by the daemon; touch the DB now
    services = _open_core(home)
    from .bridge import ensure_token
    token = ensure_token(home)
    services["db"].close()
    print(f"dhriti home ready: {home}")
    print(f"bridge token: {home / 'bridge_token'} "
          f"(paste into extension/config.js)")
    print("next: dhriti ritual   # write today's contract, cold")


def cmd_ritual(args):
    """The cold-state ritual (PDF section 5.2). Interactive, or fully
    scripted via --set for tests/simulations."""
    home = _home(args)
    s = _open_core(home)
    clock: Clock = s["clock"]
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = clock.now_utc().astimezone(tz).date()

    if args.set:
        payload = json.loads(args.set)
    else:
        print("--- cold-state ritual (no session is active) ---")
        prev = s["days"].get(today)
        payload = {
            "mandatory_task": _ask("mandatory task"),
            "smallest_next_action": _ask("smallest next action"),
            "evidence": [{"kind": _ask(
                "evidence kind (command|file|manual|observed)")}],
            "targets": [{"kind": "session_count", "count": int(
                _ask("session target count for today", "1"))}],
            "allowed_tools": _ask_list("allowed tools/domains "
                                       "(comma separated)"),
            "blocked_tools": _ask_list("extra blocked tools/domains"),
            "core_belief": _ask("core belief (one sentence)"),
            "identity_statement": _ask("identity statement (one sentence)"),
            "work_mode": _ask("work mode (closed_world|bounded_research|"
                              "open_exploration)", "closed_world"),
        }
        # D-030: the main belief and its exchange rate with substitutes.
        print("--- the main belief (D-030; honest, cold, no audience) ---")
        payload["main_belief"] = _ask("main belief "
                                      "(e.g. I want to be a software "
                                      "engineer)")
        payload["main_belief_metric"] = _ask(
            "what would prove the belief is becoming real")
        payload["main_belief_current_state"] = _ask(
            "current state, honest (e.g. I am failing the course)")
        payload["substitute_activities"] = _ask_list(
            "known substitute activities (comma separated)")
        payload["substitute_budget"] = _ask(
            "substitute budget when the main belief is healthy",
            "3 hours per week")
        # IF–THEN obstacle plan (optional group, all-or-nothing).
        print("--- IF-THEN obstacle plan (enter to skip the whole group) ---")
        obstacle = _ask("likely first obstacle")
        if obstacle:
            payload["expected_obstacle"] = obstacle
            payload["if_then_response"] = _ask("planned response")
            payload["return_condition"] = _ask(
                "when to return to the main task")
        payload["emergency_policy"] = _ask(
            "what counts as an emergency (one sentence)",
            "medical, family, or system on fire")
    contract_id = s["contracts"].create_draft(
        __import__("dhriti.models", fromlist=["ContractKind"]).ContractKind.DAILY,
        today.isoformat(), payload)
    sealed = s["contracts"].seal(contract_id)
    s["ledger"].record("contract_sealed", observed_payload={
        "kind": "daily", "scope": today.isoformat()})
    print(f"sealed: {sealed['id']}")
    print(f"day window: {s['config']['day_window']['start']} .. "
          f"{s['config']['day_window']['end']} "
          f"(day_close {s['config']['day_window']['day_close']})")
    s["db"].close()


def cmd_day(args):
    home = _home(args)
    s = _open_core(home)
    clock: Clock = s["clock"]
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = clock.now_utc().astimezone(tz).date()
    day = s["days"].ensure_day(today)
    if args.sub == "status":
        win = resolve_window(today, s["config"])
        sessions = s["sessions"].sessions_for_day(day["id"])
        print(f"date         {day['date']}")
        print(f"state        {day['state']}")
        print(f"window       {win.window_start} .. {win.window_end}")
        print(f"day_close    {win.day_close}")
        print(f"targets_met  {'yes' if day['targets_met'] else 'no'}")
        print(f"sessions     {len(sessions)}")
        for sess in sessions:
            print(f"  {sess['id'][:8]} [{sess['state']}] {sess['task']}")
    s["db"].close()


def cmd_session(args):
    home = _home(args)
    if args.sub == "start":
        daemon = Daemon(home)
        try:
            sess = daemon.start_session(
                args.task, args.evidence_spec or "", args.profile,
                condition=args.condition)
            print(f"active: {sess['id']}")
            print(f"task: {args.task}")
        finally:
            daemon.release_lock()
            daemon.db.close()
        return
    s = _open_core(home)
    active = s["sessions"].active() if args.sub in ("end", "status") else None
    if args.sub == "status":
        if active:
            started = active["started_at"]
            print(f"ACTIVE {active['id'][:8]}")
            print(f"task   {active['task']}")
            print(f"since  {started}")
        else:
            print("no active session")
    elif args.sub == "end":
        if not active:
            print("no active session")
        elif args.outcome == "success":
            try:
                result = s["sessions"].end_success(active["id"], args.note)
                print(f"ended: {result['state']}")
            except Exception:
                accepted = s["sessions"].accepted_evidence_count(
                    active["id"])
                print(f"cannot end SUCCESS: accepted evidence = {accepted}")
                sys.exit(1)
        else:
            result = s["sessions"].end_incomplete(active["id"], args.note)
            print(f"ended: {result['state']}")
    s["db"].close()


def cmd_break_glass(args):
    home = _home(args)
    s = _open_core(home)
    active = s["sessions"].active()
    day = s["days"].get(s["clock"].now_utc().astimezone(
        local_tz(s["config"]["timezone"])).date())
    if args.emergency:
        # D-019: the immediate emergency path — distinct event, no toll,
        # no cooldown, still typed and still logged.
        reason = args.reason or input(
            "emergency reason (one honest sentence): ")
        result = s["break_glass"].emergency(
            reason, session_id=active["id"] if active else None,
            day_id=day["id"] if day else None,
            session_service=s["sessions"])
        print("emergency exception logged. The cold review will read it.")
        s["db"].close()
        return
    handle = s["break_glass"].initiate(
        active["id"] if active else None,
        day["id"] if day else None)
    print(f"pressed. confirm not before {handle['confirm_not_before']}")
    print(f"handle: {handle['handle']}")
    if args.yes:
        import time as _time
        wait = handle["delay_seconds"]
        print(f"waiting {wait}s ... (the toll; Ctrl-C to go back to work)")
        _time.sleep(wait)
        reason = input("typed reason (>= 20 chars): ")
    else:
        reason = args.reason or ""
    try:
        result = s["break_glass"].confirm(handle["handle"], reason,
                                          s["sessions"])
        print(f"confirmed. honored_delay={result['honored_delay']} "
              f"cooldown_until={result['cooldown_until']}")
        if result["penalty_declared"]:
            print("declared penalties (yours, from the cold state): "
                  + "; ".join(result["penalty_declared"]))
        s["ledger"].record(
            "break_glass_confirmed", session_id=active["id"] if active
            else None,
            observed_payload={"honored_delay": result["honored_delay"]},
            action_taken="session ended; cooldown set")
    except BreakGlassError as exc:
        print(f"not confirmed: {exc}")
        sys.exit(1)
    finally:
        s["db"].close()


def cmd_proof(args):
    home = _home(args)
    s = _open_core(home)
    active = s["sessions"].active()
    if args.action == "mark-unreliable":
        # Recognition mechanism 7: flag accepted-but-weak evidence in
        # cold state. The verdict stays; the flag is the signal.
        rows = s["evidence"].for_session(args.session) if args.session \
            else []
        if not rows:
            print("no evidence rows for that session")
            sys.exit(1)
        target = None
        for row in rows:
            if row["id"].startswith(args.evidence_id or ""):
                target = row
        if not target:
            print("evidence id not found (use a prefix)")
            sys.exit(1)
        detail = target.get("detail") or {}
        detail["flagged_unreliable"] = True
        detail["flag_note"] = args.note or ""
        import json as _json
        s["db"].update("evidence", target["id"], {
            "detail_json": _json.dumps(detail, default=str)})
        s["ledger"].record(
            "evidence_flagged_unreliable",
            session_id=target["session_id"],
            observed_payload={"evidence": target["id"][:8],
                              "note": (args.note or "")[:200]},
            action_taken="flag recorded; verdict unchanged")
        print(f"flagged: {target['id'][:8]} (verdict unchanged)")
        s["db"].close()
        return
    if not active:
        print("no active session — evidence belongs to a session")
        sys.exit(1)
    if args.action == "command":
        ev = s["evidence"].machine_check_command(
            active["id"], args.command, cwd=args.cwd)
    elif args.action == "file":
        ev = s["evidence"].submit_file(active["id"], args.path,
                                       note=args.note or "")
    elif args.action == "manual":
        ev = s["evidence"].submit_manual(active["id"], args.note or "")
    else:
        print("kind must be command|file|manual")
        sys.exit(1)
    print(f"[{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev.get('verdict_reason')}")
    s["ledger"].record(
        "evidence_submitted", session_id=active["id"],
        observed_payload={"kind": ev["kind"], "verdict": ev["verdict"]})
    s["db"].close()


def cmd_research(args):
    home = _home(args)
    s = _open_core(home)
    active = s["sessions"].active()
    day = s["days"].get(s["clock"].now_utc().astimezone(
        local_tz(s["config"]["timezone"])).date())
    if args.sub == "start":
        sources = [x.strip() for x in args.sources.split(",") if x.strip()]
        rp = s["research"].start(
            args.dependency, sources, args.return_condition,
            session_id=active["id"] if active else None,
            day_id=day["id"] if day else None,
            max_minutes=args.minutes)
        print(f"pass open: {rp['id']}")
        print(f"sources allowed until {rp['expires_at']}: "
              f"{', '.join(rp['sources'])}")
        print(f"return condition: {rp['return_condition']}")
        s["ledger"].record(
            "research_pass_opened",
            session_id=active["id"] if active else None,
            observed_payload={"dependency": args.dependency,
                              "sources": sources,
                              "expires_at": rp["expires_at"]},
            action_taken="sources temporarily allowed")
    elif args.sub == "return":
        rp = s["research"].return_to_task(args.pass_id, args.notes or "")
        print(f"returned: {rp['state']}")
        s["ledger"].record("research_pass_returned",
                           observed_payload={"pass": args.pass_id})
    s["db"].close()


def cmd_report(args):
    home = _home(args)
    s = _open_core(home)
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = s["clock"].now_utc().astimezone(tz).date()
    if args.scope == "week":
        monday = today - _dt.timedelta(days=today.weekday())
        report = s["aftermath"].week_report(monday.isoformat())
        stem = f"review-week-{monday.isoformat()}"
    else:
        day = s["days"].get(
            _dt.date.fromisoformat(args.date) if args.date else today)
        if not day:
            print("no such day")
            sys.exit(1)
        report = s["aftermath"].day_report(day)
        stem = f"aftermath-{day['date']}"
    out = s["aftermath"].write(
        report, home / s["config"].get("report", {}).get("dir", "reports"),
        stem)
    print(f"markdown: {out['markdown']}")
    print(f"html:     {out['html']}")
    s["db"].close()


def cmd_bootcamp(args):
    home = _home(args)
    s = _open_core(home)
    if args.sub == "start":
        bc = s["bootcamp"].start(args.days)
        print(f"bootcamp: {bc['id']}")
        print(f"planned_days: {bc['planned_days']} — no ordinary rule "
              f"changes inside the period")
        s["ledger"].record("bootcamp_started", observed_payload={
            "planned_days": args.days})
    elif args.sub == "status":
        bc = s["bootcamp"].active()
        if not bc:
            print("no active bootcamp")
        else:
            stats = s["bootcamp"].evidence_summary()
            print(f"state        {bc['state']} (taper stage "
                  f"{bc['taper_stage']})")
            print(f"days_elapsed {stats['days_elapsed']}")
            print(f"compliance   {stats['compliance_rate']}")
            print(f"proof_rate   {stats['proof_rate']}")
            print(f"breaks_7d    {stats['break_glass_7d']}")
    elif args.sub == "taper":
        rec = s["bootcamp"].compute_taper()
        print(f"recommended stage: {rec['recommended_stage']} "
              f"({rec['reason']})")
        if args.apply:
            updated = s["bootcamp"].apply_taper(
                rec["recommended_stage"], rec["reason"])
            print(f"applied. stage now {updated['taper_stage']}")
    elif args.sub == "graduate":
        bc = s["bootcamp"].graduate()
        print(f"graduated: {bc['state']} — the tool is now optional")
    s["db"].close()


def cmd_verify(args):
    home = _home(args)
    s = _open_core(home)
    result = s["ledger"].verify_chain()
    print(f"chain ok: {result['ok']} ({result['checked']} events checked)")
    if not result["ok"]:
        print(f"first bad seq: {result['first_bad_seq']} "
              f"({result['reason']})")
        sys.exit(1)
    integrity = s["db"].integrity_check()
    print(f"sqlite integrity: {'ok' if integrity else 'FAILED'}")
    head = s["ledger"].head()
    print(f"head: {head['row_hash']}")
    print("write this hash somewhere off-machine to anchor the ledger")
    s["db"].close()


def cmd_status(args):
    home = _home(args)
    s = _open_core(home)
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = s["clock"].now_utc().astimezone(tz).date()
    day = s["days"].get(today)
    active = s["sessions"].active()
    bc = s["bootcamp"].active()
    print(f"now        {s['clock'].iso()} ({today} local)")
    print(f"bootcamp   " + (f"{bc['state']} stage {bc['taper_stage']} "
                           f"since {bc['started_at']}" if bc else "none"))
    print(f"day        " + (day["state"] if day else "none"))
    if day and day["state"] == "OPEN":
        print(f"targets    {'met' if day['targets_met'] else 'unmet'}")
    print(f"session    " + (f"ACTIVE {active['id'][:8]} — {active['task']}"
                           if active else "none"))
    s["db"].close()


def cmd_events(args):
    home = _home(args)
    s = _open_core(home)
    rows = s["ledger"].events(
        event_type=args.type, session_id=args.session,
        since_utc=args.since, limit=args.limit)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        for row in rows:
            print(f"{row['seq']:>5} {row['occurred_at_utc']} "
                  f"{row['event_type']:<32} "
                  f"{row['source_adapter']:<16} "
                  f"{row['action_taken'] or '-'}")
    s["db"].close()


def cmd_adapter(args):
    home = _home(args)
    daemon = Daemon(home)
    try:
        if args.sub == "status":
            for adapter in daemon.adapters:
                info = adapter.status()
                line = f"{adapter.name:<18} {info['probe']:<14} " \
                       f"armed={info['armed']}"
                print(line)
                if args.verbose and info.get("disclosure"):
                    print(f"{'':18} -> {info['disclosure']}")
                if args.verbose and args.sub == "status":
                    m = adapter.manifest()
                    print(f"{'':18} capabilities: "
                          f"{', '.join(m['capabilities'])}")
    finally:
        daemon.release_lock()
        daemon.db.close()


def cmd_daemon(args):
    home = _home(args)
    daemon = Daemon(home, tick_seconds=args.tick)
    try:
        daemon.run()
    except KeyboardInterrupt:
        pass


def cmd_ignite(args):
    home = _home(args)
    s = _open_core(home)
    profiles = load_profiles(home)
    profile = profiles.get(args.profile)
    if not profile:
        print(f"unknown profile '{args.profile}' "
              f"(available: {', '.join(profiles)})")
        sys.exit(1)
    plan_path = home / "profiles" / f"ignite.{args.profile}.json"
    print(f"workspace ignition profile: {args.profile}")
    if plan_path.exists():
        print(f"plan file: {plan_path}")
        print("run: powershell -File launcher/ignite.ps1 "
              f"-Profile {plan_path}")
    else:
        print(f"no ignite plan found at {plan_path}")
        print("create one by copying launcher/profiles/ignite.example.json")
    s["db"].close()


def cmd_park(args):
    """The wall's mail slot: park a curiosity in one line, go back to
    work. Dispositions happen cold (`dhriti park --list`, --dispose)."""
    home = _home(args)
    s = _open_core(home)
    active = s["sessions"].active()
    day = s["days"].get(s["clock"].now_utc().astimezone(
        local_tz(s["config"]["timezone"])).date())
    if args.dispose:
        row = s["parking"].dispose(args.dispose, args.disposition,
                                    args.note or "")
        print(f"disposed [{row['disposition']}]: {row['question']}")
        if row["disposition"] == "approved":
            print("add it to the next contract's allowed_tools, cold")
        s["db"].close()
        return
    if args.list:
        rows = s["parking"].list(args.status or None)
        if not rows:
            print("(the parking lot is empty)")
        for r in rows:
            print(f"[{r['disposition']:8}] {r['created_at'][:16]} "
                  f"{r['question']}")
        s["db"].close()
        return
    if not (args.question or "").strip():
        print("park a question: dhriti park 'why does JVM do X'")
        sys.exit(1)
    row = s["parking"].park(
        args.question, origin=args.origin or "",
        session_id=active["id"] if active else None,
        day_id=day["id"] if day else None)
    print(f"parked: {row['question']}")
    print("(deferred to cold review; back to the task)")
    s["db"].close()


def cmd_review(args):
    """The cold review: the fixed question protocol (D-031, graduation
    meta-metric, evidence quality, surveillance comfort, devices)."""
    home = _home(args)
    s = _open_core(home)
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = s["clock"].now_utc().astimezone(tz).date()
    if args.scope == "week":
        monday = today - _dt.timedelta(days=today.weekday())
        scope = f"week:{monday.isoformat()}"
        day_date = None
    else:
        scope = f"day:{args.date or today.isoformat()}"
        day_date = args.date or today.isoformat()
    answered = {r["question_key"] for r in
                s["review"].answers_for(scope)}
    pending = s["parking"].pending()
    # D-047: the leisure question is conditional — asked only for a day
    # scope on which at least one declaration exists. Six fixed
    # questions always; the seventh only when it applies.
    questions = dict(REVIEW_QUESTIONS)
    if not (args.scope == "day"
            and s["leisure"].for_day(day_date or today.isoformat())):
        questions.pop("leisure_honored", None)
    print("--- cold review (no session is active) ---")
    print(f"scope: {scope}")
    if pending and args.ask_parking:
        print("\nparking lot first (cold-state dispositions):")
        for p in pending:
            mark = _ask(f"[{p['question'][:60]}] "
                        "approved|dropped|explored (enter=keep parked)")
            if mark in ("approved", "dropped", "explored"):
                s["parking"].dispose(p["id"], mark)
    for key, (prompt, _why) in questions.items():
        if key in answered and not args.redo:
            continue
        print("\n" + prompt)
        print(f"  ({_why})")
        answer = _ask("answer")
        if answer:
            s["review"].record(scope, key, answer, day_date=day_date)
    done = s["review"].answers_for(scope)
    print(f"\n{len(done)}/{len(questions)} questions answered "
          f"for {scope}")
    missing = set(questions) - {r["question_key"] for r in done}
    for key in missing:
        print(f"  unanswered: {key}")
    s["db"].close()


def cmd_digest(args):
    """The weekly digest (dead-man's switch): plain facts + chain head,
    meant to be sent to the one human who cares."""
    home = _home(args)
    s = _open_core(home)
    tz = local_tz(s["config"].get("timezone", "UTC"))
    today = s["clock"].now_utc().astimezone(tz).date()
    monday = today - _dt.timedelta(days=today.weekday())
    text = build_digest(s["db"], s["ledger"], monday.isoformat(),
                        clock=s["clock"], config=s["config"])
    out_dir = home / s["config"].get("report", {}).get("dir", "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"digest-{monday.isoformat()}.txt"
    out.write_text(text, encoding="utf-8")
    recipient = s["config"].get("digest", {}).get("recipient_label")
    s["ledger"].record(
        "digest_generated",
        observed_payload={"week": monday.isoformat(), "path": str(out)},
        action_taken="ready to send" + (
            f" to {recipient}" if recipient else " (no recipient configured)")
    )
    print(f"digest written: {out}")
    print("send it to your accountability human. If a week's digest "
          "does not arrive, that absence is the signal.")
    s["db"].close()


def cmd_token(args):
    """Bridge token management (rotate in cold state, never mid-session)."""
    home = _home(args)
    from .bridge import ensure_token
    if args.sub == "show":
        token = ensure_token(home)
        print(f"token: {token}")
        print(f"paste into extension/config.js (bridgeToken)")
        return
    if args.sub == "rotate":
        token_file = home / "bridge_token"
        if token_file.exists():
            stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            token_file.rename(Path(str(token_file) + f".old-{stamp}"))
        token = ensure_token(home)
        print(f"new token: {token}")
        print("paste into extension/config.js now (cold state), then "
              "reload the extension. Old token invalid.")


def cmd_declare(args):
    """Structured declarations (recognition mechanisms 1 & 6, D-047).
    One-way inputs with consequences, not negotiations."""
    home = _home(args)
    s = _open_core(home)
    active = s["sessions"].active()
    if args.sub == "leisure":
        # D-047: declared rest — one-way, typed, bounded. A label, not
        # a permission: it unblocks nothing and needs no session (rest
        # happens in the evening, when no session can exist). The
        # aftermath shows it next to undeclared consumption ("drift").
        activity = (args.activity or "").strip()
        if not activity:
            print("--activity is required: what rest did you choose?")
            sys.exit(1)
        tz = local_tz(s["config"].get("timezone", "UTC"))
        today = s["clock"].now_utc().astimezone(tz).date()
        try:
            row = s["leisure"].declare(
                activity, args.minutes, note=args.note or "",
                day_date=today.isoformat())
        except ValueError as exc:
            print(f"not declared: {exc}")
            sys.exit(1)
        print(f"declared rest: {row['activity']} "
              f"({row['planned_minutes']} min, ends {row['ends_at']})")
        print("(a label, not a permission — the aftermath will show it "
              "next to drift; the review asks if it held)")
        s["db"].close()
        return
    if not active:
        print("declarations belong to an active session "
              "(except leisure, which belongs to rest)")
        sys.exit(1)
    if args.sub == "dependency":
        if not (args.what or "").strip():
            print("--what is required: which obstacle revealed this "
                  "dependency")
            sys.exit(1)
        s["ledger"].record(
            "unplanned_dependency_declared",
            session_id=active["id"],
            observed_payload={
                "obstacle": args.what,
                "resource": args.resource or ""},
            action_taken="declared; reviewed in aftermath",
            telemetry_quality="OK")
        print("declared. Use `dhriti research start` for the bounded "
              "pass; the aftermath checks the return.")
    elif args.sub == "essential-tool":
        if not (args.tool or "").strip():
            print("--tool is required")
            sys.exit(1)
        s["ledger"].record(
            "essential_tool_declared",
            session_id=active["id"],
            observed_payload={"tool": args.tool,
                              "why": args.why or ""},
            action_taken="allowed for this session; aftermath checks "
                         "whether it was essential",
            telemetry_quality="OK")
        print("declared. The aftermath will check whether it was "
              "actually essential.")
    s["db"].close()


# ---------------------------------------------------------------- plumbing
def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def _ask_list(prompt: str) -> list:
    raw = _ask(prompt + " (enter for none)")
    return [x.strip() for x in raw.split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dhriti",
        description="Dhriti — local-first commitment enforcement "
                    "(the wall, not a coach)")
    parser.add_argument("--home", help="Dhriti home (default ~/.dhriti)")
    parser.add_argument("--version", action="version",
                        version=f"dhriti {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="initialize a Dhriti home")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("ritual", help="cold-state daily contract wizard")
    p.add_argument("--set", help="JSON payload (non-interactive)")
    p.set_defaults(func=cmd_ritual)

    p = sub.add_parser("day", help="day window")
    p.add_argument("sub", choices=["status"])
    p.set_defaults(func=cmd_day)

    p = sub.add_parser("session", help="work sessions")
    p.add_argument("sub", choices=["start", "end", "status"])
    p.add_argument("--task", default="")
    p.add_argument("--profile", default="coding",
                   help="task profile (coding|study|research|writing)")
    p.add_argument("--evidence-spec", default="",
                   help='JSON list e.g. [{"kind":"command"}]')
    p.add_argument("--condition", default=None,
                   help="experiment condition tag A-E")
    p.add_argument("--outcome", default="incomplete",
                   choices=["success", "incomplete"])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("break-glass", help="the only exit")
    p.add_argument("--reason", default="", help="typed reason")
    p.add_argument("--yes", action="store_true",
                   help="interactive: wait the delay, then type reason")
    p.add_argument("--emergency", action="store_true",
                   help="D-019 immediate emergency path (logged, no toll)")
    p.set_defaults(func=cmd_break_glass)

    p = sub.add_parser("proof", help="submit evidence")
    p.add_argument("action",
                   choices=["command", "file", "manual", "mark-unreliable"],
                   help="evidence kind, or mark-unreliable")
    p.add_argument("--command", default="")
    p.add_argument("--path", default="")
    p.add_argument("--note", default="")
    p.add_argument("--cwd", default=None)
    p.add_argument("--session", default=None,
                   help="session id (mark-unreliable)")
    p.add_argument("--evidence-id", dest="evidence_id", default="")
    p.set_defaults(func=cmd_proof)

    p = sub.add_parser("research", help="bounded research pass")
    p.add_argument("sub", choices=["start", "return"])
    p.add_argument("--dependency", default="")
    p.add_argument("--sources", default="",
                   help="comma-separated domains")
    p.add_argument("--return-condition", default="")
    p.add_argument("--minutes", type=int, default=None)
    p.add_argument("--pass-id", dest="pass_id", default="")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_research)

    p = sub.add_parser("report", help="aftermath / cold review")
    p.add_argument("--scope", default="day", choices=["day", "week"])
    p.add_argument("--date", default=None, help="YYYY-MM-DD")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("bootcamp", help="commitment period")
    p.add_argument("sub", choices=["start", "status", "taper", "graduate"])
    p.add_argument("--days", type=int, default=30, choices=[30, 60, 90])
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_bootcamp)

    p = sub.add_parser("verify", help="verify the ledger hash chain")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("status", help="one-glance state")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("events", help="query the event ledger")
    p.add_argument("--type", default=None)
    p.add_argument("--session", default=None)
    p.add_argument("--since", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("adapter", help="adapter status / probes")
    p.add_argument("sub", choices=["status"])
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_adapter)

    p = sub.add_parser("daemon", help="run the enforcement daemon")
    p.add_argument("--tick", type=float, default=5.0)
    p.set_defaults(func=cmd_daemon)

    p = sub.add_parser("ignite", help="workspace ignition plan")
    p.add_argument("--profile", default="coding")
    p.set_defaults(func=cmd_ignite)

    p = sub.add_parser("park", help="curiosity parking lot (one line, "
                                     "deferred to cold review)")
    p.add_argument("question", nargs="?", default="")
    p.add_argument("--origin", default="", help="where it came from")
    p.add_argument("--list", action="store_true")
    p.add_argument("--status", default=None,
                   help="filter: parked|approved|dropped|explored")
    p.add_argument("--dispose", default=None,
                   help="parking id to dispose (cold state)")
    p.add_argument("--disposition", default="",
                   choices=["", "approved", "dropped", "explored"])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_park)

    p = sub.add_parser("review", help="cold review question protocol")
    p.add_argument("--scope", default="day", choices=["day", "week"])
    p.add_argument("--date", default=None, help="YYYY-MM-DD")
    p.add_argument("--redo", action="store_true",
                   help="ask already-answered questions again")
    p.add_argument("--ask-parking", dest="ask_parking", action="store_true",
                   help="disposition parked topics first")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("digest", help="weekly digest (dead-man's switch)")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("token", help="bridge token show/rotate")
    p.add_argument("sub", choices=["show", "rotate"])
    p.set_defaults(func=cmd_token)

    p = sub.add_parser("declare", help="structured declarations "
                                        "(dependency, tool, leisure)")
    p.add_argument("sub", choices=["dependency", "essential-tool",
                                    "leisure"])
    p.add_argument("--what", default="", help="the obstacle (dependency)")
    p.add_argument("--resource", default="")
    p.add_argument("--tool", default="")
    p.add_argument("--why", default="")
    p.add_argument("--activity", default="",
                   help="the chosen rest (leisure), in your words")
    p.add_argument("--minutes", type=int, default=45,
                   help="bounded length of the declared rest (1..240)")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_declare)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except DhritiError as exc:
        print(f"error: {exc}")
        sys.exit(1)
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
