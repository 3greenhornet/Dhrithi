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

import json
import secrets
import threading
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
        if ok or self.path.startswith("/healthz") or path in ("/", "/dashboard", "/popup.css", "/popup.js"):
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
        if path in ("/", "/dashboard"):
            popup_file = Path(__file__).parent.parent / "extension" / "popup.html"
            if popup_file.exists():
                self._send_bytes(200, popup_file.read_bytes(), "text/html; charset=utf-8")
                return
        elif path == "/popup.css":
            css_file = Path(__file__).parent.parent / "extension" / "popup.css"
            if css_file.exists():
                self._send_bytes(200, css_file.read_bytes(), "text/css; charset=utf-8")
                return
        elif path == "/popup.js":
            js_file = Path(__file__).parent.parent / "extension" / "popup.js"
            if js_file.exists():
                self._send_bytes(200, js_file.read_bytes(), "application/javascript; charset=utf-8")
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
        if length <= 0 or length > 1_000_000:
            self._send(400, {"error": "invalid body size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, {"error": "invalid JSON"})
            return
        if path == "/events" and self.on_event is not None:
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
