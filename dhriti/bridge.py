"""The local bridge: token-authenticated HTTP API between the Dhriti Wall
extension and the daemon (127.0.0.1 only).

Endpoints (extension-facing, deliberately tiny):
  GET  /status   daemon/day/session snapshot for the badge state
  GET  /policy   current extension rules (fail-safe TTL included)
  POST /events   normalized navigation events from the browser
  POST /proof    submit evidence JSON from the browser (optional)

Security posture (docs/ENFORCEMENT_LEVELS.md):
  * binds 127.0.0.1 only — nothing reachable from the network;
  * every request needs X-Dhriti-Token matching <home>/bridge_token;
  * no CORS wildcard for data; the extension supplies the token from
    its config.js. A local attacker with filesystem access is outside
    the threat model (they own the machine — tamper-evident, not
    tamper-proof).

The token file is created at init with 0600 permissions.
"""

import base64
import json
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .errors import BridgeError
from .bridge_additions import GuardRoutes


def ensure_token(home: Path) -> str:
    """Create the bridge token once; return it. Keep it out of Git."""
    token_file = home / "bridge_token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token, encoding="utf-8")
    try:
        token_file.chmod(0o600)
    except Exception:
        pass  # Windows ACLs differ; best effort on POSIX
    return token


class BridgeState:
    """Shared, lock-guarded state the daemon publishes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._policy = None       # current extension policy (dict)
        self._status = {"daemon": "starting"}

    def publish_policy(self, policy: dict):
        with self._lock:
            self._policy = policy

    def publish_status(self, status: dict):
        with self._lock:
            self._status = status

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(
                {"status": self._status, "policy": self._policy}))


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "DhritiBridge/0.1"
    protocol_version = "HTTP/1.1"

    # injected by BridgeServer
    state: BridgeState = None
    token: str = ""
    on_event = None      # callable(ledger, payload dict) -> None
    ledger = None
    _last_reject_logged = 0.0   # rate-limit token-rejection events

    def log_message(self, fmt, *args):  # silence; the ledger is the log
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, code: int, body: bytes, content_type: str = "text/html"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        path = urlparse(self.path).path
        token_param = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        ok = (self.headers.get("X-Dhriti-Token") == self.token) or (token_param == self.token)
        dashboard_paths = (
            "/", "/dashboard", "/dashboard/",
            "/style.css", "/dashboard/style.css",
            "/app.js", "/dashboard/app.js",
            "/physics_chimes.js", "/dashboard/physics_chimes.js",
            "/audio_synth.js", "/dashboard/audio_synth.js",
            "/popup.css", "/popup.js", "/popup.html", "/extension",
            "/api/gallery/images", "/api/gallery/upload", "/api/gallery/delete"
        )
        if (ok or self.path.startswith("/healthz") or path in dashboard_paths
                or path.startswith("/gallery/") or path.startswith("/dashboard/gallery/")
                or path.startswith("/api/vidura/") or path.startswith("/ledger/") or path.startswith("/stats/")
                or path.startswith("/api/defense/") or path.startswith("/api/oa/") or path.startswith("/api/capability/")
                or path in ("/targets", "/ritual/state", "/ritual/seal", "/targets/claim", "/targets/verify_recall",
                            "/api/check_query", "/api/safe_anchor", "/api/vision/classify", "/pivot/declare", "/pivot/confirm", "/lockdown/engage", "/api/task/poison")):
            return True
        # A bad token means either a stale extension config or a local
        # process probing the bridge (plan D-025: every client connection
        # is observable). Rate-limited to one chain event per minute so a
        # probe flood cannot bloat the ledger.
        import time as _time
        now = _time.monotonic()
        if now - type(self)._last_reject_logged >= 60.0 \
                and self.ledger is not None:
            type(self)._last_reject_logged = now
            self.ledger.record(
                "bridge_token_rejected",
                source_adapter="bridge",
                observed={
                    "client": self.client_address[0],
                    "path": self.path[:100]},
                action_taken="401 returned; connection logged",
                telemetry_quality="OK")
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send(200, {"ok": True})
            return

        dashboard_dir = Path(__file__).parent.parent / "dashboard"
        extension_dir = Path(__file__).parent.parent / "extension"

        if path in ("/", "/dashboard", "/dashboard/"):
            index_file = dashboard_dir / "index.html"
            if index_file.exists():
                self._send_bytes(200, index_file.read_bytes(), "text/html; charset=utf-8")
                return
            popup_file = extension_dir / "popup.html"
            if popup_file.exists():
                self._send_bytes(200, popup_file.read_bytes(), "text/html; charset=utf-8")
                return
        elif path in ("/style.css", "/dashboard/style.css"):
            css_file = dashboard_dir / "style.css"
            if css_file.exists():
                self._send_bytes(200, css_file.read_bytes(), "text/css; charset=utf-8")
                return
        elif path in ("/app.js", "/dashboard/app.js"):
            js_file = dashboard_dir / "app.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
                return
        elif path in ("/physics_chimes.js", "/dashboard/physics_chimes.js"):
            js_file = dashboard_dir / "physics_chimes.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
                return
        elif path in ("/audio_synth.js", "/dashboard/audio_synth.js"):
            js_file = dashboard_dir / "audio_synth.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
                return
        elif path in ("/thought_bubbles.js", "/dashboard/thought_bubbles.js"):
            js_file = dashboard_dir / "thought_bubbles.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
                return
        elif path.endswith((".ttf", ".woff2", ".woff", ".otf")):
            clean_font = Path(path).name
            font_file = dashboard_dir / clean_font
            if font_file.exists() and font_file.is_file():
                ext = font_file.suffix.lower()
                mimes = {
                    ".ttf": "font/ttf",
                    ".woff2": "font/woff2",
                    ".woff": "font/woff",
                    ".otf": "font/otf"
                }
                self._send_bytes(200, font_file.read_bytes(), mimes.get(ext, "font/ttf"))
                return
        elif path in ("/popup.html", "/extension"):
            popup_file = extension_dir / "popup.html"
            if popup_file.exists():
                self._send_bytes(200, popup_file.read_bytes(), "text/html; charset=utf-8")
                return
        elif path == "/popup.css":
            css_file = extension_dir / "popup.css"
            if css_file.exists():
                self._send_bytes(200, css_file.read_bytes(), "text/css; charset=utf-8")
                return
        elif path == "/popup.js":
            js_file = extension_dir / "popup.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
                return
        elif path.startswith("/gallery/") or path.startswith("/dashboard/gallery/"):
            rel_name = path.replace("/dashboard/gallery/", "").replace("/gallery/", "")
            clean_name = Path(rel_name).name
            gallery_file = dashboard_dir / "gallery" / clean_name
            if gallery_file.exists() and gallery_file.is_file():
                ext = gallery_file.suffix.lower()
                mimes = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp",
                    ".gif": "image/gif", ".svg": "image/svg+xml"
                }
                self._send_bytes(200, gallery_file.read_bytes(), mimes.get(ext, "application/octet-stream"))
                return
            self._send(404, {"error": "image not found"})
            return
        elif path == "/api/gallery/images":
            gallery_dir = dashboard_dir / "gallery"
            gallery_dir.mkdir(parents=True, exist_ok=True)
            images = []
            for f in sorted(gallery_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
                    images.append({
                        "id": f"local-{f.stem}",
                        "title": f.stem.replace("_", " ").replace("-", " ").title(),
                        "filename": f.name,
                        "url": f"/gallery/{f.name}",
                        "size": f.stat().st_size
                    })
            self._send(200, {"images": images})
            return

        if not self._authorized():
            self._send(401, {"error": "bad or missing X-Dhriti-Token"})
            return
        snap = self.state.snapshot()
        if path == "/status":
            self._send(200, snap["status"] or {"daemon": "running"})
        elif path == "/session/topic":
            self._send(200, snap["status"].get("session_topic")
                       if snap["status"].get("session_topic")
                       else {"topic": None, "session_id": None,
                             "expires_at": None})
        elif path == "/policy":
            self._send(200, snap["policy"] or {
                "enforce": False, "reason": "no active policy (dormant)"})
        elif path == "/api/vidura/search":
            qs = parse_qs(urlparse(self.path).query)
            q = qs.get("q", [""])[0]
            limit = int(qs.get("limit", [20])[0])
            try:
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                corpus = ViduraCorpus(DB_VIDURA_PATH)
                results = corpus.search(q, limit=limit)
                self._send(200, {"ok": True, "query": q, "items": results, "count": len(results)})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/vidura/surface":
            try:
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                from .vidura_surface import ViduraSurfaceService
                corpus = ViduraCorpus(DB_VIDURA_PATH)
                svc = ViduraSurfaceService(corpus)
                item = svc.suggest_daily_item()
                if not item:
                    self._send(200, {"ok": True, "card": None, "message": "no items to surface"})
                else:
                    card = svc.prepare_recall_card(item)
                    self._send(200, {"ok": True, "card": card})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/vidura/facets":
            try:
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                from .vidura_facets import FacetEngine
                corpus = ViduraCorpus(DB_VIDURA_PATH)
                engine = FacetEngine(corpus)
                breakdown = engine.get_facet_breakdown()
                self._send(200, {"ok": True, "facets": breakdown})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/vidura/instruments":
            try:
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                from .vidura_facets import FacetEngine
                corpus = ViduraCorpus(DB_VIDURA_PATH)
                engine = FacetEngine(corpus)
                instruments = engine.get_instruments()
                self._send(200, {"ok": True, "instruments": instruments, "count": len(instruments)})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/targets":
            try:
                from .constants import DB_PATH
                from .db import Database
                import datetime as _dt
                today = _dt.date.today().isoformat()
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                row = db.query_one(
                    "SELECT payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
                    (today,)
                )
                contract_targets = []
                contract_line = ""
                sealed = False
                if row:
                    sealed = True
                    payload = json.loads(row["payload_json"])
                    contract_line = payload.get("contract_line", "")
                    contract_targets = payload.get("targets", [])

                    # Enrich with claims from event audit trail
                    try:
                        ev_rows = db.query(
                            "SELECT observed_payload FROM event WHERE date(occurred_at_utc)=? AND event_type IN ('learning_proof_verified', 'target_claimed')",
                            (today,)
                        )
                        claimed_map = {}
                        for er in ev_rows:
                            try:
                                op = json.loads(er["observed_payload"])
                                tid = str(op.get("target_id", ""))
                                if tid:
                                    claimed_map[tid] = op
                            except Exception:
                                pass
                        for t in contract_targets:
                            tid = str(t.get("id", ""))
                            if tid in claimed_map:
                                t["claimed"] = True
                                t["proof"] = f"sha256:{claimed_map[tid].get('proof_hash', 'verified')[:16]}"
                    except Exception:
                        pass

                # UNION active pivots from day_pivot (F1)
                pivot_targets = []
                remaining_pivots = 3
                try:
                    from .pivot import PivotService
                    pivot_svc = PivotService(db)
                    active_pivots = pivot_svc.list_active_pivots(today)
                    remaining_pivots = pivot_svc.remaining_today(today)
                    for p in active_pivots:
                        pivot_targets.append({
                            "id": p["id"],
                            "label": p["topic"],
                            "kind": "pivot",
                            "is_pivot": True,
                            "expires_at": p["expires_at"],
                            "evidence": {"class": "learning"}
                        })
                except Exception:
                    pass

                all_targets = contract_targets + pivot_targets
                self._send(200, {
                    "ok": True,
                    "sealed": sealed,
                    "contract_line": contract_line,
                    "targets": all_targets,
                    "pivots_remaining": remaining_pivots
                })
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/ritual/state":
            try:
                from .constants import DB_PATH
                from .db import Database
                import datetime as _dt
                today = _dt.date.today().isoformat()
                yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                row_today = db.query_one(
                    "SELECT payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
                    (today,)
                )
                row_yest = db.query_one(
                    "SELECT payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
                    (yesterday,)
                )
                yest_payload = json.loads(row_yest["payload_json"]) if row_yest else None
                if row_today:
                    payload = json.loads(row_today["payload_json"])
                    self._send(200, {
                        "ok": True,
                        "date": today,
                        "local_date": today,
                        "sealed": True,
                        "contract_line": payload.get("contract_line", ""),
                        "targets": payload.get("targets", []),
                        "yesterday": yest_payload
                    })
                else:
                    self._send(200, {
                        "ok": True,
                        "date": today,
                        "local_date": today,
                        "sealed": False,
                        "contract_line": "",
                        "targets": [],
                        "yesterday": yest_payload
                    })
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/ledger/recent":
            try:
                from .constants import DB_PATH
                from .db import Database
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                parsed_q = parse_qs(urlparse(self.path).query)
                limit = int(parsed_q.get("limit", ["50"])[0])
                rows = db.query(
                    "SELECT seq, event_id, occurred_at_utc, event_type, observed_payload, action_taken, prev_hash, row_hash "
                    "FROM event ORDER BY seq DESC LIMIT ?",
                    (min(limit, 200),)
                )
                self._send(200, {"ok": True, "events": rows})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/stats/stage_ratio":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .stats import compute_today_stage_summary
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                summary = compute_today_stage_summary(db)
                self._send(200, summary)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/stats/streak":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .stats import compute_streak
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                streak = compute_streak(db)
                self._send(200, {"ok": True, "streak": streak})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/oa/drill":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .oa_simulator import OASimulator
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                sim = OASimulator(db, ledger=self.ledger)
                self._send(200, {"ok": True, "drill": sim.get_daily_drill()})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/capability/drills":
            try:
                from .capability import CapabilityService
                from .constants import DB_PATH, DEFAULT_HOME
                from .db import Database
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                svc = CapabilityService(db, ledger=self.ledger, home=DEFAULT_HOME)
                self._send(200, {"ok": True, "drills": svc.list_drills()})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/defense/cards":
            try:
                import sqlite3
                from .constants import DB_VIDURA_PATH
                if not DB_VIDURA_PATH.exists():
                    self._send(200, {"ok": True, "cards": []})
                    return
                conn = sqlite3.connect(str(DB_VIDURA_PATH))
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT id, title, description, url FROM content_item WHERE kind='defense' ORDER BY rowid DESC LIMIT 50"
                )
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                self._send(200, {"ok": True, "cards": rows})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif path == "/api/vidura/feed":
            try:
                from .vidura_feed import ViduraFeedService
                svc = ViduraFeedService()
                feed_data = svc.get_categorized_feed()
                self._send(200, feed_data)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        elif GuardRoutes.dispatch(self, "GET", path, None):
            return
        else:
            self._send(404, {"error": "unknown endpoint"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._authorized():
            self._send(401, {"error": "bad or missing X-Dhriti-Token"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        max_bytes = 50_000_000 if path == "/api/gallery/upload" else 1_000_000
        if length < 0 or length > max_bytes:
            self._send(400, {"error": "invalid body size"})
            return
        payload = {}
        if length > 0:
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                self._send(400, {"error": "invalid JSON"})
                return

        if path == "/ritual/seal":
            try:
                from .constants import DB_PATH, DEFAULT_HOME
                from .db import Database
                from .contract import ContractService
                from .timeutil import RealClock
                import datetime as _dt
                today = _dt.date.today().isoformat()
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                contracts = ContractService(db, RealClock())
                
                contract_line = payload.get("contract_line", "").strip()
                if not contract_line:
                    self._send(400, {"error": "contract_line required"})
                    return
                raw_targets = payload.get("targets", [])
                if not raw_targets:
                    raw_targets = [{"label": contract_line, "kind": "learning", "evidence": {"class": "learning"}}]
                
                targets = []
                for t in raw_targets:
                    if isinstance(t, str):
                        targets.append({"label": t, "kind": "learning", "evidence": {"class": "learning"}})
                    elif isinstance(t, dict):
                        if "evidence" not in t:
                            t["evidence"] = {"class": "learning"}
                        targets.append(t)

                full_payload = {
                    "identity_statement": payload.get("identity_statement", "I am a sovereign engineer focused on learning and shipping."),
                    "contract_line": contract_line,
                    "targets": targets,
                    "profile": payload.get("profile", "study"),
                    "main_belief": {"label": payload.get("main_belief_label", "Consistent deliberate study clears assessments.")},
                    "main_belief_metric": payload.get("main_belief_metric", "DSA problems solved & interview readiness"),
                    "main_belief_current_state": payload.get("main_belief_current_state", "Active preparation"),
                    "substitute_activities": payload.get("substitute_activities") if isinstance(payload.get("substitute_activities"), list) and payload.get("substitute_activities") else ["Passive browsing"],
                    "substitute_budget": str(payload.get("substitute_budget") or "0 hours per week")
                }

                sealed = contracts.seal(today, full_payload)
                try:
                    override_file = DEFAULT_HOME / f"contract-{today}.json"
                    override_file.write_text(json.dumps(full_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
                if self.ledger:
                    self.ledger.record("contract_sealed", observed={"date": today, "targets": len(targets)}, action_taken="contract sealed via UI ritual")
                self._send(200, {"ok": True, "sealed": True, "date": today, "targets": targets, "contract_line": contract_line})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/targets/claim":
            target_id = payload.get("target_id")
            label = payload.get("label", "")
            if self.ledger:
                self.ledger.record("target_claimed", observed={"target_id": target_id, "label": label})
            self._send(200, {"ok": True, "claimed": True, "target_id": target_id})
            return

        elif path in ("/pivot/declare", "/pivot/confirm"):
            try:
                from .constants import DB_PATH
                from .db import Database
                from .pivot import PivotService, PivotError
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                pivot_svc = PivotService(db, ledger=self.ledger)
                topic = payload.get("topic") or payload.get("text", "")
                reason = payload.get("reason", "Declared study priority shift")
                minutes = int(payload.get("minutes", 120))
                pivot = pivot_svc.declare(topic, reason, minutes=minutes)
                self._send(200, {"ok": True, "pivot": pivot})
            except PivotError as pe:
                self._send(400, {"error": str(pe)})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/check_query":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .topic_gate import TopicGate
                import datetime as _dt
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                gate = TopicGate(db)
                query = payload.get("query", "")
                url = payload.get("url", "")
                
                today = _dt.date.today().isoformat()
                row = db.query_one(
                    "SELECT payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
                    (today,)
                )
                targets = []
                if row:
                    p_json = json.loads(row["payload_json"])
                    targets = p_json.get("targets", [])
                
                snap = self.state.snapshot()
                is_active = snap["policy"].get("enforce", False) if snap.get("policy") else True
                
                result = gate.check_query(query, targets, is_session_active=is_active)
                self._send(200, result)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/safe_anchor":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .topic_gate import TopicGate
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                gate = TopicGate(db)
                anchor = payload.get("anchor", "")
                source = payload.get("source", "user_pivot")
                ok = gate.add_safe_anchor(anchor, source=source)
                self._send(200, {"ok": ok, "anchor": anchor})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/vision/classify":
            try:
                from .classifier_sidecar.vision_axis import VisionClassifier
                classifier = VisionClassifier()
                img_b64 = payload.get("image_b64", "")
                host = payload.get("host", "")
                metadata = payload.get("metadata", {})
                
                # Zero-retention: classify and decode in-memory, bytes discarded immediately (§26.1)
                img_bytes = base64.b64decode(img_b64) if img_b64 else b""
                verdict = classifier.classify_image(img_bytes, host=host, metadata=metadata)
                
                if self.ledger:
                    self.ledger.record("vision_adjudicated", observed={
                        "host": host,
                        "sha256": verdict.get("sha256"),
                        "label": verdict.get("label"),
                        "score": verdict.get("score"),
                        "action": verdict.get("action")
                    })
                self._send(200, verdict)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/vidura/sync":
            repo_dir = Path(__file__).parent.parent
            sync_script = repo_dir / "sync_playlist.py"
            def run_sync():
                try:
                    subprocess.run([sys.executable, str(sync_script)], cwd=str(repo_dir), check=False)
                except Exception as e:
                    print(f"Vidura sync error: {e}")
            t = threading.Thread(target=run_sync, daemon=True, name="vidura-sync-worker")
            t.start()
            self._send(200, {"ok": True, "message": "Vidura playlist synchronization started in background."})
            return

        elif path == "/api/gallery/upload":
            dashboard_dir = Path(__file__).parent.parent / "dashboard"
            gallery_dir = dashboard_dir / "gallery"
            gallery_dir.mkdir(parents=True, exist_ok=True)

            raw_name = payload.get("filename", "image.jpg")
            safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', Path(raw_name).stem)
            ext = Path(raw_name).suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
                ext = ".jpg"
            filename = f"{safe_stem}_{int(time.time())}{ext}"
            target_path = gallery_dir / filename

            data_str = payload.get("data", "")
            if "," in data_str:
                data_str = data_str.split(",", 1)[1]
            try:
                img_bytes = base64.b64decode(data_str)
                target_path.write_bytes(img_bytes)
            except Exception as e:
                self._send(400, {"error": f"failed to decode image data: {e}"})
                return

            self._send(200, {
                "ok": True,
                "image": {
                    "id": f"local-{target_path.stem}",
                    "title": payload.get("title") or safe_stem.replace("_", " ").title(),
                    "filename": filename,
                    "url": f"/gallery/{filename}",
                    "size": len(img_bytes)
                }
            })
            return

        elif path == "/api/gallery/delete":
            dashboard_dir = Path(__file__).parent.parent / "dashboard"
            filename = Path(payload.get("filename", "")).name
            target_path = dashboard_dir / "gallery" / filename
            if target_path.exists() and target_path.is_file():
                try:
                    target_path.unlink()
                    self._send(200, {"ok": True, "deleted": filename})
                    return
                except Exception as e:
                    self._send(500, {"error": f"failed to delete: {e}"})
                    return
            self._send(404, {"error": "file not found"})
            return

        elif path == "/api/vidura/recall":
            item_id = payload.get("item_id")
            answer = payload.get("answer", "")
            if not item_id:
                self._send(400, {"error": "item_id is required"})
                return
            try:
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                from .vidura_surface import ViduraSurfaceService
                corpus = ViduraCorpus(DB_VIDURA_PATH)
                svc = ViduraSurfaceService(corpus)
                res = svc.submit_recall_response(item_id, answer)
                self._send(200, {"ok": True, "result": res})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/events" and self.on_event is not None:
            events = payload.get("events", [payload])
            ingested, errors = 0, []
            for event in events[:100]:
                try:
                    self.on_event(self.ledger, event)
                    ingested += 1
                except Exception as exc:  # report, never silently fake
                    errors.append(str(exc)[:200])
            self._send(200, {"ingested": ingested, "errors": errors})
        elif path == "/proof" and self.on_event is not None:
            self.on_event(self.ledger, {"type": "browser_proof", **payload})
            self._send(200, {"accepted": True})
        elif path == "/lockdown/engage":
            try:
                if self.ledger:
                    self.ledger.record("lockdown_engaged", observed={"reason": "Emergency dashboard lockdown"})
                if hasattr(self, "guard_ctx") and self.guard_ctx and hasattr(self.guard_ctx, "state"):
                    self.guard_ctx.state.mode = "FULL_LOCK"
                self._send(200, {
                    "ok": True,
                    "locked": True,
                    "message": "Daily Lockdown Engaged. Enforcement active until tomorrow morning."
                })
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/task/poison":
            try:
                from .task_balancer import pick_your_poison
                deficit = float(payload.get("deficit", 2.0))
                backlog = payload.get("backlog", [])
                options = pick_your_poison(deficit, backlog, max_options=3)
                formatted = []
                for idx, basket in enumerate(options):
                    total_u = sum(item.get("units", 1.0) for item in basket)
                    label = f"Option {chr(65+idx)}: " + (" & ".join(t.get("title", "") for t in basket[:2]))
                    formatted.append({
                        "label": label,
                        "units": round(total_u, 1),
                        "items": [f"{t.get('title', '')} ({t.get('units', 1.0)}u)" for t in basket]
                    })
                self._send(200, {"ok": True, "options": formatted})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/targets/verify_recall":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .learning_proof import LearningProofService, LearningProofError
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                svc = LearningProofService(db, ledger=self.ledger)
                target_id = payload.get("target_id")
                synthesis = payload.get("synthesis") or payload.get("text", "")
                res = svc.claim_with_proof(target_id, synthesis)
                self._send(200, res)
            except LearningProofError as lpe:
                self._send(400, {"error": str(lpe)})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/defense/generate":
            try:
                from .project_defense import ProjectDefenseService
                from .constants import DB_VIDURA_PATH
                from .vidura_corpus import ViduraCorpus
                svc = ProjectDefenseService()
                file_target = payload.get("file") or "dhriti/topic_gate.py"
                res = svc.generate_defense_questions(file_target)
                if payload.get("save_to_vidura", True) and DB_VIDURA_PATH.exists():
                    try:
                        corpus = ViduraCorpus(DB_VIDURA_PATH)
                        svc.save_to_vidura(corpus, file_target, res["questions"])
                    except Exception:
                        pass
                self._send(200, res)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/oa/submit":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .oa_simulator import OASimulator
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                sim = OASimulator(db, ledger=self.ledger)
                answers = payload.get("answers", {})
                res = sim.submit_drill(answers)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/capability/start":
            try:
                from .capability import CapabilityService
                from .constants import DB_PATH, DEFAULT_HOME
                from .db import Database
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                svc = CapabilityService(db, ledger=self.ledger, home=DEFAULT_HOME)
                drill_id = payload.get("drill_id", "palindrome")
                duration = int(payload.get("duration", 25))
                res = svc.start_drill(drill_id, duration_min=duration)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/capability/verify":
            try:
                from .capability import CapabilityService
                from .constants import DB_PATH, DEFAULT_HOME
                from .db import Database
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                svc = CapabilityService(db, ledger=self.ledger, home=DEFAULT_HOME)
                drill_id = payload.get("drill_id")
                code = payload.get("code") or payload.get("file_path")
                if not drill_id or not code:
                    self._send(400, {"error": "drill_id and code/file_path are required"})
                    return
                res = svc.verify_drill(drill_id, code)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif path == "/api/vidura/feed/add_target":
            try:
                from .constants import DB_PATH
                from .db import Database
                from .vidura_feed import ViduraFeedService
                db = self.ledger.db if self.ledger and hasattr(self.ledger, "db") else Database(DB_PATH)
                item_id = payload.get("item_id")
                if not item_id:
                    self._send(400, {"error": "item_id is required"})
                    return
                svc = ViduraFeedService()
                res = svc.add_feed_item_as_target(db, item_id)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        elif GuardRoutes.dispatch(self, "POST", path, payload):
            return
        else:
            self._send(404, {"error": "unknown endpoint"})


class BridgeServer:
    def __init__(self, host: str, port: int, token: str,
                 state: BridgeState, ledger=None, on_event=None,
                 guard_ctx=None):
        self.host = host
        self.port = int(port)
        self.token = token
        self.state = state
        self.ledger = ledger
        self.on_event = on_event
        self.guard_ctx = guard_ctx
        self._httpd = None
        self._thread = None
        self.port_bound = None      # set by start(); real bound port

    def start(self):
        if self._httpd is not None:
            return
        # staticmethod() prevents Python from binding on_event to the
        # handler instance (a function on a class becomes a method).
        handler = type("BoundHandler", (BridgeHandler,), {
            "state": self.state,
            "token": self.token,
            "on_event": staticmethod(self.on_event),
            "ledger": self.ledger,
            "guard_ctx": self.guard_ctx,
        })
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        # port 0 = ephemeral: record what the OS actually assigned so
        # tests and the health probe can find the bridge.
        self.port_bound = self._httpd.server_address[1]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True,
            name="dhriti-bridge")
        self._thread.start()

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None
            self.port_bound = None

    @property
    def running(self) -> bool:
        return self._httpd is not None


def handle_extension_event(ledger, event: dict, session_resolver=None):
    """Normalize a browser event into the ledger. The extension posts
    {url, title, tabId, ts} for navigations, plus TYPED events
    ({type: 'surface_suppressed'|'blocked_tabs_closed', rule, ...})
    which keep their own event_type (D-024). Policy evaluation happens
    here (server side), not in the extension — one source of truth."""
    from .models import Action  # local import to avoid cycles
    from .policy import PolicyEngine  # lazy

    event_type = event.get("type") if event.get("type") not in (
        None, "browser_navigation") else "browser_navigation"
    url = (event.get("url") or "")[:2000]
    title = (event.get("title") or "")[:500]
    observed = {"url": url, "title": title}
    action_taken = "observed"
    if event_type in ("surface_suppressed", "blocked_tabs_closed",
                      "surface_rule_stale"):
        observed = {"site": url, "rule": (event.get("rule") or "")[:100]}
        action_taken = ("springboard removed" if event_type ==
                        "surface_suppressed" else
                        "tabs closed at arming" if event_type ==
                        "blocked_tabs_closed" else
                        "selector no longer matches — rule needs "
                        "cold-state maintenance")
    ledger.record(
        event_type,
        source_adapter="extension",
        source_version=str(event.get("ext_version", "")),
        session_id=(session_resolver() if session_resolver else None),
        observed=observed,
        action_taken=action_taken,
        telemetry_quality="OK",
    )
    # The decision for the URL is computed against the live policy and
    # recorded with the event for later false-positive analysis.
    return {"url": url, "action": Action.ALLOW.value}
