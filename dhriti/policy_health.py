#!/usr/bin/env python3
"""
Dhriti - Layer 0 + ring 1 health check (fail-visible, D-077/D-082)

Verifies, with zero dependencies:
  L0. machine policy is armed: Incognito/InPrivate disabled, DoH forced off,
      URLBlocklist contains the Images entry hosts + udm=2/tbm=isch patterns
  R1. hosts-file ring is live: entry hosts resolve to 0.0.0.0 (or fail),
      canary hostname (D-081) resolves to 127.0.0.1

Exit code 0 only if every critical check passes - so the daemon / scheduler /
`dhriti health` can consume it as a fact. Non-Windows machines: policy checks
are skipped (registry does not exist there); hosts checks still run.

Usage: python policy_health.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
    ON_WINDOWS = True
except ImportError:
    ON_WINDOWS = False

sys.path.insert(0, str(Path(__file__).parent))
from e2_images_block import BLOCKED_HOSTS, CANARY_HOST, resolve  # noqa: E402

POLICY_KEYS = {
    "Chrome": (r"SOFTWARE\Policies\Google\Chrome", "IncognitoModeAvailability"),
    "Brave":  (r"SOFTWARE\Policies\BraveSoftware\Brave", "IncognitoModeAvailability"),
    "Edge":   (r"SOFTWARE\Policies\Microsoft\Edge", "InPrivateModeAvailability"),
}

TLDS = ["google.com", "google.co.in", "google.co.uk", "google.ca", "google.com.au", "google.de", "google.fr"]

REQUIRED_TOKENS = ("search?udm=2", "search?tbm=isch", "/imghp", "/imgres")
REQUIRED_HOSTS = ("images.google.com", "lens.google.com")


def reg_read(root_path: str, name: str):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return v
    except OSError:
        return None


def reg_subkey_values(root_path: str) -> list[str]:
    """Values of the URLBlocklist subkey (values are named 1,2,3...)."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path + r"\URLBlocklist") as k:
            out = []
            i = 0
            while True:
                try:
                    _, val, _ = winreg.EnumValue(k, i)
                    out.append(str(val))
                    i += 1
                except OSError:
                    return out
    except OSError:
        return []


def check_layer0() -> tuple[int, int]:
    ok_count = 0
    total = 0
    if not ON_WINDOWS:
        print("L0  policy checks: SKIPPED (not Windows)")
        return 0, 0

    for brand, (key, incog_name) in POLICY_KEYS.items():
        total += 1
        incog = reg_read(key, incog_name)
        doh = reg_read(key, "DnsOverHttpsMode")
        safesearch = reg_read(key, "ForceGoogleSafeSearch")
        safesites = reg_read(key, "SafeSitesFilterBehavior")
        incog_allow = reg_read(key, "IncognitoModeUrlAllowlist")
        blocklist = reg_subkey_values(key)

        incog_ok = incog == 1 and not incog_allow
        doh_ok = isinstance(doh, str) and doh.lower() == "off"
        tokens_ok = all(any(tok in v for v in blocklist) for tok in REQUIRED_TOKENS) \
            and all(any(h == v for v in blocklist) for h in REQUIRED_HOSTS) \
            and len(blocklist) >= 2 * 2 * len(TLDS)
        full_ok = incog_ok and doh_ok and tokens_ok
        ok_count += full_ok

        state = "CLOSED" if full_ok else "OPEN"
        detail = []
        if not incog_ok:
            detail.append("private-mode not disabled or allowlist present")
        if not doh_ok:
            detail.append("DoH not forced off")
        if not tokens_ok:
            detail.append(f"URLBlocklist incomplete ({len(blocklist)} entries)")
        if safesearch != 1:
            detail.append("ForceGoogleSafeSearch!=1")
        if safesites != 1:
            detail.append("SafeSitesFilterBehavior!=1")
        print(f"L0  {brand:<6} {state}{'  (' + '; '.join(detail) + ')' if detail else ''}"
              f"  [incognito={'1' if incog_ok else (incog if incog is not None else 'missing')},"
              f" doh={doh if doh is not None else 'missing'}]")
    return ok_count, total


def check_ring1() -> tuple[int, int]:
    total = ok = 0
    canary_ip = resolve(CANARY_HOST)
    canary_ok = canary_ip == "127.0.0.1"
    total += 1
    ok += canary_ok
    print(f"R1  canary            {'LIVE' if canary_ok else 'MISSING — block silently removed'}"
          f"  ({canary_ip or '—'})")

    all_dead = True
    for h in BLOCKED_HOSTS:
        total += 1
        ip = resolve(h)
        dead = ip in (None, "0.0.0.0")
        ok += dead
        all_dead &= dead
        print(f"R1  {h:<34} {'DEAD' if dead else '!! LIVE'}  ({ip or 'unresolvable'})")
    return ok, total


def main() -> int:
    print("== Dhriti images-vertical exile (D-082) — health ==")
    l0_ok, l0_total = check_layer0()
    r1_ok, r1_total = check_ring1()

    print("-" * 72)
    verdict_parts = []
    if ON_WINDOWS:
        verdict_parts.append(f"Layer0 {l0_ok}/{l0_total}")
    verdict_parts.append(f"ring1 {r1_ok}/{r1_total}")
    print(f"VERDICT: {' / '.join(verdict_parts)}"
          + ("  — hole CLOSED (fail-visible monitors live)." if r1_ok == r1_total and l0_ok == l0_total
             else "  — OPEN. Run windows-policy-layer.cmd (elevated) and re-arm hosts ring."))

    if not (resolve(CANARY_HOST) == "127.0.0.1"):
        print("note: canary missing means the hosts entries were removed (AV cleaner or edit).")
    if ON_WINDOWS and l0_ok < l0_total:
        print("note: until Layer 0 is armed, Incognito remains a bypass for rings 2/3 "
              "(hosts still applies inside Incognito, provided DoH is off).")
    return 0 if (r1_ok == r1_total and l0_ok == l0_total) else 1


if __name__ == "__main__":
    sys.exit(main())
