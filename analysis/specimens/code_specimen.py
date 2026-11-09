#!/usr/bin/env python3
"""Code a raw AI-chat export into the Dhriti normalized event vocabulary.

This is Phase 2 methodology, run BEFORE any observation stack exists:
the builder already produces specimens (saved chat exports). Coding one
by hand and validating it against the vocabulary is (a) the project's
first real baseline data, (b) a stress test of the event vocabulary
itself — a vocabulary that cannot express Specimen 001 is wrong, and
(c) the cold-state analysis workflow the daemon will later automate.

Usage:
    python3 code_specimen.py specimen_001_turns.json \
        --out-dir SPECIMEN_001 [--session-id SPECIMEN-001]

Input: a coded turns file (see specimen_001_turns.json for the schema;
the turn segmentation is manual because raw exports are not
machine-delimited — that honesty is recorded in the file itself).

Output:
    <out-dir>/events.csv      rows in the normalized event vocabulary
    <out-dir>/summary.json    computed structural facts (observed)
                              plus the coder's inferences (marked)

Method rules (the constitution, applied to ourselves):
  * observed  = turn boundaries, offer counts, affordance endings,
                self-diagnosis parentheses, topic switches. Structural.
  * inferred  = topic labels, phase labels, took_offer judgements.
                Stored in inference_payload, NEVER in observed_payload.
  * evidence  = counted from the source; a chat produces zero
                MACHINE_CHECKED events by construction.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Event types used here. The pair (ai_suggestion_offered /
# ai_suggestion_taken) is the Specimen-001 addition to the vocabulary:
# the springboard is an interaction pattern, not a website.
OBSERVED_EVENT_TYPES = {
    "user_turn": "one user message in the export",
    "ai_turn": "one assistant message (recorded on the row that follows)",
    "ai_suggestion_offered": "assistant ended its turn by proposing "
                              "follow-up directions",
    "ai_suggestion_taken": "next user turn continued a proposed direction",
    "ai_affordance_tail": "assistant turn ended with any next-interaction "
                          "affordance (including refusals that end with "
                          "'come back and tell me ...')",
}
INFERRED_ONLY = {"topic_label", "phase_label"}


def load_turns(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for turn in data["turns"]:
        for key in ("i", "phase", "topic", "excerpt", "ai_offers",
                    "ai_ends_with_affordance", "took_offer",
                    "self_diagnosis"):
            if key not in turn:
                raise SystemExit(f"turn missing key {key}: {turn}")
    return data


def code_events(data: dict, session_id: str) -> list:
    """Expand turns into normalized event rows (vocabulary fields)."""
    rows = []
    seq = 0
    for turn in data["turns"]:
        seq += 1
        rows.append({
            "event_id": f"{session_id}-u{turn['i']:03d}",
            "occurred_at_utc": "UNKNOWN",  # export has no timestamps (D-040)
            "session_id": session_id,
            "source_adapter": "manual_coding",
            "event_type": "user_turn",
            "parent_event_id": (f"{session_id}-u{turn['i']-1:03d}"
                                if turn["i"] > 1 else ""),
            "observed_payload": json.dumps({
                "excerpt": turn["excerpt"],
                "self_diagnosis_parenthetical": turn["self_diagnosis"],
            }, ensure_ascii=False),
            "inference_payload": json.dumps({
                "topic_label": turn["topic"],
                "phase_label": turn["phase"],
            }, ensure_ascii=False),
            "model_id_or_rule_version": "manual-v1",
            "action_taken": "none (no system existed)",
            "telemetry_quality": "MANUAL",
        })
        if turn["ai_offers"] > 0:
            seq += 1
            rows.append({
                "event_id": f"{session_id}-a{turn['i']:03d}-offer",
                "occurred_at_utc": "UNKNOWN",
                "session_id": session_id,
                "source_adapter": "manual_coding",
                "event_type": "ai_suggestion_offered",
                "parent_event_id": f"{session_id}-u{turn['i']:03d}",
                "observed_payload": json.dumps(
                    {"count": turn["ai_offers"]}),
                "inference_payload": "{}",
                "model_id_or_rule_version": "manual-v1",
                "action_taken": "none (no system existed)",
                "telemetry_quality": "MANUAL",
            })
        if turn["ai_ends_with_affordance"]:
            seq += 1
            rows.append({
                "event_id": f"{session_id}-a{turn['i']:03d}-afford",
                "occurred_at_utc": "UNKNOWN",
                "session_id": session_id,
                "source_adapter": "manual_coding",
                "event_type": "ai_affordance_tail",
                "parent_event_id": f"{session_id}-u{turn['i']:03d}",
                "observed_payload": json.dumps(
                    {"present": True,
                     "note": "turn ends by proposing the next interaction "
                             "(question, bullet list, or return-prompt)"}),
                "inference_payload": "{}",
                "model_id_or_rule_version": "manual-v1",
                "action_taken": "none (no system existed)",
                "telemetry_quality": "MANUAL",
            })
        if turn["took_offer"]:
            seq += 1
            rows.append({
                "event_id": f"{session_id}-u{turn['i']:03d}-took",
                "occurred_at_utc": "UNKNOWN",
                "session_id": session_id,
                "source_adapter": "manual_coding",
                "event_type": "ai_suggestion_taken",
                "parent_event_id": f"{session_id}-a{turn['i']-1:03d}-offer"
                                   if turn["i"] > 1 else "",
                "observed_payload": json.dumps({"continued": True}),
                "inference_payload": json.dumps(
                    {"basis": "coder judgement: next turn follows a "
                              "proposed direction"}),
                "model_id_or_rule_version": "manual-v1",
                "action_taken": "none (no system existed)",
                "telemetry_quality": "MANUAL",
            })
    return rows


def summarize(data: dict) -> dict:
    turns = data["turns"]
    offers = sum(t["ai_offers"] for t in turns)
    early = [t for t in turns if t["phase"] == "curiosity_chain"]
    early_offers = sum(t["ai_offers"] for t in early)
    early_taken = sum(1 for t in early if t["took_offer"])
    phases = {}
    for t in turns:
        phases[t["phase"]] = phases.get(t["phase"], 0) + 1
    return {
        "specimen_id": data["specimen_id"],
        "user_turns": len(turns),
        "ai_turns_assumed": len(turns),
        "topics_touched": len({t["topic"] for t in turns}),
        "topic_chain": [t["topic"] for t in turns],
        "phases": phases,
        "ai_suggestion_offers_total": offers,
        "offers_during_curiosity_chain": early_offers,
        "uptake_during_curiosity_chain": {
            "taken": early_taken, "of": len(early),
            "rate": round(early_taken / len(early), 3) if early else None,
        },
        "ai_turns_ending_with_affordance": sum(
            1 for t in turns if t["ai_ends_with_affordance"]),
        "affordance_rate": round(sum(
            1 for t in turns if t["ai_ends_with_affordance"]) /
            len(turns), 3),
        "turns_with_self_diagnosis": sum(1 for t in turns
                                         if t["self_diagnosis"]),
        "self_diagnosis_rate": round(sum(
            1 for t in turns if t["self_diagnosis"]) / len(turns), 3),
        "evidence_events": data.get("evidence_events", {}),
        "evidence_events_total": sum(
            data.get("evidence_events", {}).values()),
        "duration": "UNKNOWN (export carries no timestamps)",
        "task_context": data.get("task_context", ""),
        "note": "offer/affordance counts are OBSERVED structure; topic and "
                "phase labels are the coder's INFERERENCE (D-014: labels "
                "never become policy).",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("turns_json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--session-id", default="SPECIMEN-001")
    args = parser.parse_args()

    data = load_turns(Path(args.turns_json))
    rows = code_events(data, args.session_id)
    summary = summarize(data)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "events.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary_path = out / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"events: {len(rows)} -> {csv_path}")
    print(f"summary -> {summary_path}")
    print(json.dumps({k: summary[k] for k in (
        "user_turns", "topics_touched", "ai_suggestion_offers_total",
        "affordance_rate", "self_diagnosis_rate",
        "evidence_events_total")}, indent=2))


if __name__ == "__main__":
    main()
