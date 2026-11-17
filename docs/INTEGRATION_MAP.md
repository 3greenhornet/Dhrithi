# INTEGRATION_MAP.md — exact insertion points, verified against the repo

This is the precise, file-and-line companion to `INTEGRATION.md` (which
explains what each module is). This file says **where each wire goes in
YOUR repo**, with the real symbol names. Everything marked `repo line ~N`
was verified against your code dump. If your tree has moved since, the
symbol names still find the spot.

---

## 0. Corrections vs INTEGRATION.md (v1.1)

Three wiring details in the v1.1 guide were guessed; they are now
verified and the kit code was updated to match:

| # | v1 said | Your repo actually does | Fixed where |
|---|---|---|---|
| 1 | `emit=lambda ev: ledger.append(ev)` | `Ledger.record(event_type, *, source_adapter, source_version, session_id, case_id, parent_event_id, process_instance_id, observed, raw_payload_reference, inference_payload, model_id_or_rule_version, policy_version, action_taken, telemetry_quality, occurred_at_utc)` (repo line ~19321) | `bridge/bridge_additions.py::guard_emit` — an adapter that does the `observed` vs `inference_payload` split correctly (facts vs judgements) |
| 2 | `handler._send_json(...)` | Your `BridgeHandler._send(status, payload)` (repo line ~17758) | `GuardRoutes.dispatch` now tries `_send` first, falls back to `_send_json` |
| 3 | "add ONE dispatch line" (vague) | Routes are `elif` chains inside `do_GET` (repo ~17755) and `do_POST` (repo ~17777); handler class is built dynamically as `type("BoundHandler", (BridgeHandler,), {...})` in `BridgeServer.start()` (repo ~17826) | Exact `elif` lines + `guard_ctx` pass-through below |

---

## 1. Python core — copy 10 files into `dhriti/`

```
chat_guard.py  content_store.py  retention.py  guard_metrics.py
observer_crosscheck.py  canary.py  anchor_proof.py  conform.py
external_cli_probe.py                                  # NEW v1.1
classifier_sidecar/  (__init__.py, server.py, verdict.py,
                      embedding_axis.py, function_axis.py)
```

Nothing imports your repo modules — the modules are seam-first (they
take callables/stores). No circular imports. `classifier_sidecar` and
`content_store` use `sqlite3`/stdlib only; `sentence-transformers` and
`transformers` are **lazy imports inside backend slots** — absent
installs degrade to documented deterministic fallbacks, never to crashes.

Also copy `bridge/bridge_additions.py` (it can live at
`dhriti/bridge_additions.py`; it imports `dhriti.chat_guard` when
inside the package and falls back to sibling imports standalone).

New data file (auto-created, no migration): `guard_content.sqlite3`
in your data dir — the sidecar store, OUTSIDE the hash chain.

---

## 2. Bridge wiring — `dhriti/bridge.py` (3 edits)

**Edit A — `BridgeServer.__init__` (repo ~17808):** add one optional
parameter and one assignment:

```python
class BridgeServer:
    def __init__(self, host: str, port: int, token: str,
                 state: BridgeState, ledger=None, on_event=None,
                 guard_ctx=None):                    # NEW
        ...
        self.guard_ctx = guard_ctx                   # NEW
```

**Edit B — `BridgeServer.start()` (repo ~17826):** pass it into the
dynamically-built handler class:

```python
handler = type("BoundHandler", (BridgeHandler,), {
    "state": self.state,
    "token": self.token,
    "on_event": staticmethod(self.on_event),
    "ledger": self.ledger,
    "guard_ctx": self.guard_ctx,                     # NEW
})
```

**Edit C — two dispatch lines:**

```python
# do_GET — after the /policy branch, before the final else 404:
    elif GuardRoutes.dispatch(self, "GET", path, None):
        return

# do_POST — after the /proof branch (payload already parsed), before
# the final else 404:
    elif GuardRoutes.dispatch(self, "POST", path, payload):
        return
```

Both sit AFTER `self._authorized()` — guard routes inherit your token
auth and your rate-limited-401 behavior unchanged.

**At daemon start** (where the BridgeServer is constructed), build the
context. The full snippet is in `bridge_additions.WIRING_SNIPPET`;
short form:

```python
from types import SimpleNamespace
from dhriti.content_store import ContentStore
from dhriti.chat_guard import GuardState, GuardMode
from dhriti.bridge_additions import guard_emit

store = ContentStore(os.path.join(data_dir, "guard_content.sqlite3"))
raw = store.kv_get("guard_state")
state = (GuardState.from_snapshot(raw) if raw else
         GuardState(mode=GuardMode.CHECKPOINT,
                    topic_label=contract.current_work_line,   # fact only
                    prompt_budget_limit=config["research_pass"].get(
                        "prompt_budget", 15)))

server = BridgeServer(host, port, token, state=bridge_state,
                      ledger=ledger, on_event=on_bridge_event,
                      guard_ctx=SimpleNamespace(
                          store=store, state=state,
                          config=DEFAULT_CONFIG,
                          emit=lambda ev: guard_emit(ledger, ev)))
```

`guard_emit` writes through your real `Ledger.record(...)`, maps every
`guard_*` type to a terse `action_taken` string, and splits payloads
the way your ledger already demands: facts (ts, prompt_hash, thread_id,
counts, honored_delay) → `observed`; judgements (reason codes, P-codes,
backend names) → `inference_payload`.

Routes added: `GET /guard/state`; `POST /guard/send_event`,
`/guard/toll_paid`, `/guard/override`, `/guard/park`,
`/guard/thread_open`, `/guard/thread_dispose`,
`/guard/adapter_health`, `/guard/sidecar_armed`. With `guard_ctx=None`
(the default) every route answers `503 {"error": "guard not
configured"}` — fail-visible, never a silent pass.

**Event vocabulary is additive and safe:** your `/events` route does
not validate event types against a whitelist (verified — the
`OBSERVED_EVENT_TYPES` set at repo ~7211 is the SPECIMEN-coding
vocabulary, not a bridge gate). The 17 `guard_*` event types therefore
need no registration; they ride `guard_emit` directly into the chain.

---

## 3. Config — `dhriti/constants.py` (`DEFAULT_CONFIG`, repo ~17920)

Paste the block from `INTEGRATION.md` §3. It nests under new top-level
keys (`guard`, `guard_sidecar`, `retention`, `canary`, `metrics`) so it
cannot collide with existing groups. L-3 notes:

- The sidecar is **off by default** (`"guard_sidecar": {"enabled":
  False}`) — L-6 cold-state consent; arming emits `guard_sidecar_armed`.
- Config values here are sealed like everything else; no hot reload.
  The guard state itself (`GuardState`) is NOT config — it is runtime
  state persisted in the sidecar kv store, same split as your policy
  snapshot vs sealed policy.

## 4. CLI — `dhriti/cli.py` (repo `add_parser` pattern ~24268+)

Match your existing style:

```python
p = sub.add_parser("retention", help="purge expired raw text (D-075)")
p.add_argument("--purge-raw-after", type=int, default=None)
p.add_argument("--execute", action="store_true")
p.set_defaults(func=cmd_retention)

p = sub.add_parser("guard", help="conversation guard (deterministic core)")
gsub = p.add_subparsers(dest="guard_cmd")
g = gsub.add_parser("status")            # chat_guard.snapshot_for_digest
g.set_defaults(func=cmd_guard_status)

p = sub.add_parser("canary", help="canary checks (D-081/D-087)")
csub = p.add_subparsers(dest="canary_cmd")
c = csub.add_parser("check")             # canary.check_e2_canary
c.add_argument("--hosts-audit", action="store_true")  # + audit_hosts_entries
c.set_defaults(func=cmd_canary)

p = sub.add_parser("conform", help="deviation check (D-083)")
p.add_argument("--date")
p.add_argument("--pm4py", action="store_true")   # optional offline
p.set_defaults(func=cmd_conform)

p = sub.add_parser("crosscheck", help="sensor disagreement scan (D-080)")
p.set_defaults(func=cmd_crosscheck)
```

Each `cmd_*` is ~5 lines wiring the module function; `retention` and
`canary`/`conform`/`crosscheck` implementations are importable
directly. The stack-role probe for external blockers is
`external_cli_probe.audit_gate(...)` — it follows your audit-gated
placeholder shape (FocusMe/Plucky/Focuser): refuses to arm until the
audit passes, records `cannot-control` honestly.

## 5. Extension wiring — merge into the EXISTING extension

Your extension already has `background.js` (wall: DNR + policy sync +
`dhriti-sync` alarm, repo ~16287) and `suppress.js` (D-024 surface
suppression). The guard coexists; it does not replace either.

1. **manifest.json merge** (do NOT copy `manifest_additions.json` over
   yours — it is a standalone test manifest):
   - add to `permissions`: `"webRequest"` (storage/alarms you have)
   - add the 5 chat-site entries to `host_permissions`
   - add the content_scripts entry with `"js": ["chatguard_content.js"]`
     (keep your existing entries; `run_at: document_idle`)
2. **One service worker only (MV3):** add
   `importScripts("chatguard_background.js");` at the TOP of your
   existing `background.js`. The guard script registers its own
   `chrome.alarms` listener (`"guard-policy"`, 1 min — MV3 floor 0.5
   is respected) and its own `onMessage` routes; it does not touch your
   `dhriti-sync` alarm or your DNR rules.
3. **Token provisioning:** `chrome.storage.local.set({token: ...})`
   from your existing onboarding flow (the guard reads the same key
   your background uses).
4. **The DOM is the battlefield, DNR is not used** for the guard: MV3
   cannot block requests dynamically; the content script gates sends at
   capture phase and diffs the transcript (source of truth). Your
   existing DNR wall keeps doing domain-level work.
5. **TTL lapse (D-062 house rule):** `POLICY_TTL_MS = 5 * 60 * 1000` in
   `chatguard_background.js` must match `bridge.policy_ttl_minutes`.
   On lapse the guard degrades to LOCAL deterministic governors only —
   documented, never silent.
6. **Site adapter slot:** add an entry to `ADAPTERS` in
   `chatguard_content.js`; field contract in `extension/SITE_ADAPTERS.md`.
   The `generic` fallback adapter (Enter-count + transcript-diff) works
   on unknown chat sites with no selectors.
7. **Sidecar slot:** `chrome.storage.local.set({sidecarUrl, sidecarToken})`
   then message `guard_sidecar_arm`; the arming probe hits `/health`
   and emits `guard_sidecar_armed` (L-6 consent event) only on success.

## 6. Scheduled jobs (Windows-first)

```
schtasks /Create /TN "Dhriti retention purge" /SC DAILY /ST 03:30 ^
  /TR "python -m dhriti.cli retention --execute"

schtasks /Create /TN "Dhriti E2 canary" /SC DAILY /ST 07:00 ^
  /TR "powershell -File scripts/e2_canary_check.ps1"
```

`e2_canary_check.ps1` does BOTH canary families now: DNS resolution of
`dhriti-canary.invalid` (D-081) and `--hosts-audit` on the hosts file
(D-087, bypass-shaped anomalies).

## 7. Digest additions — `dhriti/aftermath.py`

```python
from dhriti.guard_metrics import (kill_chain_attribution, novelty_domains,
                                  park_break_ratio, render_guard_block)
from dhriti.chat_guard import snapshot_for_digest
```

Append `render_guard_block(...)` to the Experiment view (five-view
honesty, L-7 — including its overrides). `park_break_ratio(series)` is
the near-miss pyramid line (D-085). `kill_chain_attribution` feeds
stage-attribution into the Conversation Boundary view.

## 8. Optional: coverage-map row

The guard is bridge-mediated, not a classic adapter class, so no
registry change is REQUIRED. If you want it visible in
`dhriti health`'s coverage map, add a stack-role row keyed on
`chat_guard` with `manifest()` = `{armed: guard_ctx is not None,
sidecar: config.guard_sidecar.enabled, sites: [manifest matches]}`.
Honest health beats pretty health — if you don't wire it, the digest
block still reports it.

## 9. The 10-minute smoke path

```bash
cd <repo>
python -m unittest tests.test_chat_guard tests.test_content_store \
         tests.test_metrics_and_sensors tests.test_counterexamples \
         tests.test_v1_1_additions -v        # 78 tests, all local
python scripts/smoke_guard_day.py           # golden day incl. guard events
python -m dhriti.cli events --type guard_send_held   # chain received them
```

Then the browser: load the extension unpacked, open a chat site, send
3 prompts inside 10 minutes → third send gets the burst hold card →
pay the 10 s toll or park it → `guard_burst_toll` /
`guard_toll_paid` / `guard_parked` in the ledger, prompt text only in
the sidecar, hash only in the chain.

## 10. Enablement order (L-6 sequencing, all at cold state)

1. Day 0: wire bridge + extension, `guard_sidecar.enabled=False`.
   Structural governors only (burst toll, budget, interlock, length
   cap) — L-4-pure, no content anywhere.
2. First clean week: review the guard block in the digest. Only then
   decide on the sidecar.
3. Sidecar (optional, cold-consent): `enabled: true`, arm via the
   extension, run `dhriti embed-eval` against your coded specimens
   FIRST; escalate-not-decide is enforced in `chat_guard.decide` — the
   sidecar can only raise an action to the mode floor, never deny.

## 11. Rollback story

- `guard_ctx=None` → all routes 503 honestly; extension degrades to
  local governors after TTL.
- `guard_sidecar.enabled=False` → embedding/function axes never load.
- Remove the two dispatch lines → the guard is fully inert; the 10
  copied files are dormant (nothing auto-runs at import).
- The sidecar DB can be deleted outright; the chain never referenced
  its rows (D-075 — content lives outside the chain by construction).
