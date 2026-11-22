import os
import tempfile
import urllib.request
from pathlib import Path
from dhriti.bridge import BridgeServer, BridgeState
from dhriti.db import Database
from dhriti.ledger import Ledger


def test_dashboard_static_routes():
    state = BridgeState()
    token = "test-token-12345"
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    db = Database(Path(tmp.name))
    ledger = Ledger(db)
    server = BridgeServer("127.0.0.1", 0, token, state, ledger=ledger)
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

        # 10. Test POST /api/check_query (Study query -> allowed with 16 thumbnail bound)
        check_body = b'{"query": "java multithreading deadlock"}'
        req = urllib.request.Request(f"{base_url}/api/check_query", data=check_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert data.get("allowed") is True
            assert data.get("is_adult") is False
            assert data.get("suppress_image_grid") is False
            assert data.get("max_thumbnails") == 16

        # 10b. Test POST /api/check_query (Adult query -> blocked and image grid suppressed)
        adult_check_body = b'{"query": "pornographic video adult 18+"}'
        req_adult = urllib.request.Request(f"{base_url}/api/check_query", data=adult_check_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_adult) as resp:
            assert resp.status == 200
            import json as _json
            data = _json.loads(resp.read().decode("utf-8"))
            assert data.get("allowed") is False
            assert data.get("is_adult") is True
            assert data.get("suppress_image_grid") is True
            assert data.get("max_thumbnails") == 0

        # 10c. Test POST /api/vision/classify (Vision Axis zero-retention classification)
        import base64 as _base64
        dummy_png_b64 = _base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82").decode("ascii")
        vision_body = _json.dumps({"image_b64": dummy_png_b64, "host": "google.com", "metadata": {"alt": "test diagram"}}).encode("utf-8")
        req_vision = urllib.request.Request(f"{base_url}/api/vision/classify", data=vision_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_vision) as resp:
            assert resp.status == 200
            v_data = _json.loads(resp.read().decode("utf-8"))
            assert "sha256" in v_data
            assert "action" in v_data

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
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

