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

    finally:
        server.stop()

