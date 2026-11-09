"""Dhriti command line (v0.5.0 Context architecture).

Wall Principle in the CLI: during an ACTIVE session, `dhriti status`
shows state, task and elapsed time. No coaching copy, no philosophy, no
"return to task!", no shame. The user's own contract is the only voice.

Every command receives (args, ctx) where ctx is a Context — one wired
bundle of home + config + db + services, closed after the command
returns. Tests build Contexts the same way the CLI does.
"""

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path

from . import __version__
from .backup import BackupService
from .bootcamp import BootcampService
from .break_glass import BreakGlassError, BreakGlassService
from .constants import default_home, load_config
from .daemon import Daemon
from .db import Database
from .day_window import DayService, resolve_window
from .errors import DhritiError
from .evidence import EvidenceService
from .health import build_health
from .journal import JournalService
from .ledger import Ledger
from .policy import PolicyEngine
from .profiles import DEFAULT_PROFILES, load_profiles
from .research_pass import ResearchService
from .review import (ParkingLotService, ColdReviewService,
                     REVIEW_QUESTIONS, CONDITIONAL_QUESTIONS, build_digest)
from .leisure import LeisureService
from .session import SessionService
from .timeutil import Clock, RealClock, local_tz, parse_iso, to_iso
from .contract import ContractService, ContractError
from .aftermath import AftermathService
from .vidura import ViduraService


# ---------------------------------------------------------------- context
class Context:
    """One wired bundle of home + config + db + services. The CLI
    builds one per command; tests build them the same way."""

    def __init__(self, home: Path, config: dict = None,
                 clock: Clock = None, db: Database = None):
        self.home = Path(home)
        self.config = config or load_config(self.home)
        self.clock = clock or RealClock()
        self.db = db or Database(self.home / "dhriti.sqlite3")
        self.ledger = Ledger(self.db, self.clock, int(
            self.config.get("ledger", {}).get(
                "anchor_interval_events", 100)))
        self.contracts = ContractService(self.db, self.clock)
        self.days = DayService(self.db, self.config, self.clock)
        self.sessions = SessionService(self.db, self.clock)
        self.evidence = EvidenceService(self.db, self.clock,
                                        home=self.home)
        self.passes = ResearchService(self.db, self.config, self.clock,
                                  self.ledger)
        self.bootcamp = BootcampService(self.db, self.config, self.clock)
        self.breaks = BreakGlassService(
            self.db, self.config, self.clock, self.ledger)
        self.aftermath = AftermathService(
            self.db, self.config, self.clock, self.ledger)
        self.parking = ParkingLotService(self.db, self.clock, self.ledger)
        self.review = ColdReviewService(self.db, self.clock, self.ledger)
        self.leisure = LeisureService(self.db, self.clock, self.ledger)
        self.vidura = ViduraService(self.db, self.config, self.clock,
                                    self.ledger)
        self.policy = PolicyEngine(self.db, self.clock)

    def close(self):
        self.db.close()


def _home(args) -> Path:
    return Path(args.home).expanduser().resolve() if args.home \
        else default_home()


def _make_ctx(args, clock: Clock = None) -> Context:
    return Context(_home(args), clock=clock)


# ---------------------------------------------------------------- helpers
_CONTRACT_FILE_RE = re.compile(r"contract-(\d{4}-\d{2}-\d{2})")


def _parse_date_arg(value) -> str:
    if not value:
        return None
    return _dt.date.fromisoformat(str(value)).isoformat()


def _local_today(ctx: Context) -> str:
    tz = local_tz(ctx.config.get("timezone", "UTC"))
    return ctx.clock.now_utc().astimezone(tz).date().isoformat()


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def _ask_list(prompt: str) -> list:
    raw = _ask(prompt + " (enter for none)")
    return [x.strip() for x in raw.split(",") if x.strip()]


# ---------------------------------------------------------------- commands
def cmd_init(args, ctx):
    home = ctx.home
    home.mkdir(parents=True, exist_ok=True)
    config_path = home / "dhriti.config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(ctx.config, indent=2),
                               encoding="utf-8")
        print(f"config written: {config_path}")
    (home / "profiles").mkdir(exist_ok=True)
    from .bridge import ensure_token
    ensure_token(home)
    print(f"dhriti home ready: {home}")
    print(f"bridge token: {home / 'bridge_token'} "
          f"(paste into extension/config.js)")
    print("next: dhriti ritual   # write today's contract, cold")


def cmd_ritual(args, ctx):
    """The cold-state ritual. Interactive, or fully scripted via --set.
    Writes contract-<date>.json; sealing is a separate act."""
    today = _local_today(ctx)
    if args.set:
        payload = json.loads(args.set)
    else:
        print("--- cold-state ritual (no session is active) ---")
        payload = {
            "identity_statement": _ask(
                "identity statement (one sentence)"),
            "contract_line": _ask(
                "the contract line — today's goal, one line"),
        }
        print("--- the main belief (D-030; honest, cold, no audience) ---")
        payload["main_belief"] = {"label": _ask(
            "main belief (e.g. compiler practice)")}
        payload["main_belief_metric"] = _ask(
            "what would prove the belief is becoming real")
        payload["main_belief_current_state"] = _ask(
            "current state, honest (e.g. behind on the C book chapters)")
        payload["substitute_activities"] = _ask_list(
            "known substitute activities (comma separated)")
        payload["substitute_budget"] = _ask(
            "substitute budget while the belief is healthy",
            "3 hours per week")
        payload["targets"] = []
        while True:
            label = _ask("target label (enter to finish targets)")
            if not label:
                break
            ev_class = _ask(
                "evidence class (machine|file|manual)", "machine")
            target = {"label": label, "evidence": {"class": ev_class}}
            if ev_class == "machine":
                target["evidence"]["command"] = _ask("the command")
            elif ev_class == "file":
                target["evidence"]["path"] = _ask("the file path")
            payload["targets"].append(target)
        payload["profile"] = _ask("profile", "coding")
        if_then = _ask("likely first obstacle (enter to skip the group)")
        if if_then:
            payload["expected_obstacle"] = if_then
            payload["if_then_response"] = _ask("planned response")
            payload["return_condition"] = _ask("when to return")
    from .contract import validate
    validate(payload)
    out = ctx.home / f"contract-{today}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"draft written: {out}")
    print(f"seal it cold: dhriti contract seal {out.name}")
    ctx.ledger.record(
        "contract_draft_written",
        observed={"date": today, "path": str(out),
                  "sha256": hashlib.sha256(
                      out.read_bytes()).hexdigest()},
        action_taken="draft written")


def cmd_contract_write(args, ctx):
    cmd_ritual(args, ctx)


def _seal_target_date(args, ctx) -> str:
    """Bug C fix (v0.6.0 Part 1 §3): the file's own date is
    authoritative. --date is accepted only when it matches the file's
    date (or when the file name carries no date at all)."""
    explicit = _parse_date_arg(getattr(args, "date", None))
    file_match = _CONTRACT_FILE_RE.match(Path(args.file).name)
    file_date = file_match.group(1) if file_match else None

    if file_date and explicit and file_date != explicit:
        raise SystemExit(
            f"date mismatch: the file is named for {file_date} but "
            f"--date says {explicit}. The file's date is authoritative; "
            "either rename the file or drop --date.")
    if file_date:
        return file_date
    if explicit:
        return explicit
    return ctx.days.today()["date"]


def cmd_contract_seal(args, ctx):
    path = Path(args.file).expanduser()
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    date = _seal_target_date(args, ctx)
    ctx.days.ensure_day(date)
    contract = ctx.contracts.seal(date, payload)
    ctx.ledger.record(
        "contract_sealed",
        case_id=f"day-{date}",
        observed={"date": date, "file": str(path),
                  "contract_id": contract["id"]},
        action_taken="sealed cold; the day may open")
    # Mechanism 2 (v0.6.0 Part 2 §2.1): a draft that was written,
    # edited, and then sealed emits contract_revised — the fact of
    # the revision is recorded, whatever path edited the file.
    draft_events = ctx.ledger.events(event_type="contract_draft_written")
    prior_hash = None
    for ev in draft_events:
        try:
            observed = json.loads(ev["observed_payload"])
        except Exception:
            continue
        if observed.get("date") == date:
            prior_hash = observed.get("sha256")  # last wins
    if prior_hash:
        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if prior_hash != current_hash:
            ctx.ledger.record(
                "contract_revised",
                case_id=f"day-{date}",
                observed={"date": date,
                          "prior_sha256": prior_hash,
                          "final_sha256": current_hash},
                action_taken="draft revised before seal")
    print(f"sealed: {contract['id'][:8]} for {date}")
    win = resolve_window(_dt.date.fromisoformat(date), ctx.config)
    print(f"day window: {win.window_start.astimezone(local_tz(ctx.config.get('timezone', 'UTC'))):%H:%M} .. "
          f"{win.window_end.astimezone(local_tz(ctx.config.get('timezone', 'UTC'))):%H:%M} "
          f"(day_close "
          f"{win.day_close.astimezone(local_tz(ctx.config.get('timezone', 'UTC'))):%H:%M})")


def cmd_day(args, ctx):
    today = _local_today(ctx)
    day = ctx.days.ensure_day(today)
    if args.sub == "status":
        win = resolve_window(_dt.date.fromisoformat(day["date"]),
                             ctx.config)
        sessions = ctx.sessions.sessions_for_day(day["id"])
        print(f"date         {day['date']}")
        print(f"state        {day['state']}")
        print(f"window       {win.window_start} .. {win.window_end}")
        print(f"day_close    {win.day_close}")
        print(f"targets_met  {'yes' if day['targets_met'] else 'no'}")
        print(f"sessions     {len(sessions)}")
        for sess in sessions:
            print(f"  {sess['id'][:8]} [{sess['state']}] {sess['task']}")


def cmd_session(args, ctx):
    if args.sub == "start":
        daemon = Daemon(ctx.home, config=ctx.config, clock=ctx.clock)
        try:
            sess = daemon.start_session(args.task)
            print(f"active: {sess['id']}")
            print(f"task: {args.task}")
        finally:
            daemon.release_lock()
            daemon.db.close()
        return
    active = ctx.sessions.active() if args.sub in ("end", "status") \
        else None
    if args.sub == "status":
        if active:
            print(f"ACTIVE {active['id'][:8]}")
            print(f"task   {active['task']}")
            print(f"since  {active['started_at']}")
        else:
            print("no active session")
    elif args.sub == "end":
        if not active:
            print("no active session")
        elif args.outcome == "success":
            daemon = Daemon(ctx.home, config=ctx.config, clock=ctx.clock)
            try:
                result = daemon.end_session_success(active["id"],
                                                    args.note)
                print(f"ended: {result['state']}")
            except RuntimeError as exc:
                print(str(exc))
                sys.exit(1)
            finally:
                daemon.release_lock()
                daemon.db.close()
        else:
            result = ctx.sessions.finish(
                active["id"],
                __import__("dhriti.models",
                           fromlist=["SessionState"]).SessionState
                .INCOMPLETE, note=args.note)
            print(f"ended: {result['state']}")


def cmd_break_initiate(args, ctx):
    active = ctx.sessions.active()
    handle = ctx.breaks.initiate(active["id"] if active else None)
    print(f"pressed. confirm not before {handle['confirm_not_before']}")
    print(f"handle: {handle['id']}")
    if args.yes:
        ctx.clock.sleep(handle["delay_seconds"])
        print(f"waited {handle['delay_seconds']}s (the toll)")


def cmd_break_confirm(args, ctx):
    from .models import SessionState

    parked_id = args.from_parking_lot
    item = None
    if parked_id:
        item = ctx.parking.get(parked_id)
        if item is None:
            raise SystemExit(f"no parked item {parked_id}")
        if item["disposition"]:
            raise SystemExit(
                f"item is already {item['disposition']}; cannot use "
                "as break-glass justification")

    def finish(session_id):
        ctx.sessions.finish(session_id, SessionState.BREAK_GLASS)

    try:
        row = ctx.breaks.confirm(args.id, args.reason,
                                 session_finish=finish,
                                 parked_item_id=parked_id)
    except BreakGlassError as exc:
        raise SystemExit(f"not confirmed: {exc}")
    print(f"break confirmed ({row['kind']}); "
          f"honored_delay={row['honored_delay']} "
          f"cooldown_until={row['cooldown_until']}")
    if row["penalty_declared"]:
        print("declared penalties (yours, from the cold state): "
              + "; ".join(row["penalty_declared"]))
    if parked_id and item is not None:
        print(f"linked to parked item {parked_id[:8]}: "
              f"{item['question']}")


def cmd_break_emergency(args, ctx):
    from .models import SessionState
    active = ctx.sessions.active()

    def finish(session_id):
        ctx.sessions.finish(session_id, SessionState.BREAK_GLASS)

    reason = args.reason or _ask("emergency reason (one honest sentence)")
    ctx.breaks.emergency(active["id"] if active else None, reason,
                         session_finish=finish)
    print("emergency exception logged. The cold review will read it.")


def _workspace_for_session(session, ctx) -> Path:
    contract = ctx.contracts.get(session["contract_id"]) \
        if session.get("contract_id") else None
    payload = ctx.contracts.payload_of(contract)
    workspace = payload.get("workspace_dir")
    return Path(workspace).expanduser() if workspace else None


def cmd_evidence_file(args, ctx):
    active = ctx.sessions.active()
    if not active:
        print("no active session — evidence belongs to a session")
        sys.exit(1)
    ev = ctx.evidence.submit_file(
        active["id"], args.target, args.path,
        note=args.note or "",
        workspace=_workspace_for_session(active, ctx))
    print(f"[{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev.get('verdict_reason')}")
    ctx.ledger.record(
        "evidence_submitted", session_id=active["id"],
        observed={"kind": ev["kind"], "verdict": ev["verdict"]})


def cmd_evidence_machine(args, ctx):
    active = ctx.sessions.active()
    if not active:
        print("no active session — evidence belongs to a session")
        sys.exit(1)
    ev = ctx.evidence.machine_check_command(
        active["id"], args.target, args.command,
        accept_nonzero_exit=args.accept_nonzero,
        workspace=_workspace_for_session(active, ctx))
    print(f"[{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev.get('verdict_reason')}")
    ctx.ledger.record(
        "evidence_submitted", session_id=active["id"],
        observed={"kind": ev["kind"], "verdict": ev["verdict"]})


def cmd_evidence_manual(args, ctx):
    active = ctx.sessions.active()
    if not active:
        print("no active session — evidence belongs to a session")
        sys.exit(1)
    ev = ctx.evidence.submit_manual(active["id"], args.target,
                                    args.note or "")
    print(f"[{ev['verdict']}] {ev['class']}/{ev['kind']}: "
          f"{ev.get('verdict_reason')}")


def cmd_research(args, ctx):
    active = ctx.sessions.active()
    if args.sub == "open":
        if not active:
            print("research passes belong to an active session")
            sys.exit(1)
        rp = ctx.passes.open(active["id"], args.question,
                             minutes=args.minutes)
        print(f"pass open: {rp['id']}")
        print(f"question: {rp['question']}")
        print(f"sources allowed until {rp['expires_at']}: "
              f"{', '.join(rp['sources'])}")
        ctx.ledger.record(
            "research_pass_opened",
            session_id=active["id"],
            observed={"question": rp["question"],
                      "sources": rp["sources"],
                      "expires_at": rp["expires_at"]},
            action_taken="sources temporarily allowed")
    elif args.sub == "return":
        rp = ctx.passes.return_pass(args.answer,
                                    pass_id=args.pass_id or None)
        print(f"returned: {rp['state']}")
        ctx.ledger.record(
            "research_pass_returned",
            observed={"pass": rp["id"],
                      "answer_length": len(rp.get("answer") or "")},
            action_taken="back to the task; answer kept for review")


def cmd_report(args, ctx):
    today = _local_today(ctx)
    if args.scope == "week":
        monday = (_dt.date.fromisoformat(today)
                  - _dt.timedelta(
                      days=_dt.date.fromisoformat(today).weekday()))
        report = ctx.aftermath.week_report(monday.isoformat())
        stem = f"review-week-{monday.isoformat()}"
    else:
        date = args.date or today
        report = ctx.aftermath.day_report(date)
        stem = f"aftermath-{date}"
    out = ctx.aftermath.write(
        report, ctx.home / ctx.config.get("report", {}).get("dir",
                                                            "reports"),
        stem)
    print(f"markdown: {out['markdown']}")
    print(f"html:     {out['html']}")


def cmd_bootcamp(args, ctx):
    if args.sub == "start":
        bc = ctx.bootcamp.start(args.days)
        print(f"bootcamp: {bc['id']}")
        print(f"planned_days: {bc['planned_days']} — no ordinary rule "
              f"changes inside the period")
        ctx.ledger.record("bootcamp_started",
                          observed={"planned_days": args.days})
    elif args.sub == "status":
        bc = ctx.bootcamp.active()
        if not bc:
            print("no active bootcamp")
        else:
            stats = ctx.bootcamp.evidence_summary()
            print(f"state        {bc['state']} (taper stage "
                  f"{bc['taper_stage']})")
            print(f"days_elapsed {stats['days_elapsed']}")
            print(f"compliance   {stats['compliance_rate']}")
            print(f"proof_rate   {stats['proof_rate']}")
            print(f"breaks_7d    {stats['break_glass_7d']}")
    elif args.sub == "taper":
        rec = ctx.bootcamp.compute_taper()
        print(f"recommended stage: {rec['recommended_stage']} "
              f"({rec['reason']})")
        if args.apply:
            updated = ctx.bootcamp.apply_taper(
                rec["recommended_stage"], rec["reason"])
            print(f"applied. stage now {updated['taper_stage']}")
    elif args.sub == "graduate":
        bc = ctx.bootcamp.graduate()
        print(f"graduated: {bc['state']} — the tool is now optional")


def cmd_verify(args, ctx):
    result = ctx.ledger.verify_chain()
    print(f"chain ok: {result['ok']} ({result['checked']} events checked)")
    if not result["ok"]:
        print(f"first bad seq: {result['first_bad_seq']} "
              f"({result['reason']})")
        sys.exit(1)
    integrity = ctx.db.integrity_check()
    print(f"sqlite integrity: {'ok' if integrity else 'FAILED'}")
    head = ctx.ledger.head()
    print(f"head: {head['row_hash']}")
    print("write this hash somewhere off-machine to anchor the ledger")


def cmd_status(args, ctx):
    today = _local_today(ctx)
    day = ctx.days.get(today)
    active = ctx.sessions.active()
    bc = ctx.bootcamp.active()
    print(f"now        {ctx.clock.iso()} ({today} local)")
    print(f"bootcamp   " + (f"{bc['state']} stage {bc['taper_stage']} "
                           f"since {bc['started_at']}" if bc else "none"))
    print(f"day        " + (day["state"] if day else "none"))
    if day and day["state"] == "OPEN":
        print(f"targets    {'met' if day['targets_met'] else 'unmet'}")
    print(f"session    " + (f"ACTIVE {active['id'][:8]} — {active['task']}"
                           if active else "none"))


def cmd_events(args, ctx):
    rows = ctx.ledger.events(
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


def cmd_adapter(args, ctx):
    daemon = Daemon(ctx.home, config=ctx.config, clock=ctx.clock)
    try:
        if args.sub == "status":
            for adapter in daemon.adapters:
                info = adapter.status()
                line = f"{adapter.name:<18} {info['probe']:<14} " \
                       f"armed={info['armed']}"
                print(line)
                if args.verbose and info.get("disclosure"):
                    print(f"{'':18} -> {info['disclosure']}")
                if args.verbose:
                    m = adapter.manifest()
                    print(f"{'':18} capabilities: "
                          f"{', '.join(m['capabilities'])}")
    finally:
        daemon.release_lock()
        daemon.db.close()


def cmd_daemon(args, ctx):
    daemon = Daemon(ctx.home, config=ctx.config, clock=ctx.clock,
                    tick_seconds=args.tick)
    try:
        daemon.run()
    except KeyboardInterrupt:
        pass


def cmd_ignite(args, ctx):
    profiles = load_profiles(ctx.home)
    profile = profiles.get(args.profile)
    if not profile:
        print(f"unknown profile '{args.profile}' "
              f"(available: {', '.join(profiles)})")
        sys.exit(1)
    plan_path = ctx.home / "profiles" / f"ignite.{args.profile}.json"
    print(f"workspace ignition profile: {args.profile}")
    if plan_path.exists():
        print(f"plan file: {plan_path}")
        print("run: powershell -File launcher/ignite.ps1 "
              f"-Profile {plan_path}")
    else:
        print(f"no ignite plan found at {plan_path}")
        print("create one by copying launcher/profiles/ignite.example.json")


def cmd_park(args, ctx):
    active = ctx.sessions.active()
    try:
        row = ctx.parking.park(
            args.question, kind=args.kind or "question",
            source=args.source or "cli",
            sparked_by_url=args.sparked_by,
            sparked_by_event_id=args.sparked_by_event,
            session_id=active["id"] if active else None)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"parked ({row['id'][:8]}) [{row['kind']}]: "
          f"{row['question']}")


def cmd_parking(args, ctx):
    if args.sub == "list":
        for row in ctx.parking.open_items():
            spark = (f" (sparked by: {row['sparked_by_url']})"
                     if row.get("sparked_by_url") else "")
            print(f"- [{row['id'][:8]}] [{row['kind']}] "
                  f"{row['question']}{spark}")
        if not ctx.parking.open_items():
            print("(the parking lot is empty)")
    elif args.sub == "evening":
        day = args.date or _local_today(ctx)
        items = ctx.parking.surface_evening(day)
        if not items:
            print(f"nothing parked on {day}")
            return
        print(f"The evening is yours. {len(items)} parked today:")
        for row in items:
            print(f"- [{row['kind']}] {row['question']}")
    elif args.sub == "review":
        items = ctx.parking.surface_review(min_age_days=3)
        if not items:
            print("nothing older than 3 days is open")
            return
        print(f"{len(items)} older items:")
        for row in items:
            age = (ctx.clock.now_utc()
                   - parse_iso(row["created_at"])).days
            print(f"- [{row['kind']}] {row['question']} ({age} days)")


def cmd_parking_dispose(args, ctx):
    try:
        row = ctx.parking.dispose(args.id, args.disposition,
                                  note=args.note or "")
        if args.disposition == "approved" and args.to_contract:
            ctx.parking.dispose_approved_to_contract(
                args.id, args.to_contract)
            print(f"approved for {args.to_contract} research fallback")
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"{row['disposition']}: {row['question']}")
    if row["disposition"] == "approved":
        print("add it to the next contract's allowed_tools or research "
              "fallback, cold")


def cmd_review(args, ctx):
    """The cold review: the fixed question protocol."""
    today = _local_today(ctx)
    if args.scope == "week":
        monday = (_dt.date.fromisoformat(today)
                  - _dt.timedelta(
                      days=_dt.date.fromisoformat(today).weekday()))
        scope = f"week:{monday.isoformat()}"
        day_date = None
    else:
        scope = f"day:{args.date or today}"
        day_date = args.date or today
    answered = {r["question_key"] for r in
                ctx.review.answers_for(scope)}
    pending = ctx.parking.pending()
    leisure_declared = bool(
        args.scope == "day" and ctx.leisure.for_day(day_date or today))
    questions = ctx.review.questions_for(leisure_declared)
    print("--- cold review (no session is active) ---")
    print(f"scope: {scope}")
    if pending and args.ask_parking:
        print("\nparking lot first (cold-state dispositions):")
        for p in pending:
            mark = _ask(f"[{p['question'][:60]}] "
                        "approved|dropped|explored (enter=keep parked)")
            if mark in ("approved", "dropped", "explored"):
                ctx.parking.dispose(p["id"], mark)
    for key, prompt in questions:
        if key in answered and not args.redo:
            continue
        print("\n" + prompt)
        answer = _ask("answer")
        if answer:
            ctx.review.record(scope, key, answer, day_date=day_date)
    done = ctx.review.answers_for(scope)
    print(f"\n{len(done)}/{len(questions)} questions answered "
          f"for {scope}")
    missing = {k for k, _ in questions} - {r["question_key"]
                                           for r in done}
    for key in missing:
        print(f"  unanswered: {key}")


def cmd_digest(args, ctx):
    """The weekly digest (dead-man's switch)."""
    today = _local_today(ctx)
    monday = (_dt.date.fromisoformat(today)
              - _dt.timedelta(
                  days=_dt.date.fromisoformat(today).weekday()))
    text = build_digest(ctx.db, ctx.ledger, monday.isoformat(),
                        config=ctx.config, clock=ctx.clock)
    out_dir = ctx.home / ctx.config.get("report", {}).get("dir",
                                                          "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"digest-{monday.isoformat()}.txt"
    out.write_text(text, encoding="utf-8")
    recipient = ctx.config.get("digest", {}).get("recipient_label")
    ctx.ledger.record(
        "digest_generated",
        observed={"week": monday.isoformat(), "path": str(out)},
        action_taken="ready to send" + (
            f" to {recipient}" if recipient
            else " (no recipient configured)"))
    print(f"digest written: {out}")
    print("send it to your accountability human. If a week's digest "
          "does not arrive, that absence is the signal.")


def cmd_token(args, ctx):
    from .bridge import ensure_token
    if args.sub == "show":
        token = ensure_token(ctx.home)
        print(f"token: {token}")
        print("paste into extension/config.js (bridgeToken)")
    elif args.sub == "rotate":
        token_file = ctx.home / "bridge_token"
        if token_file.exists():
            stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            token_file.rename(Path(str(token_file) + f".old-{stamp}"))
        token = ensure_token(ctx.home)
        print(f"new token: {token}")
        print("paste into extension/config.js now (cold state), then "
              "reload the extension. Old token invalid.")


def cmd_declare(args, ctx):
    active = ctx.sessions.active()
    if args.sub == "leisure":
        activity = (args.activity or "").strip()
        if not activity:
            print("--activity is required: what rest did you choose?")
            sys.exit(1)
        today = _local_today(ctx)
        try:
            row = ctx.leisure.declare(
                activity, args.minutes, note=args.note or "",
                day_date=today)
        except ValueError as exc:
            print(f"not declared: {exc}")
            sys.exit(1)
        print(f"declared rest: {row['activity']} "
              f"({row['planned_minutes']} min, ends {row['ends_at']})")
        print("(a label, not a permission — the aftermath will show it "
              "next to drift; the review asks if it held)")
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
        ctx.ledger.record(
            "unplanned_dependency_declared",
            session_id=active["id"],
            observed={"obstacle": args.what,
                      "resource": args.resource or ""},
            action_taken="declared; reviewed in aftermath")
        print("declared. Use `dhriti research open` for the bounded "
              "pass; the aftermath checks the return.")
    elif args.sub == "essential-tool":
        if not (args.tool or "").strip():
            print("--tool is required")
            sys.exit(1)
        ctx.ledger.record(
            "essential_tool_declared",
            session_id=active["id"],
            observed={"tool": args.tool, "why": args.why or ""},
            action_taken="allowed for this session; aftermath checks "
                         "whether it was essential")


def cmd_vidura_ingest(args, ctx):
    """Ingest a day's returned research-pass answers as spaced items."""
    date = args.date or _local_today(ctx)
    # Bug B (v0.6.0): identity statements are shown in the day report,
    # never spaced. The ingest command records that decision honestly
    # whenever the date carries a sealed contract.
    if ctx.contracts.for_day(date) is not None:
        ctx.ledger.record(
            "vidura_identity_not_spaced",
            observed={"date": date,
                      "note": "identity statements are shown, not spaced"},
            action_taken="considered and rejected as a card (D-065)")
    items = ctx.vidura.ingest_pass_answers(date)
    if not items:
        print(f"no returned research passes on {date} to ingest")
        return
    for item in items:
        print(f"vidura item ({item['kind']}): {item['front'][:60]}")
    print(f"{len(items)} item(s) scheduled; due tomorrow")


def cmd_vidura_due(args, ctx):
    date = args.date or ctx.clock.now_utc().strftime("%Y-%m-%d")
    for item in ctx.vidura.due(date + "T23:59:59Z"):
        print(f"[{item['kind']}] {item['front']}")
        print(f"  due {item['due_at']}, reps {item['reps']}, "
              f"interval {item['interval_days']}d")
    if not ctx.vidura.due(date + "T23:59:59Z"):
        print("nothing due")


def cmd_vidura_review(args, ctx):
    row = ctx.vidura.review(args.item, args.grade)
    print(f"reviewed '{args.grade}': next due {row['due_at']} "
          f"(interval {row['interval_days']}d, "
          f"EF {row['ease_factor']})")


def cmd_health(args, ctx):
    """Operational state, one screen, facts only (toolkit #1)."""
    report = build_health(ctx.home, ctx.config, ctx.clock,
                          db=ctx.db, ledger=ctx.ledger)
    for line in report.lines:
        print(line)
    print(f"Overall: {report.overall}")
    ctx.ledger.record(
        "health_check_run",
        observed={"overall": report.overall,
                  "extension_bridge_probe":
                      report.extension_bridge_probe},
        action_taken="health checked")
    # explicit exit codes: 0 = OK, 1 = DEGRADED or BROKEN (a clean
    # run is a fact, not the absence of a failure)
    sys.exit(0 if report.overall == "OK" else 1)


def cmd_backup(args, ctx):
    service = BackupService(ctx.home, ctx.db, ctx.ledger, ctx.clock)
    dest = Path(args.dest).expanduser() if args.dest else None
    manifest = service.create(dest)
    print(f"backup: {manifest['dest']}")
    print(f"backup: chain ok before={manifest['chain_verified_before']} "
          f"after={manifest.get('chain_verified_after')} "
          f"({manifest['chain_events']} events)")
    for entry in manifest["files"]:
        print(f"backup: {entry['name']} sha256 {entry['sha256'][:16]}...")
    ctx.ledger.record(
        "backup_created",
        observed={"dest": manifest["dest"],
                  "chain_verified": manifest.get(
                      "chain_verified_after")},
        action_taken="local backup with manifest")


def cmd_journal(args, ctx):
    service = JournalService(ctx.home, ctx.clock)
    try:
        if args.sub == "add":
            row = service.add(args.text)
            ctx.ledger.record(
                "journal_entry_added",
                observed={"at": row["at_utc"]},
                action_taken="fact recorded; content stays in the "
                             "journal")
            print(f"journal entry added at {row['at_utc']}")
            print(f"stored in {service.path} (separate from the ledger)")
        elif args.sub == "list":
            rows = service.list(args.since)
            for row in rows:
                print(f"{row['at_utc']}  {row['text']}")
            if not rows:
                print("(no entries)")
        elif args.sub == "export":
            print(service.export())
    finally:
        service.close()


def cmd_explain(args, ctx):
    needle = (args.what or "").strip()
    if not needle:
        print("explain what? an event id prefix, 'chain', or a date")
        sys.exit(1)
    if needle == "chain":
        result = ctx.ledger.verify_chain()
        print(f"chain ok: {result['ok']} ({result['checked']} events)")
        print(f"head: {ctx.ledger.head()['row_hash']}")
        return
    rows = ctx.ledger.events()
    matched = [r for r in rows if r["event_id"].startswith(needle)
               or (r["session_id"] or "").startswith(needle)]
    if not matched:
        print(f"no events match {needle!r}")
        sys.exit(1)
    for row in matched[-10:]:
        print(f"{row['seq']:>5} {row['occurred_at_utc']} "
              f"{row['event_type']:<28} "
              f"{row['observed_payload'][:160]}")
    print(f"{len(matched)} event(s); newest shown; "
          "every number in the reports derives from these rows")


def cmd_config(args, ctx):
    path = ctx.home / "dhriti.config.json"
    if args.sub == "show":
        print(json.dumps(ctx.config, indent=2))
    elif args.sub == "validate":
        problems = []
        if not isinstance(ctx.config.get("day_window", {})
                          .get("start"), str):
            problems.append("day_window.start missing")
        if not (ctx.config.get("enforcement", {})
                .get("required_adapters")):
            problems.append("enforcement.required_adapters empty")
        if problems:
            for p in problems:
                print(f"[warn] {p}")
            sys.exit(1)
        print("[ok  ] config valid")
    elif args.sub == "get":
        node = ctx.config
        for part in args.key.split("."):
            if not isinstance(node, dict) or part not in node:
                print(f"no such key: {args.key}")
                sys.exit(1)
            node = node[part]
        print(json.dumps(node, indent=2, default=str))
    elif args.sub == "set":
        # cold-state act: refuse while the daemon holds the lock
        if (ctx.home / "daemon.lock").exists():
            print("refused: the daemon holds the lock. Stop it first — "
                  "config changes apply at next start (L-3/D-050).")
            sys.exit(1)
        cfg = json.loads(path.read_text(encoding="utf-8")) \
            if path.exists() else {}
        node = cfg
        parts = args.key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        try:
            node[parts[-1]] = json.loads(args.value)
        except json.JSONDecodeError:
            node[parts[-1]] = args.value
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"set {args.key} (applies at next daemon start)")


# ---------------------------------------------------------------- plumbing
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

    p = sub.add_parser("contract", help="write / seal the contract")
    csub = p.add_subparsers(dest="sub", required=True)
    w = csub.add_parser("write", help="write today's contract file")
    w.add_argument("--set", help="JSON payload (non-interactive)")
    w.set_defaults(func=cmd_contract_write)
    s = csub.add_parser("seal", help="seal a contract file, cold")
    s.add_argument("file")
    s.add_argument("--date", default=None, help="YYYY-MM-DD")
    s.set_defaults(func=cmd_contract_seal)

    p = sub.add_parser("day", help="day window")
    p.add_argument("sub", choices=["status"])
    p.set_defaults(func=cmd_day)

    p = sub.add_parser("session", help="work sessions")
    p.add_argument("sub", choices=["start", "end", "status"])
    p.add_argument("--task", default="")
    p.add_argument("--profile", default="coding")
    p.add_argument("--condition", default=None,
                   help="experiment condition tag A-E")
    p.add_argument("--outcome", default="incomplete",
                   choices=["success", "incomplete"])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("break-glass", help="the only exit")
    bsub = p.add_subparsers(dest="sub")
    bi = bsub.add_parser("initiate", help="press; get the handle")
    bi.add_argument("--yes", action="store_true",
                    help="wait the delay interactively")
    bi.set_defaults(func=cmd_break_initiate)
    bc = bsub.add_parser("confirm", help="confirm with a typed reason")
    bc.add_argument("id")
    bc.add_argument("--reason", required=True)
    bc.add_argument("--from-parking-lot", dest="from_parking_lot",
                    default=None,
                    help="parked item id this break is for")
    bc.set_defaults(func=cmd_break_confirm)
    be = bsub.add_parser("emergency", help="D-019 immediate path")
    be.add_argument("--reason", default="")
    be.set_defaults(func=cmd_break_emergency)

    p = sub.add_parser("evidence", help="submit proof")
    esub = p.add_subparsers(dest="sub", required=True)
    ef = esub.add_parser("file", help="submit a file (hashed)")
    ef.add_argument("--target", required=True,
                    help="the contract target label this proves")
    ef.add_argument("path")
    ef.add_argument("--note", default="")
    ef.set_defaults(func=cmd_evidence_file)
    em = esub.add_parser("machine", help="run a command; exit code is "
                                         "the fact")
    em.add_argument("--target", required=True)
    em.add_argument("--accept-nonzero", dest="accept_nonzero",
                    action="store_true",
                    help="documented-failure proof counts")
    em.add_argument("command")
    em.set_defaults(func=cmd_evidence_machine)
    eu = esub.add_parser("manual", help="a claim, kept for review")
    eu.add_argument("--target", required=True)
    eu.add_argument("--note", default="")
    eu.set_defaults(func=cmd_evidence_manual)

    p = sub.add_parser("research", help="bounded, topic-locked pass")
    p.add_argument("sub", choices=["open", "return"])
    p.add_argument("--question", default="")
    p.add_argument("--minutes", type=int, default=None)
    p.add_argument("--pass-id", dest="pass_id", default="")
    p.add_argument("--answer", default="")
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

    p = sub.add_parser("park", help="curiosity parking lot (one line)")
    p.add_argument("question", nargs="?", default="")
    p.add_argument("--kind", default="question",
                   choices=["question", "resource", "desire",
                            "association"])
    p.add_argument("--source", default=None,
                   help="where it came from")
    p.add_argument("--sparked-by", dest="sparked_by", default=None,
                   help="URL that sparked this")
    p.add_argument("--sparked-by-event", dest="sparked_by_event",
                   default=None, help="event id that sparked this")
    p.set_defaults(func=cmd_park)

    p = sub.add_parser("parking", help="the parking lot, cold")
    psub = p.add_subparsers(dest="sub", required=True)
    psub.add_parser("list")
    ev = psub.add_parser("evening",
                         help="surface today's parked items (earned)")
    ev.add_argument("--date", default=None)
    rv = psub.add_parser("review",
                         help="surface older open items (cold)")
    p.set_defaults(func=cmd_parking)

    p = sub.add_parser("parking-dispose", help="dispose a parked item")
    p.add_argument("id")
    p.add_argument("disposition",
                   choices=["approved", "dropped", "explored"])
    p.add_argument("--note", default="")
    p.add_argument("--to-contract", dest="to_contract", default=None,
                   help="YYYY-MM-DD: the contract day this becomes a "
                        "research fallback for")
    p.set_defaults(func=cmd_parking_dispose)

    p = sub.add_parser("review", help="cold review question protocol")
    p.add_argument("--scope", default="day", choices=["day", "week"])
    p.add_argument("--date", default=None, help="YYYY-MM-DD")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--ask-parking", dest="ask_parking",
                   action="store_true")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("digest", help="weekly digest (dead-man's switch)")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("token", help="bridge token show/rotate")
    p.add_argument("sub", choices=["show", "rotate"])
    p.set_defaults(func=cmd_token)

    p = sub.add_parser("declare", help="structured declarations")
    p.add_argument("sub", choices=["dependency", "essential-tool",
                                   "leisure"])
    p.add_argument("--what", default="")
    p.add_argument("--resource", default="")
    p.add_argument("--tool", default="")
    p.add_argument("--why", default="")
    p.add_argument("--activity", default="")
    p.add_argument("--minutes", type=int, default=45)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_declare)

    p = sub.add_parser("vidura", help="spaced review of your answers")
    vsub = p.add_subparsers(dest="sub", required=True)
    vi = vsub.add_parser("ingest", help="ingest a day's pass answers")
    vi.add_argument("--date", default=None, help="YYYY-MM-DD")
    vi.set_defaults(func=cmd_vidura_ingest)
    vd = vsub.add_parser("due", help="items due")
    vd.add_argument("--date", default=None)
    vd.set_defaults(func=cmd_vidura_due)
    vr = vsub.add_parser("review", help="review an item")
    vr.add_argument("item")
    vr.add_argument("grade", choices=["again", "hard", "good", "easy"])
    vr.set_defaults(func=cmd_vidura_review)

    p = sub.add_parser("health", help="operational state, one screen")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("backup", help="local backup with manifest")
    p.add_argument("--dest", default=None)
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("journal", help="experimenter's log (separate DB)")
    p.add_argument("sub", choices=["add", "list", "export"])
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--since", default=None)
    p.set_defaults(func=cmd_journal)

    p = sub.add_parser("explain", help="trace a number to its events")
    p.add_argument("what", nargs="?", default="")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("config", help="config validate/show/get/set")
    p.add_argument("sub", choices=["validate", "show", "get", "set"])
    p.add_argument("key", nargs="?", default="")
    p.add_argument("value", nargs="?", default="")
    p.set_defaults(func=cmd_config)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx = None
    try:
        ctx = _make_ctx(args)
        args.func(args, ctx)
    except DhritiError as exc:
        print(f"error: {exc}")
        sys.exit(1)
    except ContractError as exc:
        print(f"error: {exc}")
        sys.exit(1)
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        sys.exit(1)
    finally:
        if ctx is not None:
            ctx.close()


if __name__ == "__main__":
    main()
