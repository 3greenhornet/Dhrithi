"""Classifier sidecar server -- loopback HTTP, token-authed, escalate-only.

The sidecar is a SEPARATE process (never imported by the enforcement core,
mirroring the "FastAPI stays out of enforcement" refusal). stdlib
http.server, same trust shape as the Dhriti bridge: 127.0.0.1 only,
X-Dhriti-Token required, 401 on mismatch.

Endpoints:
    GET  /health    -> {"ok": true, "backend": {...}}   (arming probe)
    POST /verdict   -> body {"prompt", "anchors": [...], "recent": [...]}
                       -> verdict.py fusion result (escalate-or-not only)

Run:
    python -m dhriti.classifier_sidecar.server --port 8765 --token-file guard.token
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dhriti.classifier_sidecar import embedding_axis, function_axis
from dhriti.classifier_sidecar.verdict import fuse
from dhriti.classifier_sidecar.springboard_math import evaluate_springboard_breach, tokenize

_state = {"requests": 0, "escalations": 0, "avg_latency_ms": 0.0}
_session_tokens = Counter()
_lock = threading.Lock()


class SidecarHandler(BaseHTTPRequestHandler):
    token = ""          # set by serve()
    max_prompt_chars = 8000

    def _authed(self) -> bool:
        return self.headers.get("X-Dhriti-Token", "") == self.token

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            if not self._authed():
                return self._send(401, {"error": "token rejected"})
            return self._send(200, {"ok": True,
                                    **embedding_axis.backend_info(),
                                    "requests": _state["requests"],
                                    "escalations": _state["escalations"]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/verdict":
            return self._send(404, {"error": "not found"})
        if not self._authed():
            return self._send(401, {"error": "token rejected"})
        import time
        t0 = time.time()
        try:
            body = json.loads(self.rfile.read(
                int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception:
            return self._send(400, {"error": "bad json"})
        prompt = str(body.get("prompt", ""))[: self.max_prompt_chars]
        anchors = [str(a)[:2000] for a in (body.get("anchors") or [])]
        recent = [str(r)[:2000] for r in (body.get("recent") or [])]
        if not prompt:
            return self._send(400, {"error": "empty prompt"})

        # Drift anchor: the pass's own earlier self (running centroid)
        centroid = embedding_axis.running_centroid(recent)
        eff_anchors = anchors + ([centroid] if centroid else [])
        topic_score = embedding_axis.score_against_anchors(prompt, eff_anchors)
        act = function_axis.classify(prompt)

        # Recommendation Engine Inversion (Pixie walk, UCB uncertainty, MMR divergence)
        prompt_vec = embedding_axis.embed(prompt)
        anchor_vecs = [v for a in anchors if (v := embedding_axis.embed(a)) is not None]
        recent_vecs = [v for r in recent if (v := embedding_axis.embed(r)) is not None]
        springboard = evaluate_springboard_breach(
            prompt, prompt_vec, anchor_vecs, recent_vecs, _session_tokens)

        verdict = fuse(
            topic_score, act["function_code"], act["confidence"],
            springboard_report=springboard)
        verdict.model_info = {
            "function_backend": act.get("backend"),
            "matched": act.get("matched"),
            "springboard": springboard,
            **embedding_axis.backend_info()}

        with _lock:
            _session_tokens.update(tokenize(prompt))
            n = _state["requests"] + 1
            ms = (time.time() - t0) * 1000.0
            _state["requests"] = n
            _state["avg_latency_ms"] = (_state["avg_latency_ms"] * (n - 1)
                                        + ms) / n
            if verdict.escalate:
                _state["escalations"] += 1
        return self._send(200, verdict.to_dict())

    def log_message(self, fmt, *args):  # quiet: no prompt text in logs
        pass


def serve(port: int = 8765, token: str = "", host: str = "127.0.0.1"):
    if not token:
        raise SystemExit("refusing to start without a token "
                         "(generate: python -c \"import secrets;"
                         "print(secrets.token_urlsafe(32))\")")
    SidecarHandler.token = token
    srv = ThreadingHTTPServer((host, port), SidecarHandler)
    print(f"sidecar on http://{host}:{port} (escalate-only sensor)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--token", default=os.environ.get("DHRITI_SIDECAR_TOKEN", ""))
    ap.add_argument("--token-file", default="")
    a = ap.parse_args()
    tok = a.token
    if not tok and a.token_file and os.path.exists(a.token_file):
        tok = open(a.token_file, "r", encoding="utf-8").read().strip()
    serve(port=a.port, token=tok, host=a.host)
