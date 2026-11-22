import tempfile
import urllib.request
from pathlib import Path
from dhriti.bridge import BridgeServer, BridgeState


def test_dashboard_static_routes():
    state = BridgeState()
    token = "test-token-12345"
    server = BridgeServer("127.0.0.1", 0, token, state)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port_bound}"

        # 1. Test /dashboard
        with urllib.request.urlopen(f"{base_url}/dashboard") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type")
            html = resp.read().decode("utf-8")
            assert "Dhriti" in html
            assert "grid-board" in html
            assert "chimes-canvas" in html

        # 2. Test /style.css
        with urllib.request.urlopen(f"{base_url}/style.css") as resp:
            assert resp.status == 200
            assert "text/css" in resp.headers.get("Content-Type")
            css = resp.read().decode("utf-8")
            assert "tactile-tile" in css

        # 3. Test /app.js
        with urllib.request.urlopen(f"{base_url}/app.js") as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type")
            js = resp.read().decode("utf-8")
            assert "Solitaire" in js or "flipToDashboard" in js

        # 4. Test /physics_chimes.js
        with urllib.request.urlopen(f"{base_url}/physics_chimes.js") as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type")
            js = resp.read().decode("utf-8")
            assert "DhritiChimes" in js

        # 5. Test /audio_synth.js
        with urllib.request.urlopen(f"{base_url}/audio_synth.js") as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type")
            js = resp.read().decode("utf-8")
            assert "DhritiAudio" in js

        # 6. Test /thought_bubbles.js
        with urllib.request.urlopen(f"{base_url}/thought_bubbles.js") as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type")

        # 7. Test POST /api/vidura/sync
        req = urllib.request.Request(f"{base_url}/api/vidura/sync", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = resp.read().decode("utf-8")
            assert "started" in data

        # 8. Test GET /targets
        with urllib.request.urlopen(f"{base_url}/targets") as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert "ok" in data
            assert "targets" in data

        # 9. Test GET /ritual/state
        with urllib.request.urlopen(f"{base_url}/ritual/state") as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert "ok" in data
            assert "date" in data

        # 10. Test POST /api/check_query
        check_body = b'{"query": "java multithreading deadlock"}'
        req = urllib.request.Request(f"{base_url}/api/check_query", data=check_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert data.get("allowed") is True

        # 11. Test POST /api/safe_anchor
        anchor_body = b'{"anchor": "operating systems scheduling algorithms", "source": "test"}'
        req = urllib.request.Request(f"{base_url}/api/safe_anchor", data=anchor_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True

        # 12. Test POST /pivot/declare
        pivot_body = b'{"topic": "Quantitative Aptitude: Time and Work", "reason": "Pivoting study to clear assessment drill"}'
        req = urllib.request.Request(f"{base_url}/pivot/declare", data=pivot_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True

        # Verify GET /targets includes the declared pivot
        with urllib.request.urlopen(f"{base_url}/targets") as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            labels = [t.get("label") for t in data.get("targets", [])]
            assert "Quantitative Aptitude: Time and Work" in labels

    finally:
        server.stop()

