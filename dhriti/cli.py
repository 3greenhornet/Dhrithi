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
from .mirror.store import MirrorStore
from .mirror.ingest import YouTubeIngest, import_csv, OAuthError
from .mirror.surface import SurfaceService
from .life_mirror import LifeMirrorService, KINDS as LIFE_KINDS
from .search_escape import SearchEscapeDetector
from .break_glass_friction import FrictionLadder
from .reflection_bank import ReflectionBank, EmergencyContacts
from .fsrs import FsrsShadow
from . import rituals as rituals_mod
from .lite import LiteMode
from .stack import StackProbe, NextDnsPoller


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
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, OSError):
        # no interactive stdin (headless run, piped CI, captured
        # test): the default is the honest answer, not a crash.
        # Prompts without a default return "" and their callers
        # decide what an empty answer means.
        value = ""
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
    Writes contract-<date>.json; sealing is a separate act.

    --quick (§3.13): yesterday's contract unchanged, diff shown,
    confirmed — the 20-minute shortcut for the days the full ritual
    would be skipped. It does not replace the ritual."""
    today = _local_today(ctx)
    if getattr(args, "quick", False):
        yesterday = (_dt.date.fromisoformat(today)
                     - _dt.timedelta(days=1)).isoformat()
        prior = ctx.contracts.for_day(yesterday)
        if prior is None:
            raise SystemExit(
                "--quick needs yesterday's sealed contract; none "
                f"exists for {yesterday}")
        prior_payload = prior["payload"]
        print(f"yesterday's contract ({yesterday}):")
        print(f"  line: {prior_payload.get('contract_line')}")
        print("  (diff: unchanged — that is the point of --quick)")
        if _ask("use it unchanged for today? (y/n)", "y") != "y":
            raise SystemExit("run the full ritual: dhriti ritual")
        payload = dict(prior_payload)
        out = ctx.home / f"contract-{today}.json"
        out.write_text(json.dumps(payload, indent=2,
                                  ensure_ascii=False),
                       encoding="utf-8")
        ctx.ledger.record(
            "contract_draft_written",
            observed={"date": today, "path": str(out),
                      "sha256": hashlib.sha256(
                          out.read_bytes()).hexdigest(),
                      "quick": True},
            action_taken="quick draft from yesterday (diff shown, "
                         "confirmed)")
        print(f"draft written: {out}")
        print(f"seal it cold: dhriti contract seal {out.name}")
        return
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
        # §4.4: the physical register — one sentence about the body.
        payload["body_register"] = _ask(
            "how is your body this week? (sleep, energy, movement — "
            "one sentence)")
        # §4.17: the complexity budget.
        payload["complexity_budget_minutes"] = int(_ask(
            "how much time will you spend on Dhriti this week? "
            "(minutes)", "15"))
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
            sess = daemon.start_session(args.task,
                                        next_action=getattr(args, "next", ""),
                                        blocker=getattr(args, "blocker", ""))
            print(f"active: {sess['id']}")
            print(f"task: {args.task}")
            if getattr(args, "next", ""):
                print(f"next: {args.next}")
            if getattr(args, "blocker", ""):
                print(f"blocker: {args.blocker}")
        finally:
            daemon.release_lock()
            daemon.db.close()
        return
    active = ctx.sessions.active() if args.sub in ("end", "status", "checkpoint") \
        else None
    if args.sub == "status":
        if active:
            print(f"ACTIVE {active['id'][:8]}")
            print(f"task   {active['task']}")
            print(f"since  {active['started_at']}")
            if active.get("outcome_json"):
                try:
                    cap = json.loads(active["outcome_json"]).get("resume_capsule")
                    if cap:
                        if cap.get("next_action"):
                            print(f"next   {cap['next_action']}")
                        if cap.get("blocker"):
                            print(f"block  {cap['blocker']}")
                except Exception:
                    pass
        else:
            print("no active session")
    elif args.sub == "checkpoint":
        if not active:
            print("no active session to checkpoint")
            return
        daemon = Daemon(ctx.home, config=ctx.config, clock=ctx.clock)
        try:
            sess = daemon.checkpoint_session(active["id"],
                                            next_action=getattr(args, "next", ""),
                                            blocker=getattr(args, "blocker", ""))
            print(f"checkpointed session: {sess['id'][:8]}")
            if getattr(args, "next", ""):
                print(f"next action: {args.next}")
            if getattr(args, "blocker", ""):
                print(f"blocker:     {args.blocker}")
        finally:
            daemon.release_lock()
            daemon.db.close()
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
        # §4.9: the 30-second transition — one optional prompt after
        # every finish
        if ctx.config.get("debrief", {}).get("enabled", True):
            from .rituals import DebriefService
            debrief = DebriefService(ctx.db, ctx.config, ctx.clock,
                                     ctx.ledger)
            answer = _ask("what happened? (one sentence, enter to "
                          "skip)")
            debrief.record(active["id"], answer)


def cmd_break_initiate(args, ctx):
    # §4.14: the bounded two-turn confession — OFFERED before the
    # break, never forced. The mirror is a structural echo; no LLM.
    confession_turns = None
    if ctx.config.get("confession", {}).get("enabled", False):
        from .rituals import ConfessionService
        confession = ConfessionService(ctx.db, ctx.config, ctx.clock,
                                        ctx.ledger)
        print("Before you break: name it.")
        first = _ask("You")
        if first:
            print(f"Mirror: {confession.mirror_turn(first)}")
            second = _ask("You")
            if second:
                print(f"Mirror: {confession.close_turn(second)}")
                print("[two turns. no offers. session ends.]")
                confession_turns = (first, second)
    active = ctx.sessions.active()
    handle = ctx.breaks.initiate(active["id"] if active else None)
    if confession_turns is not None:
        from .rituals import ConfessionService
        ConfessionService(ctx.db, ctx.config, ctx.clock,
                          ctx.ledger).record(
            confession_turns[0], confession_turns[1], handle["id"])
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
    elif args.sub == "clean":
        archived = ctx.parking.auto_archive_expired(max_age_days=getattr(args, "ttl", 7.0))
        print(f"DLQ TTL clean: composted {len(archived)} stale items (>={getattr(args, 'ttl', 7.0)}d).")


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
    monday_iso = (_dt.date.fromisoformat(today)
                  - _dt.timedelta(
                      days=_dt.date.fromisoformat(today).weekday())
                  ).isoformat()
    curation = ctx.review.curation_applicable(monday_iso)
    questions = ctx.review.questions_for(leisure_declared,
                                         curation_applicable=curation)
    # §3.2: the life question fires when an alternative got 0 time
    from .life_mirror import LifeMirrorService
    life = LifeMirrorService(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    untouched = life.untouched_this_week(monday_iso)
    if untouched and args.scope == "week":
        questions = list(questions) + [(
            "life_untouched",
            f"Which declared alternative got 0 time this week, and "
            f"why? (untouched: {', '.join(untouched[:3])})")]
    print("--- cold review (no session is active) ---")
    print(f"scope: {scope}")
    # §3.13: the reflection bank draw (off by default)
    if ctx.config.get("reflection_bank", {}).get("enabled", False):
        bank = ReflectionBank(ctx.db, ctx.config, ctx.clock,
                              ctx.ledger)
        question = bank.draw(monday_iso)
        if question:
            print()
            print(f"the bank asks: {question}")
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




# ---------------------------------------------------------------- v0.7.0 commands
def _mirror_dispatch(args, ctx):
    """Route the mirror subcommands to their handlers."""
    handlers = {"auth": cmd_mirror_auth, "ingest": cmd_mirror_ingest,
                "import": cmd_mirror_import,
                "surface": cmd_mirror_surface,
                "dismiss": cmd_mirror_dismiss,
                "abandon": cmd_mirror_abandon,
                "reentry": cmd_mirror_reentry,
                "explain": cmd_mirror_explain}
    args.sub = args.sub if args.sub != "reentry" else "reentry"
    handler = handlers.get(args.sub)
    if handler is None:
        raise SystemExit(f"unknown mirror subcommand: {args.sub}")
    if args.sub == "reentry":
        args.sub = args.rsub
    handler(args, ctx)


def cmd_mirror_auth(args, ctx):
    """The OAuth consent flow (PKCE). Opens the browser and listens
    on 127.0.0.1:8767 for the callback."""
    ingest = YouTubeIngest(ctx.db, ctx.config, ctx.home, ctx.clock,
                           ctx.ledger)
    redirect = f"http://127.0.0.1:8767/callback"
    try:
        url, verifier, state = ingest.build_auth_url(redirect)
    except OAuthError as exc:
        raise SystemExit(str(exc))
    print("1. open this URL in your browser:")
    print(f"   {url}")
    print("2. approve the read-only scope; the callback lands on "
          "127.0.0.1:8767")
    if args.code:
        tokens = ingest.exchange_code(args.code, verifier, redirect)
        print("refresh token stored at "
              f"{ingest.refresh_token_path} (0600)")
    else:
        print("3. paste the ?code= value from the callback URL:")
        print("   dhriti mirror auth --code <code>")
        print(f"   (state to verify: {state})")


def cmd_mirror_ingest(args, ctx):
    ingest = YouTubeIngest(ctx.db, ctx.config, ctx.home, ctx.clock,
                           ctx.ledger)
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    sources = store.sources() if not args.source else [
        s for s in store.sources()
        if s["display_name"] == args.source or
        s["source_identifier"] == args.source]
    if not sources:
        raise SystemExit("no mirror sources configured "
                         "(dhriti config set mirror... cold)")
    for source in sources:
        report = ingest.ingest(store, source)
        if report.get("ok"):
            print(f"mirror: ingested {report['ingested']} item(s) "
                  f"from {source['display_name']} "
                  f"(quota {report['quota_used']})")
        else:
            print(f"mirror: {source['display_name']} failed: "
                  f"{report.get('reason')}")


def cmd_mirror_import(args, ctx):
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    source = store.add_source("csv_import", str(Path(args.file).name),
                              f"CSV: {Path(args.file).name}")
    report = import_csv(store, source, Path(args.file))
    print(f"mirror: imported {report['ingested']} item(s) "
          f"({report['malformed']} malformed rows reported honestly)")


def cmd_mirror_surface(args, ctx):
    """The one-per-day surfacing, with recall before reveal."""
    surface = SurfaceService(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    day = ctx.days.get(_local_today(ctx))
    item = surface.surface(day, minutes=args.minutes,
                           category=args.category, state=args.state)
    if item is None:
        print("nothing to surface (not eligible, already surfaced "
              "today, or the pile is empty)")
        return
    print(surface.recall_prompt(item))
    answer = _ask("recall")
    verdict = surface.handle_recall(item, answer)
    if verdict["penalized"]:
        print("(honest: recorded. The reveal follows anyway.)")
    print()
    print(surface.reveal(item))
    choice = _ask("open / dismiss / abandon")
    if choice in ("open", "dismiss", "abandon"):
        reason = ""
        if choice == "abandon":
            reason = _ask("the abandon reason (one line, honest)")
        try:
            ctx_row = MirrorStore(
                ctx.db, ctx.config, ctx.clock,
                ctx.ledger).record_choice(item["id"], choice, reason)
        except ValueError as exc:
            raise SystemExit(str(exc))
        if choice == "open":
            context = _ask("the re-entry context (one sentence: why "
                           "are you opening this?)")
            try:
                MirrorStore(ctx.db, ctx.config, ctx.clock,
                            ctx.ledger).declare_reentry(
                                item["id"], context,
                                day_date=_local_today(ctx))
            except ValueError as exc:
                raise SystemExit(str(exc))
        print(f"recorded: {choice}")


def cmd_mirror_dismiss(args, ctx):
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    store.record_choice(args.item, "dismiss")
    print("dismissed; not a verdict")


def cmd_mirror_abandon(args, ctx):
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    try:
        store.record_choice(args.item, "abandon", args.reason or "")
    except ValueError as exc:
        raise SystemExit(str(exc))
    print("abandoned, with the reason recorded")


def cmd_mirror_reentry(args, ctx):
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    if args.sub == "declare":
        store.declare_reentry(args.item, args.context,
                              day_date=_local_today(ctx))
        print("re-entry declared")
    elif args.sub == "outcome":
        store.record_reentry_outcome(args.reentry, args.outcome)
        print(f"outcome recorded: {args.outcome}")


def cmd_mirror_explain(args, ctx):
    from .mirror.adapter import ViduraMirrorAdapter
    adapter = ViduraMirrorAdapter(ctx.config, ctx.home, db=ctx.db,
                                  clock=ctx.clock, ledger=ctx.ledger)
    result = adapter.explain(args.item)
    if "error" in result:
        raise SystemExit(result["error"])
    print(json.dumps(result, indent=2, default=str))


def cmd_life(args, ctx):
    life = LifeMirrorService(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    if args.sub == "declare":
        try:
            row = life.declare(args.label, args.kind,
                               args.minimum or "")
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"declared: '{row['label']}' ({row['kind']}) — the "
              "record will show what it got")
    elif args.sub == "list":
        for row in life.list():
            print(f"- [{row['kind']}] '{row['label']}' — "
                  f"{len(row['occurrences'])} logged, last "
                  f"{row['last_logged_at'] or 'never'}")
    elif args.sub == "log":
        try:
            row = life.log(args.id, args.date)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"logged: '{row['label']}' on "
              f"{args.date or 'today'}")
    elif args.sub == "remove":
        life.remove(args.id)
        print("removed, cold")


def cmd_search_escape(args, ctx):
    detector = SearchEscapeDetector(ctx.db, ctx.config, ctx.clock,
                                    ctx.ledger)
    since = args.since or (_dt.date.fromisoformat(_local_today(ctx))
                           - _dt.timedelta(days=7)).isoformat()
    escapes = detector.detect(since)
    if not escapes:
        print(f"no search escapes since {since}")
        return
    print(f"search escapes since {since}:")
    for row in escapes:
        print(f"  - '{row['query']}' -> {row['unopened_count']} "
              f"unopened {row['category']} item(s) "
              f"(oldest {row['oldest_unopened_days']} days)")


def cmd_stack(args, ctx):
    probe = StackProbe(ctx.config, ctx.home, ctx.clock, ctx.ledger,
                       db=ctx.db)
    if args.sub == "probe":
        for row in probe.probe_all():
            detail = f" ({row['detail']})" if row.get("detail") else ""
            print(f"{row['tool']:<14} {row['status']}{detail}")
    elif args.sub == "status":
        for row in probe.probe_all():
            print(f"{row['tool']:<14} {row['status']} — blind spots "
                  "disclosed in integrations/README.md")
    elif args.sub == "integrate":
        probe.declare_integration(args.tool, args.delegate or [])
        print(f"delegation declared: {args.tool} owns "
              f"{args.delegate}")
    elif args.sub == "import-brave":
        report = probe.import_brave(Path(args.file))
        print(f"brave import: {len(report['supported'])} rule(s) "
              f"supported, {report['unsupported']} unsupported "
              "(reported honestly)")


def cmd_barcode(args, ctx):
    ladder = FrictionLadder(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    if args.sub == "register":
        ladder.register_barcode(args.code, args.label or "")
        print("barcode registered (hash stored; the code is logged, "
              "never the location)")
    elif args.sub == "list":
        rows = ctx.db.query("SELECT id, label FROM barcode")
        for row in rows:
            print(f"- {row['id'][:8]} {row['label'] or ''}")


def cmd_gate(args, ctx):
    shadow = FsrsShadow(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    if args.sub == "status":
        status = shadow.production_gate_status()
        for key, value in status.items():
            print(f"{key:<20} {value}")
    elif args.sub == "open":
        try:
            shadow.open_production_gate()
        except ValueError as exc:
            raise SystemExit(str(exc))
        print("gate open: the mirror's ranking is now "
              "stability-based (cold-state act recorded)")


def cmd_emergency(args, ctx):
    contacts = EmergencyContacts(ctx.db, ctx.clock, ctx.ledger)
    if args.sub == "add":
        try:
            contacts.add(args.label, args.contact)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print("contact declared cold; shown on the wall when a break "
              "starts")
    elif args.sub == "list":
        for row in contacts.list():
            print(f"- {row['label']}: {row['contact']}")
    elif args.sub == "remove":
        contacts.remove(args.id)
        print("removed")


def cmd_confrontation(args, ctx):
    """§3.10: the confrontation file — generated, not sent."""
    from .review import build_confrontation_file
    today = _dt.date.fromisoformat(_local_today(ctx))
    monday = today - _dt.timedelta(days=today.weekday())
    text = build_confrontation_file(ctx.db, ctx.ledger,
                                    monday.isoformat(), ctx.config,
                                    ctx.clock)
    out_dir = ctx.home / ctx.config.get("report", {}).get("dir",
                                                          "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"confrontation-{monday.isoformat()}.txt"
    out.write_text(text, encoding="utf-8")
    ctx.ledger.record(
        "confrontation_generated",
        observed={"week": monday.isoformat(), "path": str(out)},
        action_taken="generated; NOT sent — for the user, not the "
                     "witness")
    print(f"confrontation file written: {out}")
    print("(for you. not sent. not shared.)")


def cmd_compost(args, ctx):
    from .rituals import CompostRitual
    compost = CompostRitual(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    if not compost.due() and not args.force:
        print("the compost ritual is not due yet "
              "(config compost.interval_days)")
        return
    candidates = compost.candidates()
    total = sum(len(v) for v in candidates.values())
    print(f"the compost ritual: {total} candidate(s)")
    notes = {}
    for group, rows in candidates.items():
        for row in rows:
            key = row.get("title") or row.get("question") \
                or row.get("scope_date")
            mark = _ask(f"[{group}] {str(key)[:60]} — letting-go "
                        "note (or 'skip')")
            notes[row["id"]] = mark
    counts = compost.complete(notes)
    print(f"composted: {counts['composted']}, kept: "
          f"{counts['kept']}")


def cmd_absence(args, ctx):
    from .rituals import AbsenceTest
    absence = AbsenceTest(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    try:
        absence.declare(args.date)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"the absence test is declared for {args.date}: the system "
          "will not enforce that day")


def cmd_ceremony(args, ctx):
    from .rituals import CeremonyService
    ceremony = CeremonyService(ctx.db, ctx.config, ctx.home,
                               ctx.clock, ctx.ledger)
    if not ctx.config.get("ceremony", {}).get("enabled", True):
        raise SystemExit("the ceremony is off (config ceremony."
                         "enabled)")
    print("--- the broken-contract ceremony (cold state) ---")
    for row in ceremony.eligible_dates()[:5]:
        print(f"  {row['date']} — {row['state']}")
    date = args.date or _ask("which date")
    contract = ctx.contracts.for_day(date)
    paragraph = _ask("One paragraph. What did it feel like to break "
                     "this contract?")
    try:
        result = ceremony.write(
            date, paragraph,
            contract_line=(contract or {}).get("payload", {}).get(
                "contract_line", ""),
            identity=(contract or {}).get("payload", {}).get(
                "identity_statement", ""))
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"written: {result['path']} ({result['word_count']} words; "
          "the ledger keeps the count, not the paragraph)")


def cmd_letter(args, ctx):
    from .rituals import LetterService
    letters = LetterService(ctx.db, ctx.config, ctx.home, ctx.clock,
                            ctx.ledger)
    if args.now:
        text = _ask("the letter to future-self (write it cold)")
        try:
            result = letters.write(text)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"letter written: {result['path']}")
    elif args.read:
        due = letters.due()
        if due:
            print(f"letter from {due['date']}:")
            print(due["text"])
        else:
            print("no letter is due this month")


def cmd_voice(args, ctx):
    from .rituals import VoiceArchive
    voice = VoiceArchive(ctx.db, ctx.config, ctx.home, ctx.clock,
                         ctx.ledger)
    if not ctx.config.get("voice_archive", {}).get("enabled", False) \
            and not args.typed:
        raise SystemExit("audio recording needs your setup "
                         "(voice_archive.enabled, off by default); "
                         "the typed version works: dhriti voice "
                         "--record --typed")
    text = _ask("say it (typed)")
    try:
        result = voice.record_typed(text)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"voice memo archived: {result['path']} (typed)")


def cmd_meta_review(args, ctx):
    from .rituals import MetaCommitment
    meta = MetaCommitment(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    print("--- the meta-commitment review (cold state) ---")
    print("You said you wanted to change X. Is the change:")
    print("  (a) a genuine correction")
    print("  (b) an avoidance")
    print("  (c) unclear")
    choice = _ask("a|b|c")
    try:
        result = meta.review(choice, args.change or "")
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"outcome: {result['outcome']}")


def cmd_lite(args, ctx):
    lite = LiteMode(ctx.db, ctx.home, ctx.clock, ctx.ledger)
    if args.sub == "start":
        try:
            day = lite.start(args.task, args.action, args.evidence)
        except ValueError as exc:
            raise SystemExit(str(exc))
        print(f"lite day open: {day['task']}")
        print(f"first action: {day['action']}")
    elif args.sub == "evidence":
        lite.submit_evidence(args.detail or "")
        print("evidence recorded")
    elif args.sub == "finish":
        try:
            day = lite.finish()
        except ValueError as exc:
            raise SystemExit(str(exc))
        print("one lite day done — the smallest working thing, worked")
    elif args.sub == "status" or args.sub is None:
        print(lite.report())


def cmd_anchor_offsite(args, ctx):
    """§3.14: write the current anchor to a path outside the home."""
    target = Path(args.path).expanduser()
    if target.resolve().is_relative_to(ctx.home.resolve()):
        raise SystemExit("the offsite anchor must live OUTSIDE the "
                         "dhriti home — that is the point")
    target.parent.mkdir(parents=True, exist_ok=True)
    head = ctx.ledger.head()
    anchor = ctx.ledger.write_anchor(note="offsite")
    target.write_text(
        json.dumps({"head": head["row_hash"], "seq": head["seq"],
                    "anchor": anchor["head_hash"],
                    "written_at": ctx.clock.iso()},
                   indent=2), encoding="utf-8")
    print(f"anchor written offsite: {target}")
    print(f"head: {head['row_hash']}")


def cmd_reclassify(args, ctx):
    """§3.14: additive reclassification — new categorized events are
    appended (the chain is append-only); existing rows are never
    edited."""
    from .mirror.classify_rule import classify
    store = MirrorStore(ctx.db, ctx.config, ctx.clock, ctx.ledger)
    items = ctx.db.query(
        "SELECT * FROM content_item WHERE saved_at_utc >= ?",
        (args.since + "T00:00:00Z",))
    changed = 0
    for item in items:
        verdict = classify(item["title"], item["description"] or "")
        ctx.ledger.record(
            "content_item_categorized",
            observed={"item": item["id"][:8],
                      "category": verdict["category"],
                      "confidence": verdict["confidence"],
                      "classifier": verdict["classifier"],
                      "classifier_version":
                          verdict["classifier_version"],
                      "reclassify": True},
            action_taken="additive reclassification (append-only)")
        if verdict["category"] != item["category"]:
            store.db.execute(
                "UPDATE content_item SET category=?, "
                "category_confidence=?, category_classified_at=?, "
                "category_classified_by=? WHERE id=?",
                (verdict["category"], verdict["confidence"],
                 ctx.clock.iso(), verdict["classifier_version"],
                 item["id"]))
            changed += 1
    print(f"reclassified {len(items)} item(s); {changed} changed "
          "(all events appended, none edited)")


def cmd_policy_replay(args, ctx):
    """§3.14: replay the last N weeks' events against a hypothetical
    config; reports changed decisions, applies nothing."""
    hypothetical = json.loads(Path(args.config).read_text())
    since = (ctx.clock.now_utc()
             - _dt.timedelta(weeks=args.weeks)).strftime(
                 "%Y-%m-%dT%H:%M:%SZ")
    from .policy import PolicyEngine
    engine = PolicyEngine(ctx.db, ctx.clock)
    current_snap = engine.current_snapshot() or {}
    changed = 0
    for row in ctx.ledger.events(since_utc=since):
        if row["event_type"] != "browser_navigation":
            continue
        try:
            payload = json.loads(row["observed_payload"])
        except Exception:
            continue
        url = payload.get("url", "")
        now = engine.evaluate_url(current_snap, url)
        merged = json.loads(json.dumps(ctx.config))
        _deep_merge_config(merged, hypothetical)
        engine_hyp = PolicyEngine(ctx.db, ctx.clock)
        # evaluate with the hypothetical policy domains
        hyp_snap = dict(current_snap)
        hyp_snap["blocked_domains"] = sorted(
            set(current_snap.get("blocked_domains", []))
            | set(hypothetical.get("blocked_domains", [])))
        then = engine_hyp.evaluate_url(hyp_snap, url)
        if now.action != then.action:
            changed += 1
    print(f"replay over {args.weeks} week(s): {changed} decision(s) "
          "would change under the hypothetical config")
    print("(reported, not applied — a dry run by law)")


def _deep_merge_config(base: dict, override: dict):
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) \
                and isinstance(value, dict):
            _deep_merge_config(base[key], value)
        else:
            base[key] = value


def cmd_digest_v070(args, ctx):
    """The digest with the witness protocol (§4.1/§4.6) and the
    confrontation flag (§3.10)."""
    if args.confrontation:
        cmd_confrontation(args, ctx)
        return
    from .review import build_digest_v070
    today = _dt.date.fromisoformat(_local_today(ctx))
    monday = today - _dt.timedelta(days=today.weekday())
    text = build_digest_v070(ctx.db, ctx.ledger, monday.isoformat(),
                             ctx.config, ctx.clock)
    out_dir = ctx.home / ctx.config.get("report", {}).get("dir",
                                                          "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"digest-{monday.isoformat()}.txt"
    out.write_text(text, encoding="utf-8")
    ctx.ledger.record(
        "digest_generated",
        observed={"week": monday.isoformat(), "path": str(out)},
        action_taken="ready to send (witness view)")
    print(f"digest written: {out}")


# ---------------------------------------------------------------- guard kit (D-071..D-089)
def cmd_retention(args, ctx):
    from .content_store import ContentStore
    from .retention import cmd_retention as _run_retention
    store = ContentStore(str(ctx.home / "guard_content.sqlite3"))
    ret_cfg = ctx.config.get("retention", {})
    return _run_retention(args, ret_cfg, store)


def cmd_guard_status(args, ctx):
    from .content_store import ContentStore
    from .chat_guard import GuardState, GuardMode, snapshot_for_digest
    import time
    store = ContentStore(str(ctx.home / "guard_content.sqlite3"))
    raw = store.kv_get("guard_state")
    if not raw:
        print("guard state: dormant / not initialized")
        return
    st = GuardState.from_snapshot(raw)
    snap = snapshot_for_digest(st, time.time())
    used = snap.get("prompt_budget_used", 0)
    limit = snap.get("prompt_budget_limit", 0)
    print(f"Guard Mode: {st.mode.value}")
    print(f"Prompt budget: {used} / {limit} (remaining: {max(0, limit - used)})")
    print(f"Burst active: {snap.get('bursting', False)}")
    print(f"Debt: {snap.get('debt_value', 0.0):.2f}")
    print(f"Sidecar armed: {st.sidecar_armed}")


def cmd_canary(args, ctx):
    import os
    from pathlib import Path
    from .canary import check_e2_canary, audit_hosts_entries
    canary_cfg = ctx.config.get("canary", {})
    hostname = canary_cfg.get("e2_hostname", "dhriti-canary.invalid")
    res = check_e2_canary(hostname)
    print(f"E2 canary ({hostname}): status={res.get('status')} ok={res.get('ok')} detail={res.get('detail')}")
    if getattr(args, "hosts_audit", False):
        hosts_path = (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
                      if os.name == "nt" else Path("/etc/hosts"))
        content = hosts_path.read_text(encoding="utf-8", errors="ignore") if hosts_path.exists() else ""
        report = audit_hosts_entries(content)
        findings = report.get("findings", [])
        print(f"Hosts file audit ({hosts_path}): {len(findings)} findings (bypass_risk={report.get('bypass_risk')})")
        for f in findings:
            line_str = f"line {f.get('line')}" if f.get('line') else "general"
            print(f"  [{f.get('kind')}] {line_str}: {f.get('detail')}")


def cmd_conform(args, ctx):
    from .conform import build_normative, stdlib_check, pm4py_check
    today = getattr(args, "date", None) or _local_today(ctx)
    events = ctx.ledger.events(since_utc=today)
    normalized = [{"type": e.get("event_type", ""), "ts": e.get("occurred_at_utc", "")} for e in events]
    window = ctx.config.get("day_window", {"start": "10:00", "end": "21:00", "day_close": "20:00"})
    stages = build_normative(window)
    res = stdlib_check(normalized, stages)
    print(f"Conformance report for {today}: conformant={res.get('conformant')}")
    for d in res.get("deviations", []):
        print(f"  deviation: {d['kind']} in {d.get('stage')} ({d.get('detail')})")
    if getattr(args, "pm4py", False):
        pm = pm4py_check(normalized)
        print(f"PM4Py token replay: {pm}")


def cmd_crosscheck(args, ctx):
    from .observer_crosscheck import poll_activitywatch, browser_minutes_from_aw, hourly_conflict_scan
    today = _local_today(ctx)
    nav_events = [e for e in ctx.ledger.events(since_utc=today) if "nav" in e.get("event_type", "")]
    nav_count = len(nav_events)
    aw_data = poll_activitywatch()
    browser_mins = browser_minutes_from_aw((aw_data or {}).get("events"))
    conflicts = hourly_conflict_scan([{"hour": "today", "aw_browser_minutes": browser_mins, "ext_nav_events": nav_count}])
    print(f"Sensor crosscheck: AW minutes={browser_mins:.1f}, extension navs={nav_count}")
    if conflicts:
        print(f"Sensor conflicts detected: {conflicts}")
    else:
        print("No sensor conflict detected.")


def cmd_app(args, ctx):
    """Launch the Dhriti desktop application window (Chromium app mode)."""
    from .app import launch_desktop_app
    launch_desktop_app()


def cmd_autostart(args, ctx):
    """Manage Windows boot autostart and desktop shortcut."""
    import subprocess
    action = getattr(args, "action", "status")
    script = ctx.home.parent / "launcher" / "autostart.ps1"
    if not script.exists():
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "launcher" / "autostart.ps1"
    
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Action", action.capitalize()]
    subprocess.run(cmd)


def cmd_sidecar(args, ctx):
    """Run loopback classifier sidecar (escalate-only sensor)."""
    from .bridge import ensure_token
    from .classifier_sidecar.server import serve
    token = ensure_token(ctx.home)
    port = getattr(args, "port", 8765)
    serve(port=port, token=token)


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
    p.add_argument("--quick", action="store_true",
                   help="use yesterday's contract unchanged (diff "
                        "shown, confirmed)")
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
    p.add_argument("sub", choices=["start", "end", "status", "checkpoint"])
    p.add_argument("--task", default="")
    p.add_argument("--next", default="", help="immediate next physical action (Resume Capsule)")
    p.add_argument("--blocker", default="", help="current stuck point / blocker")
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
    cl = psub.add_parser("clean", help="dead-letter queue TTL prune for stale items")
    cl.add_argument("--ttl", type=float, default=7.0, help="TTL in days (default: 7.0)")
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
    p.add_argument("--confrontation", action="store_true",
                   help="generate the confrontation file instead "
                        "(§3.10: not sent)")
    p.set_defaults(func=cmd_digest_v070)

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

    # -- v0.7.0 ---------------------------------------------------------
    m = sub.add_parser("mirror", help="the saved-content mirror")
    msub = m.add_subparsers(dest="sub", required=True)
    ma = msub.add_parser("auth", help="the OAuth consent flow")
    ma.add_argument("--code", default=None)
    mi = msub.add_parser("ingest", help="fetch from YouTube now")
    mi.add_argument("--source", default=None)
    mm = msub.add_parser("import", help="import a Takeout CSV")
    mm.add_argument("file")
    ms = msub.add_parser("surface", help="the one-per-day surfacing")
    ms.add_argument("--minutes", type=int, default=None)
    ms.add_argument("--category", default=None)
    ms.add_argument("--state", default=None)
    md = msub.add_parser("dismiss", help="dismiss the surfaced item")
    md.add_argument("item")
    mab = msub.add_parser("abandon", help="abandon, with a reason")
    mab.add_argument("item")
    mab.add_argument("--reason", default="")
    mr = msub.add_parser("reentry", help="re-entry declarations")
    mrs = mr.add_subparsers(dest="rsub", required=True)
    mrd = mrs.add_parser("declare")
    mrd.add_argument("item")
    mrd.add_argument("context")
    mro = mrs.add_parser("outcome")
    mro.add_argument("reentry")
    mro.add_argument("outcome",
                     choices=["completed", "partial", "abandoned"])
    me = msub.add_parser("explain", help="an item's full history")
    me.add_argument("item")
    m.set_defaults(func=_mirror_dispatch)

    p = sub.add_parser("life", help="declared alternatives")
    lsub = p.add_subparsers(dest="sub", required=True)
    ld = lsub.add_parser("declare")
    ld.add_argument("--label", required=True)
    ld.add_argument("--kind", required=True,
                    choices=list(LIFE_KINDS))
    ld.add_argument("--minimum", default="")
    lsub.add_parser("list")
    ll = lsub.add_parser("log")
    ll.add_argument("id")
    ll.add_argument("--date", default=None)
    lr = lsub.add_parser("remove")
    lr.add_argument("id")
    p.set_defaults(func=cmd_life)

    p = sub.add_parser("search-escape",
                       help="searches for what you already saved")
    p.add_argument("sub", choices=["report"])
    p.add_argument("--since", default=None)
    p.set_defaults(func=cmd_search_escape)

    p = sub.add_parser("stack", help="existing tool integrations")
    ssub = p.add_subparsers(dest="sub", required=True)
    ssub.add_parser("probe")
    ssub.add_parser("status")
    si = ssub.add_parser("integrate")
    si.add_argument("tool")
    si.add_argument("--delegate", nargs="*", default=[])
    sb = ssub.add_parser("import-brave")
    sb.add_argument("file")
    p.set_defaults(func=cmd_stack)

    p = sub.add_parser("barcode", help="pre-registered barcodes")
    bsub = p.add_subparsers(dest="sub", required=True)
    br = bsub.add_parser("register")
    br.add_argument("code")
    br.add_argument("--label", default="")
    bsub.add_parser("list")
    p.set_defaults(func=cmd_barcode)

    p = sub.add_parser("gate", help="the evidence gates")
    gsub = p.add_subparsers(dest="sub", required=True)
    gsub.add_parser("status")
    go = gsub.add_parser("open")
    go.add_argument("which", choices=["fsrs"])
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("emergency", help="the three humans")
    esub = p.add_subparsers(dest="sub", required=True)
    ea = esub.add_parser("add")
    ea.add_argument("label")
    ea.add_argument("contact")
    esub.add_parser("list")
    er = esub.add_parser("remove")
    er.add_argument("id")
    p.set_defaults(func=cmd_emergency)

    p = sub.add_parser("compost", help="the quarterly letting-go")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_compost)

    p = sub.add_parser("absence", help="the monthly system-off day")
    p.add_argument("date")
    p.set_defaults(func=cmd_absence)

    p = sub.add_parser("broken-contract",
                       help="the ceremony, cold")
    p.add_argument("--date", default=None)
    p.set_defaults(func=cmd_ceremony)

    p = sub.add_parser("letter", help="the 6-month letter")
    p.add_argument("--now", action="store_true")
    p.add_argument("--read", action="store_true")
    p.set_defaults(func=cmd_letter)

    p = sub.add_parser("voice", help="the voice archive")
    p.add_argument("--record", dest="record", action="store_true")
    p.add_argument("--typed", action="store_true")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("meta-review",
                       help="the meta-commitment review")
    p.add_argument("--change", default="")
    p.set_defaults(func=cmd_meta_review)

    p = sub.add_parser("lite", help="the smallest working thing")
    lisub = p.add_subparsers(dest="sub")
    ls = lisub.add_parser("start")
    ls.add_argument("task")
    ls.add_argument("action")
    ls.add_argument("--evidence", default="machine",
                    choices=["machine", "file", "manual"])
    le = lisub.add_parser("evidence")
    le.add_argument("--detail", default="")
    lisub.add_parser("finish")
    lisub.add_parser("status")
    p.set_defaults(func=cmd_lite)

    p = sub.add_parser("anchor", help="off-machine anchor")
    p.add_argument("--offsite", default=None,
                   help="write the anchor outside the home")
    p.set_defaults(func=cmd_anchor_offsite)

    p = sub.add_parser("reclassify",
                       help="additive reclassification")
    p.add_argument("--classifier", default="rules-v1")
    p.add_argument("--since", required=True)
    p.set_defaults(func=cmd_reclassify)

    p = sub.add_parser("policy-replay",
                       help="dry-run a hypothetical config")
    p.add_argument("--config", required=True)
    p.add_argument("--weeks", type=int, default=1)
    p.set_defaults(func=cmd_policy_replay)

    # Guard Kit commands (D-071..D-089)
    p = sub.add_parser("retention", help="purge expired raw text (D-075)")
    p.add_argument("--purge-raw-after", type=int, default=None)
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_retention)

    p = sub.add_parser("guard", help="conversation guard status and mode")
    gsub = p.add_subparsers(dest="guard_cmd")
    g = gsub.add_parser("status")
    g.set_defaults(func=cmd_guard_status)
    p.set_defaults(func=cmd_guard_status)

    p = sub.add_parser("canary", help="canary checks (D-081/D-087)")
    csub = p.add_subparsers(dest="canary_cmd")
    c = csub.add_parser("check")
    c.add_argument("--hosts-audit", action="store_true")
    c.set_defaults(func=cmd_canary)
    p.set_defaults(func=cmd_canary)

    p = sub.add_parser("conform", help="deviation check against normative contract (D-083)")
    p.add_argument("--date", default=None)
    p.add_argument("--pm4py", action="store_true")
    p.set_defaults(func=cmd_conform)

    p = sub.add_parser("crosscheck", help="sensor disagreement scan (D-080)")
    p.set_defaults(func=cmd_crosscheck)

    p = sub.add_parser("app", help="launch dedicated Dhriti desktop application window")
    p.set_defaults(func=cmd_app)

    p = sub.add_parser("sidecar", help="run loopback classifier sidecar (escalate-only sensor)")
    p.add_argument("--port", type=int, default=8765, help="port to bind (default: 8765)")
    p.set_defaults(func=cmd_sidecar)

    p = sub.add_parser("autostart", help="manage Windows logon autostart and desktop shortcut")
    p.add_argument("action", nargs="?", default="status", choices=["install", "status", "remove"],
                   help="install, status, or remove logon task")
    p.set_defaults(func=cmd_autostart)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx = None
    try:
        ctx = _make_ctx(args)
        # §4.21: while a lite day is open, lite is the ONLY command —
        # the point is finishing one day (the exit is 'lite finish')
        if getattr(args, "cmd", None) != "lite":
            LiteMode(ctx.db, ctx.home, ctx.clock,
                     ctx.ledger).guard_other_commands()
        args.func(args, ctx)
    except PermissionError as exc:
        print(f"refused: {exc}")
        sys.exit(1)
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
