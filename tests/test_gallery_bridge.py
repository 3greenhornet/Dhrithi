import base64
import json
import urllib.request
from pathlib import Path
import pytest
from dhriti.bridge import BridgeServer, BridgeState

# 1x1 transparent PNG base64
TINY_PNG_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

def test_gallery_upload_and_serve(tmp_path):
    state = BridgeState()
    server = BridgeServer("127.0.0.1", 0, "test-token", state)
    server.start()
    port = server.port_bound
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Test GET /api/gallery/images
        req = urllib.request.Request(f"{base_url}/api/gallery/images")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "images" in data

        # 2. Test POST /api/gallery/upload
        upload_payload = json.dumps({
            "filename": "test_sample_art.png",
            "title": "Test Sample Art",
            "data": TINY_PNG_B64
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/api/gallery/upload",
            data=upload_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            upload_res = json.loads(resp.read().decode("utf-8"))
            assert upload_res["ok"] is True
            image_info = upload_res["image"]
            assert "test_sample_art" in image_info["filename"]
            saved_filename = image_info["filename"]

        # 3. Test GET /gallery/<filename>
        req = urllib.request.Request(f"{base_url}/gallery/{saved_filename}")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "image/png"
            img_bytes = resp.read()
            assert len(img_bytes) > 0

        # 4. Test POST /api/gallery/delete
        del_payload = json.dumps({"filename": saved_filename}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/gallery/delete",
            data=del_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            del_res = json.loads(resp.read().decode("utf-8"))
            assert del_res["ok"] is True
            assert del_res["deleted"] == saved_filename

        # Verify it's deleted
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/gallery/{saved_filename}")
        assert exc_info.value.code == 404

    finally:
        server.stop()
