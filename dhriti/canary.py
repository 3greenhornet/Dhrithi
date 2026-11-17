"""Dhriti Guard Kit -- canaries (D-081).

Two canary families:
1. E2-tamper canary: a hostname that must never resolve except to the
   blackhole address. The hosts-file block can be silently deleted by any
   admin shell; the canary turns that silence into an event.
   - resolves to blackhole (0.0.0.0 / 127.0.0.1)  -> block alive
   - resolves to a public address                  -> TAMPERED
   - NXDOMAIN / no entry                           -> canary misconfigured
2. DOM canary: a hidden marker injected by the extension at arm-time; its
   disappearance mid-session means selectors went stale *now*. The Python
   side only records the event (EVENT_DOM_CANARY_MISSING).

The scheduled check lives in scripts/e2_canary_check.ps1 (schtasks example
in INTEGRATION.md).
"""

from __future__ import annotations

import socket
from typing import Optional

BLACKHOLES = {"0.0.0.0", "127.0.0.1", "::", "::1"}
EVENT_E2_CANARY_MISSING = "guard_e2_canary_missing"


def check_e2_canary(hostname: str, timeout: float = 3.0,
                    resolver=None) -> dict:
    """Never raises. Returns a dict for the caller to log/digest.
    resolver: injectable for tests; default socket.getaddrinfo."""
    resolve = resolver or socket.getaddrinfo
    try:
        infos = resolve(hostname, None)
    except socket.gaierror as exc:
        # NXDOMAIN: hosts entry missing or DNS resolver bypassing hosts
        return {"ok": False, "status": "missing_entry",
                "detail": f"{hostname} did not resolve ({exc}); "
                          "add '0.0.0.0 {0}' to hosts".format(hostname),
                "event": EVENT_E2_CANARY_MISSING}
    except Exception as exc:  # network down etc. -- honest unknown
        return {"ok": None, "status": "unknown", "detail": str(exc)}
    addrs = sorted({i[4][0] for i in infos})
    if all(a in BLACKHOLES for a in addrs):
        return {"ok": True, "status": "alive", "addresses": addrs,
                "detail": "hosts-file block is live"}
    return {"ok": False, "status": "tampered", "addresses": addrs,
            "detail": "canary resolved to a public address; "
                      "the E2 block is gone",
            "event": EVENT_E2_CANARY_MISSING}


def hosts_line(hostname: str) -> str:
    """The line integrations/windows/hosts-block.ps1 should append."""
    return f"0.0.0.0 {hostname}"


# --------------------------------------------------------------------------
# Block-list bypass audit (D-087) -- borrowed from the raw-material CVE note
# --------------------------------------------------------------------------
# CVE-2026-17923 (Chrome URLBlocklist bypass via crafted domain names) is
# the browser-policy shape of a GENERAL failure: an exact-match block list
# is routed around by name variants. hosts-file E2 has the same class of
# hole -- the canary above proves ONE hostname is blocked, not that the
# LIST still means what it said. audit_hosts_entries turns each variant
# class into a finding so the E2 layer cannot rot silently.

BLACKHOLE_IPS = BLACKHOLES  # alias: same set, clearer name for the audit


def normalize_hostname(name: str) -> str:
    """Canonical form for comparison ONLY: lowercase, strip one trailing
    dot. Deliberately does NOT strip 'www.' -- www.x.com is a distinct
    hosts entry, and treating it as equal is exactly the bypass this
    audit exists to catch."""
    return name.strip().lower().rstrip(".")


def audit_hosts_entries(content: str) -> dict:
    """Parse hosts-file content and flag bypass-shaped anomalies.
    Never raises; content injectable for tests (read the file at the
    call site: C:/Windows/System32/drivers/etc/hosts or /etc/hosts).

    Findings (hard -> the block can actually be routed around):
      non_blackhole_ip  an entry points somewhere public
      duplicate_conflict  same hostname mapped to different address kinds
      punycode          xn-- entry (homoglyph risk; approve cold if intended)
    Findings (soft -> coverage gaps):
      www_gap           domain blocked without its www form
      trailing_dot      entry ends with a dot (resolver-dependent match)
      mixed_case        non-canonical case (works today, rots quietly)
    """
    seen: dict[str, set] = {}
    findings: list[dict] = []
    lines = content.splitlines()
    for lineno, raw in enumerate(lines, start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            findings.append({"line": lineno, "kind": "malformed",
                             "detail": f"unparseable hosts line: {raw!r}"})
            continue
        ip, host = parts[0], parts[-1]
        canon = normalize_hostname(host)
        if ip not in BLACKHOLE_IPS:
            findings.append({"line": lineno, "kind": "non_blackhole_ip",
                             "detail": f"{host} -> {ip} (public address)",
                             "host": canon})
        # .invalid canary names are our own convention: never flagged.
        if "." in host and host.rstrip(".").endswith("."):
            findings.append({"line": lineno, "kind": "trailing_dot",
                             "detail": f"{host} -- match is resolver-dependent",
                             "host": canon})
        if canon.startswith("xn--") or ".xn--" in canon:
            findings.append({"line": lineno, "kind": "punycode",
                             "detail": f"{host} -- IDN/homoglyph risk; "
                                       "approve cold-state if intended",
                             "host": canon})
        if host != host.lower():
            findings.append({"line": lineno, "kind": "mixed_case",
                             "detail": f"{host} -- normalize to lowercase",
                             "host": canon})
        seen.setdefault(canon, set()).add(ip)

    for canon, ips in seen.items():
        if len(ips) > 1 and not all(i in BLACKHOLE_IPS for i in ips):
            findings.append({"line": None, "kind": "duplicate_conflict",
                             "detail": f"{canon} maps to {sorted(ips)}",
                             "host": canon})
        if (canon.endswith(".invalid") or canon.startswith("xn--")
                or "." not in canon):
            continue  # canary / TLD / IP -- no www expectation
        labels = canon.split(".")
        registrable_like = len(labels) <= 3  # approx; no PSL dependency
        if registrable_like and not canon.startswith("www.") and \
                f"www.{canon}" not in seen:
            findings.append({"line": None, "kind": "www_gap",
                             "detail": f"{canon} blocked but www.{canon} "
                                       "is not -- classic exact-match gap",
                             "host": canon})
    hard = {"non_blackhole_ip", "duplicate_conflict", "punycode"}
    out = {"checked_lines": len(lines),
           "unique_names": len(seen),
           "findings": findings,
           "hard": [f for f in findings if f["kind"] in hard],
           "soft": [f for f in findings if f["kind"] not in hard]}
    if out["hard"]:
        out["event"] = "guard_e2_block_bypass_risk"
    return out
