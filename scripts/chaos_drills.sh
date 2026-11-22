#!/usr/bin/env bash
# chaos_drills.sh -- Dhriti Guard Kit monthly fault-injection ritual (Linux/macOS).
# Windows twin: chaos_drills.ps1. Guided semi-automation: the script drives
# the cheap assertions; the human reads the states between steps.
set -u
DRILL=${1:-all}
PASS=0; FAIL=0

check() { # check <name> <cmd...>
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS  $name"; PASS=$((PASS+1));
  else echo "FAIL  $name"; FAIL=$((FAIL+1)); fi
}

manual() { echo "MANUAL $1"; }

if [ "$DRILL" = "all" ] || [ "$DRILL" = "1" ]; then
  echo "--- Drill 1: dead daemon mid-session (RECOVERED path)"
  manual "kill the daemon while a session is ACTIVE; restart it"
  manual "expect: dhriti day status shows RECOVERED (not silently golden)"
  check "verify chain intact"    dhriti verify
  check "health runs"            dhriti health
fi

if [ "$DRILL" = "all" ] || [ "$DRILL" = "2" ]; then
  echo "--- Drill 2: policy TTL lapse (D-062)"
  manual "stop the daemon; open a chat site with a fresh policy"
  manual "expect: guard degrades to LOCAL deterministic burst toll only (not bricked, not open)"
  manual "restart the daemon; expect policy returns within 1 poll cycle"
fi

if [ "$DRILL" = "all" ] || [ "$DRILL" = "3" ]; then
  echo "--- Drill 3: WAL sidecar quarantine (D-052/D-064)"
  manual "with daemon stopped: corrupt-shape a sidecar (truncate middle bytes)"
  manual "expect: quarantined to *.corrupt-<ts> + one retry; locked file must NOT quarantine"
fi

if [ "$DRILL" = "all" ] || [ "$DRILL" = "4" ]; then
  echo "--- Drill 4: token revocation"
  manual "rotate the bridge token; fire one request with the old token"
  check "bridge rejects old token (401)" sh -c "curl -s -o /dev/null -w '%{http_code}' -H 'X-Dhriti-Token: stale' http://127.0.0.1:7311/guard/state | grep -q 401"
  manual "expect: bridge_token_rejected event, rate-limited"
fi

if [ "$DRILL" = "all" ] || [ "$DRILL" = "5" ]; then
  echo "--- Drill 5: E2 canary (D-081)"
  python3 - "$@" <<'PY'
import socket, sys
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "dhriti"))
from dhriti.canary import check_e2_canary
r = check_e2_canary("dhriti-canary.invalid")
print(f"canary: {r['status']} -- {r.get('detail','')}")
sys.exit(0 if r["ok"] is True else 1)
PY
  if [ $? -eq 0 ]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
fi

echo; echo "drills: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ]
