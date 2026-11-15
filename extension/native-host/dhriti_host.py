#!/usr/bin/env python3
"""Dhriti native messaging host (OPTIONAL path).

The extension normally talks to the daemon over the localhost HTTP
bridge (config.js). This host exists for a stricter setup where you
prefer Chrome's native messaging over a local port. It is a
well-specified placeholder: the length-prefixed JSON protocol is fully
implemented, but registering the host requires a manual step (registry
edit on Windows / JSON file in the browser's native messaging dir),
documented below. Until registered, it is never used.

Protocol (Chrome native messaging):
  - stdin/stdout, each message is: 4-byte little-endian length + UTF-8 JSON
  - The extension sends: {"command": "get_policy"} or
    {"command": "post_event", "event": {...}}
  - This host answers by reading the daemon's HTTP bridge on 127.0.0.1
    (same token), so there is exactly one source of truth.

Manual registration (Windows):
  1. Put this file somewhere permanent, e.g. C:\\Tools\\dhriti\\.
  2. Edit com.dhriti.bridge.json: set "path" to this file's absolute
     path and put your extension ID in allowed_origins.
  3. reg add HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\
     com.dhriti.bridge /ve /t REG_SZ /d "C:\\Tools\\dhriti\\com.dhriti.bridge.json"
  4. Update the extension to use chrome.runtime.sendNativeMessage.

Linux: place the JSON in
~/.config/google-chrome/NativeMessagingHosts/ (or chromium/ edge/).
"""

import json
import struct
import sys
import urllib.request


def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    length = struct.unpack("<I", raw_length)[0]
    if length <= 0 or length > 1_000_000:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def write_message(payload):
    data = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main():
    from pathlib import Path
    import os
    home = Path(os.environ.get("DHRITI_HOME", Path.home() / ".dhriti"))
    token_file = home / "bridge_token"
    token = token_file.read_text(encoding="utf-8").strip() \
        if token_file.exists() else ""
    while True:
        message = read_message()
        if message is None:
            return
        try:
            if message.get("command") == "get_policy":
                request = urllib.request.Request(
                    "http://127.0.0.1:7311/policy",
                    headers={"X-Dhriti-Token": token})
                with urllib.request.urlopen(request, timeout=5) as resp:
                    write_message(json.loads(resp.read().decode("utf-8")))
            elif message.get("command") == "post_event":
                event = message.get("event", {})
                body = json.dumps(event).encode("utf-8")
                request = urllib.request.Request(
                    "http://127.0.0.1:7311/events", data=body,
                    method="POST",
                    headers={"X-Dhriti-Token": token,
                             "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=5) as resp:
                    write_message({"ok": True})
            else:
                write_message({"error": "unknown command"})
        except Exception as exc:
            write_message({"error": str(exc)})


if __name__ == "__main__":
    main()
