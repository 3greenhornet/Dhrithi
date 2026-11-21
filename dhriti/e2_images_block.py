#!/usr/bin/env python3
"""
dhriti-e2 · images-vertical block adapter (D-082, ring 1: DNS)

Rationale
---------
Google Images is no longer its own site: the grid lives on www.google.com/search
with tbm=isch (legacy) or udm=2 (current), reachable via images.google.com and
imghp. A hosts file cannot distinguish paths or query params on the SAME host —
that is rings 2/3 (extension) territory. What ring 1 can do:

  * kill the dedicated entry hosts   (images.google.com, lens.google.com)
  * kill the thumbnail CDN           (encrypted-tbn0..3.gstatic.com) — so even if
    a stale Images page somehow renders, the grid is empty and nothing scrolls
  * plant a canary hostname (D-081)  — if it stops resolving to 127.0.0.1,
    something (AV cleaner, manual edit) silently removed the block

Interface: probe() / arm() / disarm() / status() — matches the adapter registry
contract (probe->arm->disarm->status). Pure stdlib. Windows-first.

Usage:  python e2_images_block.py probe|arm|disarm|status
Elevation: writing the hosts file needs an Administrator terminal once (arm).
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# [PLUG-IN] override via env var or move lookup into your adapter config block
HOSTS_PATH = Path(
    os.environ.get("DHRI_E2_HOSTS",
                   r"C:\Windows\System32\drivers\etc\hosts" if os.name == "nt" else "/etc/hosts")
)

MARK_BEGIN = "# >>> dhriti-e2 images-vertical (managed) >>>"
MARK_END   = "# <<< dhriti-e2 images-vertical <<<"

# Positive control (D-081): must resolve to 127.0.0.1 while the block is armed.
CANARY_HOST = "dhriti-canary.invalid"

# Dedicated entry hosts + thumbnail CDN. www.google.com search itself is NOT
# blocked — only the Images verticals are, via the extension rings.
BLOCKED_HOSTS = [
    "images.google.com",
    "lens.google.com",
    "encrypted-tbn0.gstatic.com",
    "encrypted-tbn1.gstatic.com",
    "encrypted-tbn2.gstatic.com",
    "encrypted-tbn3.gstatic.com",
    # "photos.google.com",  # optional: your own photo library — uncomment if you
    #                       # want that exiled too; then mirror it in the DNR rules
]


def render_block() -> str:
    lines = [
        MARK_BEGIN,
        "# D-082 ring 1: kill the entry, empty the room. Managed block — do not edit inside.",
    ]
    lines += [f"0.0.0.0 {h}" for h in BLOCKED_HOSTS]
    lines += [f"127.0.0.1 {CANARY_HOST}  # canary: must stay resolvable"]
    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def read_hosts() -> list[str]:
    try:
        return HOSTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        sys.exit(f"[e2-images] hosts file not found at {HOSTS_PATH}")
    except PermissionError:
        sys.exit(f"[e2-images] hosts file not readable at {HOSTS_PATH}")


def atomic_write(lines: list[str]) -> None:
    backup = HOSTS_PATH.with_suffix(
        HOSTS_PATH.suffix + f".dhriti-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.bak"
    )
    shutil.copyfile(HOSTS_PATH, backup)
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(HOSTS_PATH.parent), prefix="hosts.", suffix=".tmp")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        os.replace(tmp_name, HOSTS_PATH)
    except PermissionError:
        Path(tmp_name).unlink(missing_ok=True)
        sys.exit(
            "[e2-images] PermissionError — run this once from an ELEVATED terminal "
            "(Administrator cmd/PowerShell):  python e2_images_block.py arm"
        )
    print(f"[e2-images] hosts updated (backup: {backup.name})")
    if os.name == "nt":
        print("[e2-images] now run:  ipconfig /flushdns   and restart your browser")


def replace_managed_region(lines: list[str], block_lines: list[str]) -> list[str]:
    """Idempotent: swap the managed region if present, else append it."""
    try:
        i = next(idx for idx, l in enumerate(lines) if l.strip() == MARK_BEGIN)
        j = next(idx for idx, l in enumerate(lines) if l.strip() == MARK_END and idx > i)
        return lines[:i] + block_lines + lines[j + 1:]
    except StopIteration:
        return lines + [""] + block_lines


def cmd_arm() -> None:
    lines = read_hosts()

    # Fail-visible note: duplicates left outside the managed region (manual or AV edits)?
    managed = set(BLOCKED_HOSTS) | {CANARY_HOST}
    outside, inside = [], False
    for l in lines:
        s = l.strip()
        if s == MARK_BEGIN:
            inside = True
            continue
        if s == MARK_END:
            inside = False
            continue
        if not inside and s and not s.startswith("#"):
            parts = s.split()
            if len(parts) >= 2 and parts[1] in managed:
                outside.append(l)
    if outside:
        print(f"[e2-images] note: {len(outside)} unmanaged duplicate entry/ies already present; leaving them untouched")

    atomic_write(replace_managed_region(lines, render_block().splitlines()))


def cmd_disarm() -> None:
    lines = read_hosts()
    try:
        i = next(idx for idx, l in enumerate(lines) if l.strip() == MARK_BEGIN)
        j = next(idx for idx, l in enumerate(lines) if l.strip() == MARK_END and idx > i)
        atomic_write(lines[:i] + lines[j + 1:])
        print("[e2-images] managed block removed")
    except StopIteration:
        print("[e2-images] no managed block present; nothing to do")


def resolve(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def cmd_status() -> int:
    canary_ip = resolve(CANARY_HOST)
    canary_ok = canary_ip == "127.0.0.1"

    print(f"{'host':<34} {'resolved':<16} state")
    print("-" * 62)
    all_blocked = True
    for h in BLOCKED_HOSTS:
        ip = resolve(h)
        ok = ip in (None, "0.0.0.0")
        all_blocked &= ok
        print(f"{h:<34} {ip or '—':<16} {'BLOCKED' if ok else '!! LIVE'}")

    print("-" * 62)
    print(f"{'canary (must be 127.0.0.1)':<34} {canary_ip or '—':<16} "
          f"{'OK' if canary_ok else '!! MISSING — block was silently removed'}")

    if not canary_ok:
        print("[e2-images] VERDICT: fail-visible — ring 1 is down. Re-arm from an elevated terminal.")
        return 1
    if not all_blocked:
        print("[e2-images] VERDICT: partially armed — one or more entry hosts still resolve.")
        return 1
    print("[e2-images] VERDICT: armed. Ring 1 live (entries dead, thumbnails dead, canary up).")
    print("[e2-images] reminder: if the browser uses Secure DNS (DoH), ring 1 is bypassed — "
          "keep Secure DNS OFF in browser settings.")
    return 0


def cmd_probe() -> int:
    print(f"hosts file : {HOSTS_PATH}  exists={HOSTS_PATH.exists()}")
    print(f"writable   : {os.access(HOSTS_PATH, os.W_OK) if HOSTS_PATH.exists() else False} "
          f"(os.access is not a reliable admin test on Windows — arm() is the real test)")
    print(f"targets    : {len(BLOCKED_HOSTS)} entry hosts + canary {CANARY_HOST}")
    return 0 if HOSTS_PATH.exists() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Dhriti E2 — Google Images vertical block (D-082 ring 1)")
    parser.add_argument("command", choices=["probe", "arm", "disarm", "status"], nargs="?", default="status")
    args = parser.parse_args()
    result = {"probe": cmd_probe, "arm": cmd_arm, "disarm": cmd_disarm, "status": cmd_status}[args.command]()
    return result or 0


if __name__ == "__main__":
    sys.exit(main())
