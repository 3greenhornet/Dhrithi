"""Dhriti Guard Kit -- bridge route additions (paste into dhriti/bridge.py).

Wiring: their bridge is a stdlib http.server BaseHTTPRequestHandler with
token auth and rate-limited 401s (repo bridge.py). Their send helper is
`_send(status, payload)` and routes live in do_GET / do_POST. Add ONE
dispatch line per method, inside the existing elif chain, AFTER the
token check and BEFORE the final 404 else:

    # do_GET, after the /policy branch:
    elif GuardRoutes.dispatch(self, "GET", path, None):
        return
    # do_POST, after the /proof branch (payload already parsed):
    elif GuardRoutes.dispatch(self, "POST", path, payload):
        return

GuardRoutes expects the handler object (or a namespace) to expose:
    .guard_ctx  -> SimpleNamespace(store=ContentStore,
                                   state=GuardState,
                                   emit=<event adapter>,
                                   config=<dict>)
If .guard_ctx is absent, the guard routes report 503 with an honest
"guard not configured" -- never a silent pass.

CRITICAL WIRING NOTE (v1.1 correction): the repo's ledger API is
    Ledger.record(event_type, *, source_adapter, observed,
                  inference_payload, action_taken, telemetry_quality, ...)
NOT `ledger.append(ev)`. Use the `guard_emit` adapter below -- it also
splits the house vocabulary correctly: facts (ts, hashes, counts) go to
`observed`; judgements (reason codes, P-codes, backend names) go to
`inference_payload` -- the split their ledger already enforces.

All handlers return (status:int, payload:dict) and are content-blind on
the enforcement path: text bodies (parked prompt text, hidden response
bodies) go ONLY to the ContentStore sidecar; the ledger event carries the
hash/count facts (D-075).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

try:  # drop-in: works both inside the repo and standalone in the kit
    from dhriti import chat_guard as cg
    from dhriti.content_store import ContentStore
except ImportError:  # pragma: no cover
    import chat_guard as cg  # type: ignore
    from content_store import ContentStore  # type: ignore


def _now() -> float:
    return time.time()


class GuardRoutes:
    routes: dict = {}

    @classmethod
    def route(cls, method: str, path: str):
        def deco(fn):
            cls.routes[(method, path)] = fn
            return fn
        return deco

    @classmethod
    def dispatch(cls, handler, method: str, path: str,
                 body: Optional[dict]) -> bool:
        fn = cls.routes.get((method.upper(), path))
        if fn is None:
            return False
        ctx = getattr(handler, "guard_ctx", None)
        if ctx is None:
            _send = (getattr(handler, "_send", None)
                     or getattr(handler, "_send_json"))
            _send(503, {"error": "guard not configured "
                                 "(guard_ctx missing)"})
            return True
        status, payload = fn(ctx, body or {})
        # repo's helper is _send(status, payload); _send_json is the
        # kit-standalone fallback -- dispatch works in both worlds.
        _send = (getattr(handler, "_send", None)
                 or getattr(handler, "_send_json"))
        _send(status, payload)
        return True


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

@GuardRoutes.route("GET", "/guard/state")
def guard_state(ctx, body):
    st = ctx.state
    import datetime
    cg.decay_debt(st, datetime.date.today())
    anchors = []
    if st.topic_label:
        anchors.append(st.topic_label)
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "sessions", None):
        try:
            active = ctx.daemon.sessions.active()
            if active and active.get("task_description"):
                anchors.append(active["task_description"])
        except Exception:
            pass
    return 200, {"snapshot": cg.snapshot_for_digest(st, _now()),
                 "mode": st.mode.value,
                 "sidecar_armed": st.sidecar_armed,
                 "anchors": anchors}


@GuardRoutes.route("POST", "/guard/send_event")
def guard_send_event(ctx, body):
    """The extension's send gate asks THIS before letting a prompt leave.
    body: {site, thread_id, prompt_hash, in_scope|null, sidecar_verdict|null,
           kind: 'send'|'enter_press'}"""
    st = ctx.state
    now = _now()
    decision = cg.decide(
        st, now,
        in_scope=body.get("in_scope"),
        sidecar_verdict=body.get("sidecar_verdict"),
        prompt_hash=str(body.get("prompt_hash", "")))
    for ev in decision.events:
        ctx.emit(ev)
    ctx.store.kv_set("guard_state", st.to_snapshot())
    return 200, {"action": decision.action.value,
                 "toll_seconds": decision.toll_seconds,
                 "collapse_response": decision.collapse_response,
                 "reason": decision.reason,
                 "card_lines": decision.card_lines}


@GuardRoutes.route("POST", "/guard/toll_paid")
def guard_toll_paid(ctx, body):
    st = ctx.state
    d = cg.confirm_toll_paid(st, _now(),
                             str(body.get("prompt_hash", "")))
    for ev in d.events:
        ctx.emit(ev)
    ctx.store.kv_set("guard_state", st.to_snapshot())
    return 200, {"action": d.action.value}


@GuardRoutes.route("POST", "/guard/override")
def guard_override(ctx, body):
    for ev in cg.record_override(ctx.state, _now(),
                                 str(body.get("prompt_hash", ""))):
        ctx.emit(ev)
    return 200, {"ok": True}


@GuardRoutes.route("POST", "/guard/learn_safe")
def guard_learn_safe(ctx, body):
    """Active learning loop (Section 7.6): records user-approved false-positive
    embeddings into vec_safe_anchors in ContentStore so the system adapts."""
    text = str(body.get("text", "")).strip()
    if text and hasattr(ctx, "store") and getattr(ctx.store, "_vec_enabled", False):
        try:
            from dhriti.classifier_sidecar import embedding_axis
            vec = embedding_axis.embed(text)
            if vec and len(vec) == 384:
                ctx.store.add_safe_anchor_vec(vec)
                ctx.emit({"type": "guard_safe_anchor_learned", "ts": _now(), "chars": len(text)})
        except Exception:
            pass
    return 200, {"ok": True}


@GuardRoutes.route("POST", "/guard/park")
def guard_park(ctx, body):
    """Hidden/held prompt -> parking lot item (D-071 unification).
    Text goes to the sidecar; the ledger gets the fact only."""
    st = ctx.state
    thread_id = str(body.get("thread_id", ""))
    text = str(body.get("text", ""))
    site = str(body.get("site", ""))
    content_id = ctx.store.put_text(text, kind="held_prompt",
                                    thread_id=thread_id, site=site,
                                    ttl_days=ctx.config.get(
                                        "retention", {})
                                        .get("raw_text_days", 14.0))
    ctx.emit({"type": cg.EVENT_PARKED, "ts": _now(), "site": site,
              "thread_id": thread_id,
              "prompt_hash": str(body.get("prompt_hash", "")),
              "content_ref": content_id, "sparked_by": "guard_hold"})
    for ev in cg.dispose_thread(st, thread_id, "parked", _now()):
        ctx.emit(ev)
    ctx.store.kv_set("guard_state", st.to_snapshot())
    return 200, {"parked": True, "content_ref": content_id}


@GuardRoutes.route("POST", "/guard/thread_open")
def guard_thread_open(ctx, body):
    st = ctx.state
    ok, reason, events = cg.open_thread(st, str(body.get("thread_id", "")),
                                        str(body.get("site", "")), _now())
    for ev in events:
        ctx.emit(ev)
    ctx.store.kv_set("guard_state", st.to_snapshot())
    return 200, {"allowed": ok, "reason": reason,
                 "card_lines": ([] if ok else
                                ["Dispose current thread first: park it "
                                 "or complete it."])}


@GuardRoutes.route("POST", "/guard/thread_dispose")
def guard_thread_dispose(ctx, body):
    for ev in cg.dispose_thread(ctx.state, str(body.get("thread_id", "")),
                                str(body.get("disposition", "")), _now()):
        ctx.emit(ev)
    ctx.store.kv_set("guard_state", ctx.state.to_snapshot())
    return 200, {"ok": True}


@GuardRoutes.route("POST", "/guard/adapter_health")
def guard_adapter_health(ctx, body):
    """Fail-visible blindness + DOM canary reports (D-077 / D-081)."""
    site = str(body.get("site", ""))
    ok = bool(body.get("ok", False))
    detail = str(body.get("detail", ""))
    events = []
    if not ok:
        events = cg.mark_adapter_blind(ctx.state, site, _now(), detail)
    elif body.get("canary_missing"):
        events = [{"type": cg.EVENT_DOM_CANARY_MISSING, "site": site,
                   "ts": _now(), "detail": detail}]
    for ev in events:
        ctx.emit(ev)
    return 200, {"recorded": len(events)}


@GuardRoutes.route("POST", "/guard/sidecar_armed")
def guard_sidecar_armed(ctx, body):
    """Arming gate for the optional sensor (L-6 cold-state consent event)."""
    ok = bool(body.get("ok", False))
    ctx.state.sidecar_armed = ok
    ctx.emit({"type": cg.EVENT_SIDECAR_ARMED, "ts": _now(), "ok": ok,
              "backend": str(body.get("backend", ""))})
    return 200, {"armed": ok}


# --------------------------------------------------------------------------
# Dashboard v2 Extended Bridge Routes (D-091 - D-096)
# --------------------------------------------------------------------------

_TOPIC_TICKS: list = []
_DECOMPRESSION_MGR = None


def _get_topic_ticks_path() -> Path:
    home = Path(os.environ.get("DHRITI_HOME", Path.home() / ".dhriti"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "topic_ticks.json"


def _load_topic_ticks() -> list:
    global _TOPIC_TICKS
    if not _TOPIC_TICKS:
        p = _get_topic_ticks_path()
        if p.exists():
            try:
                _TOPIC_TICKS = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                _TOPIC_TICKS = []
    return _TOPIC_TICKS


def _save_topic_ticks():
    p = _get_topic_ticks_path()
    try:
        p.write_text(json.dumps(_TOPIC_TICKS[-1000:]), encoding="utf-8")
    except Exception:
        pass


@GuardRoutes.route("GET", "/history")
def history(ctx, body):
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "db", None):
        try:
            days = ctx.daemon.db.query(
                "SELECT date, state, targets_met FROM day ORDER BY date DESC LIMIT 31")
            sessions = ctx.daemon.db.query(
                "SELECT s.task, s.state, s.ended_at, d.date AS day FROM session s "
                "JOIN day d ON s.day_id=d.id ORDER BY s.started_at DESC LIMIT 200")
            return 200, {"days": days, "sessions": sessions}
        except Exception as e:
            return 200, {"days": [], "sessions": [], "error": str(e)}
    return 200, {"days": [], "sessions": []}


@GuardRoutes.route("GET", "/topic/day")
def topic_day(ctx, body):
    from .topic_time import day_histogram
    ticks = _load_topic_ticks()
    return 200, day_histogram(ticks)


@GuardRoutes.route("POST", "/topic/tick")
def topic_tick(ctx, body):
    from .topic_time import day_histogram
    ticks = _load_topic_ticks()
    if body and isinstance(body, dict):
        ticks.append(body)
        _save_topic_ticks()
    return 200, day_histogram(ticks)


@GuardRoutes.route("GET", "/parking/timeline")
def parking_timeline(ctx, body):
    items = []
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "db", None):
        try:
            items = ctx.daemon.db.query(
                "SELECT id, text, kind, sparked_by, created_at, disposition, note FROM parking_lot "
                "ORDER BY created_at DESC LIMIT 200")
        except Exception:
            pass
    return 200, {"items": items, "open_count": sum(1 for it in items if not it.get("disposition"))}


@GuardRoutes.route("GET", "/life/list")
def life_list(ctx, body):
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "db", None):
        try:
            from .life_mirror import LifeMirrorService
            svc = LifeMirrorService(ctx.daemon.db, getattr(ctx, "config", {}), ctx.daemon.clock, ctx.daemon.ledger)
            return 200, {"items": svc.list()}
        except Exception as e:
            return 200, {"items": [], "error": str(e)}
    return 200, {"items": []}


@GuardRoutes.route("POST", "/life/declare")
def life_declare(ctx, body):
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "db", None):
        try:
            from .life_mirror import LifeMirrorService
            svc = LifeMirrorService(ctx.daemon.db, getattr(ctx, "config", {}), ctx.daemon.clock, ctx.daemon.ledger)
            res = svc.declare(body.get("label", ""), body.get("kind", "other"), body.get("minimum_version", ""))
            return 200, res
        except Exception as e:
            return 400, {"error": str(e)}
    return 200, {"id": "local", "label": body.get("label", ""), "kind": body.get("kind", "other")}


@GuardRoutes.route("POST", "/life/log")
def life_log(ctx, body):
    if hasattr(ctx, "daemon") and getattr(ctx.daemon, "db", None):
        try:
            from .life_mirror import LifeMirrorService
            svc = LifeMirrorService(ctx.daemon.db, getattr(ctx, "config", {}), ctx.daemon.clock, ctx.daemon.ledger)
            res = svc.log(body.get("id", ""))
            return 200, res
        except Exception as e:
            return 400, {"error": str(e)}
    return 200, {"logged": True}


@GuardRoutes.route("GET", "/decompression/status")
def decompression_status(ctx, body):
    global _DECOMPRESSION_MGR
    if _DECOMPRESSION_MGR is None:
        from .decompression import DecompressionManager
        cfg = getattr(ctx, "config", {}).get("decompression", {})
        _DECOMPRESSION_MGR = DecompressionManager(config=cfg)
    return 200, _DECOMPRESSION_MGR.status()


@GuardRoutes.route("POST", "/decompression/action")
def decompression_action(ctx, body):
    global _DECOMPRESSION_MGR
    if _DECOMPRESSION_MGR is None:
        from .decompression import DecompressionManager
        cfg = getattr(ctx, "config", {}).get("decompression", {})
        _DECOMPRESSION_MGR = DecompressionManager(config=cfg)
    act = body.get("action")
    if act == "start":
        return 200, _DECOMPRESSION_MGR.start()
    elif act == "eval":
        res = _DECOMPRESSION_MGR.evaluate_navigation(body.get("url", ""), body.get("category"))
        return 200, res
    return 200, _DECOMPRESSION_MGR.status()


# --------------------------------------------------------------------------
# Event adapter: guard events -> the repo's real Ledger.record signature
# --------------------------------------------------------------------------

# Guard events carry both facts and judgements. The house ledger keeps
# them apart (observed_payload vs inference_payload); this adapter does
# that split so nothing on the enforcement path blurs the line (L-7).
FACT_KEYS = ("ts", "prompt_hash", "thread_id", "site", "content_ref",
             "sparked_by", "action", "debt", "disposition", "count",
             "honored_delay")


def guard_emit(ledger, ev: dict) -> str:
    """Write one guard event through Ledger.record(...). Never raises:
    a ledger hiccup must not take the bridge thread down (the caller's
    own error vocabulary covers it -- house style, observer_poll_failed
    precedent). Returns the event_id or empty string."""
    facts = {k: v for k, v in ev.items() if k in FACT_KEYS}
    judgements = {k: v for k, v in ev.items()
                  if k not in FACT_KEYS and k != "type"}
    try:
        return ledger.record(
            str(ev.get("type", "guard_unknown")),
            source_adapter="chat_guard",
            observed=facts,
            inference_payload=judgements,
            action_taken=FACT_KEYS_ACTION.get(ev.get("type"), "recorded"),
            telemetry_quality="OK",
        )
    except Exception:
        return ""


# action_taken strings, aligned with the terse house voice:
FACT_KEYS_ACTION = {
    "guard_send_held": "send held; card shown",
    "guard_toll_paid": "toll honored; send allowed",
    "guard_parked": "held prompt parked; disposal at day_close",
    "guard_override_used": "override used; recorded",
    "guard_burst_toll": "burst toll active",
    "guard_thread_interlocked": "thread open refused; prior undisposed",
    "guard_thread_disposed": "thread disposed",
    "guard_adapter_blind": "adapter blind; recorded",
    "guard_dom_canary_missing": "DOM canary missing; selectors stale",
    "guard_e2_canary_missing": "E2 canary missing; hosts block gone",
    "guard_content_purged": "raw content purged at TTL",
    "guard_sidecar_armed": "sidecar armed (cold-state consent)",
    "guard_sensor_conflict": "sensor disagreement; recorded",
    "guard_novel_domain": "novel domain; reclassify queued",
    "guard_stack_bypass_risk": "external stack bypass risk; recorded",
    "guard_lineage_conflict": "process lineage conflict; recorded",
    "guard_e2_block_bypass_risk": "hosts entry anomaly; recorded",
}


# --------------------------------------------------------------------------
# Reference wiring for the repo's ACTUAL bridge (bridge.py, verified)
# --------------------------------------------------------------------------

WIRING_SNIPPET = '''
# --- dhriti/bridge.py, class BridgeServer (repo line ~17808) -------------
class BridgeServer:
    def __init__(self, host, port, token, state, ledger=None, on_event=None,
                 guard_ctx=None):            # NEW parameter, default None
        ...
        self.guard_ctx = guard_ctx

    def start(self):
        if self._httpd is not None:
            return
        handler = type("BoundHandler", (BridgeHandler,), {
            "state": self.state,
            "token": self.token,
            "on_event": staticmethod(self.on_event),
            "ledger": self.ledger,
            "guard_ctx": self.guard_ctx,     # NEW: pass through to handler
        })
        ...

# --- inside do_GET, after the /policy branch, before the final else ------
        elif GuardRoutes.dispatch(self, "GET", path, None):
            return

# --- inside do_POST, after the /proof branch, before the final else ------
        elif GuardRoutes.dispatch(self, "POST", path, payload):
            return

# --- at daemon start, where the BridgeServer is constructed --------------
from dhriti.content_store import ContentStore
from dhriti.chat_guard import GuardState, GuardMode
from dhriti.bridge_additions import guard_emit

store = ContentStore(os.path.join(data_dir, "guard_content.sqlite3"))
raw = store.kv_get("guard_state")
state = (GuardState.from_snapshot(raw) if raw else
         GuardState(mode=GuardMode.CHECKPOINT,
                    topic_label=contract.current_work_line,
                    prompt_budget_limit=config["research_pass"].get(
                        "prompt_budget", 15)))

server = BridgeServer(host, port, token, state=bridge_state,
                      ledger=ledger, on_event=on_bridge_event,
                      guard_ctx=SimpleNamespace(
                          store=store, state=state, config=DEFAULT_CONFIG,
                          emit=lambda ev: guard_emit(ledger, ev)))
'''

# Note on do_GET ordering: GuardRoutes.dispatch for GET must come AFTER
# the authorized() check (guard routes assume token auth is already
# enforced) and BEFORE the 404 else. Same for do_POST: dispatch AFTER the
# JSON body is parsed (guard handlers receive the parsed dict), so the
# extension's send gate gets its payload through the normal body path.
