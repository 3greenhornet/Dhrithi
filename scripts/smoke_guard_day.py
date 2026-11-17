#!/usr/bin/env python3
"""Smoke test: one simulated guard day, printed as a factual table.

Run:  python3 scripts/smoke_guard_day.py
No state is persisted; the ContentStore uses a temp file and is deleted.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dhriti import chat_guard as cg                      # noqa: E402
from dhriti.classifier_sidecar.verdict import fuse        # noqa: E402
from dhriti.content_store import ContentStore            # noqa: E402


def main() -> int:
    st = cg.GuardState(mode=cg.GuardMode.CHECKPOINT, topic_label="guard-kit build",
                       prompt_budget_limit=5)
    now = time.time()
    rows = []

    # 1. in-scope send
    d = cg.decide(st, now, in_scope=True, prompt_hash="a1")
    rows.append(("1 in-scope send", d.action.value, d.reason, ", ".join(d.card_lines[:1])))

    # 2. off-scope prompt (embedding gate says off-scope, no sidecar)
    d = cg.decide(st, now + 5, in_scope=False, prompt_hash="a2")
    rows.append(("2 off-scope (structural)", d.action.value, d.reason,
                 "collapse=" + str(d.collapse_response)))

    # 3. burst: three sends quickly -> toll
    cg.decide(st, now + 10, in_scope=True, prompt_hash="a3")
    cg.decide(st, now + 20, in_scope=True, prompt_hash="a4")
    d = cg.decide(st, now + 30, in_scope=True, prompt_hash="a5")
    rows.append(("3 burst (3 in 10m)", d.action.value, d.reason,
                 f"toll={d.toll_seconds}s"))

    # 4. sidecar escalation: P-15 leap -> park in CHECKPOINT? (mode floor: collapse)
    v = fuse(topic_score=0.85, function_code="P-15", confidence=0.8)
    d = cg.decide(st, now + 60, in_scope=None, sidecar_verdict=v.to_dict(),
                  prompt_hash="a6")
    rows.append(("4 sidecar leap P-15", d.action.value, d.reason,
                 "escalate=" + str(v.escalate)))

    # 5. budget exhausted
    st.prompt_budget_used = st.prompt_budget_limit
    d = cg.decide(st, now + 90, in_scope=True, prompt_hash="a7")
    rows.append(("5 budget exhausted", d.action.value, d.reason, ""))

    # 6. thread interlock
    ok, reason, ev = cg.open_thread(st, "t1", "chatgpt", now)
    ok2, reason2, ev2 = cg.open_thread(st, "t2", "chatgpt", now + 1)
    rows.append(("6 open thread t1", "allowed" if ok else "refused", reason, ""))
    rows.append(("7 open thread t2 (t1 open)", "allowed" if ok2 else "refused",
                 reason2, ""))

    # 7. debt anti-windup under FULL_LOCK
    st.mode = cg.GuardMode.FULL_LOCK
    before = st.debt.value
    cg.accrue_debt(st)
    cg.accrue_debt(st)
    rows.append(("8 debt under FULL_LOCK", "frozen" if st.debt.value == before
                 else "windup!", f"{st.debt.value}", "anti-windup"))

    # 8. Schmitt: breach tightens immediately, clean streak relaxes later
    st2 = cg.GuardState(mode=cg.GuardMode.CHECKPOINT, taper_index=1)
    cg.schmitt_step(st2, breach=True)
    tightened = st2.mode
    for _ in range(3):
        cg.schmitt_step(st2, breach=False)
    rows.append(("9 Schmitt breach", tightened.value, "immediate up", ""))
    rows.append(("10 Schmitt clean x3", st2.mode.value, "one step down", ""))

    # sidecar store + retention
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    store = ContentStore(tmp.name)
    cid = store.put_text("secret-ish held prompt", kind="held_prompt",
                         thread_id="t1", site="chatgpt", ttl_days=14)
    store.close()
    try:
        os.unlink(tmp.name)
    except Exception:
        pass
    rows.append(("11 content store", f"row {cid}", "ttl 14d", "outside chain"))

    w = max(len(r[0]) for r in rows)
    print(f"{'scenario':<{w}}  action/status   reason          detail")
    print("-" * (w + 60))
    for r in rows:
        print(f"{r[0]:<{w}}  {r[1]:<13} {r[2]:<15} {r[3]}")
    print()
    print(cg.snapshot_for_digest(st, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
