#!/usr/bin/env python3
"""Conversation mining, --patterns mode (v0.7.0 Part 3 s3.15 + s4.20).

The ENA+TNA functionality, cold-state, on specimen data. No live
classifier: the P-codes are the analyst's hand coding (the taxonomy is
authored, not discovered - Part 4 s2.4 stage 3); this module computes
the structure over them:

  * the turn-type distribution (which P-codes appear, by side)
  * the transition network (which P-code follows which, with counts)
  * the top variants (the modal n-grams of the P-code sequence)
  * the user-probe named patterns (s4.20: elaborations past
    completion, corrections of the AI's framing, show-and-tell,
    conversation-for-its-own-sake)

The rule lists (stage 1 of the label production) live here too, so
the taxonomy has ONE canonical home in the analysis tree. Rules are
structural only: punctuation, phrase lists, token shape (L-4).

Usage:
    python3 conversation_mining.py SPECIMEN_002/specimen_002_turns.json \
        --patterns
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# -- the taxonomy (Part 4 s2.1) -------------------------------------------
# AI-side: P-11..P-16. User-side: P-19..P-22. P-17/P-18 reserved.
P_CODE_NAMES = {
    "P-11": ("the Affordance Tail", "AI"),
    "P-12": ("Completion Deflection", "AI"),
    "P-13": ("the Mirror of Meta", "AI"),
    "P-14": ("the Scope Invitation", "AI"),
    "P-15": ("the Topic Leap", "AI"),
    "P-16": ("Structural Endlessness", "AI"),
    "P-19": ("Show-and-Tell", "user"),
    "P-20": ("Elaboration Past Completion", "user"),
    "P-21": ("Conversation for Its Own Sake", "user"),
    "P-22": ("Task-Anchor Drift", "user"),
}

# -- stage-1 rule lists (Part 4 s2.4) --------------------------------------
# Structural markers only. They catch most turns with zero ambiguity;
# the rest is hand coding (stage 3). No content reading.
COMPLETION_SIGNALS = [
    "good", "done", "works", "solved", "got it", "that's it",
    "perfect", "yes", "correct", "exactly", "right",
]
OFFER_PHRASES = [
    "would you like", "shall i", "let me know", "can i",
    "do you want", "i can also", "would you like me to",
]
ELABORATION_MARKERS = [
    "also", "plus", "one more", "you forgot", "what about",
    "and another",
]
META_PHRASES = [
    "eh?", "right?", "isn't it", "hmm", "i am back",
    "one more problem",
]
SHOW_AND_TELL_MARKERS = [
    "i downloaded", "i also used", "i typed in", "i installed",
]


def _norm(text: str) -> str:
    return " " + (text or "").lower().replace("\n", " ") + " "


_WORD_RE = re.compile(r"[a-z']+")


def _words(text: str) -> set:
    """Punctuation-stripped word tokens ('good.' -> 'good')."""
    return set(_WORD_RE.findall((text or "").lower()))


def _has_completion_signal(text: str) -> bool:
    words = _words(text)
    lowered = _norm(text)
    return bool(
        words & {"good", "done", "works", "solved", "correct",
                 "exactly", "perfect"}
        or "got it" in lowered or "that's it" in lowered)


def rule_labels(turn_text: str, side: str) -> list:
    """Stage-1 rule classification of one turn. Structural only; the
    honest claim is 'these markers are present', never 'this turn
    means X' (that is the hand coding's job)."""
    text = _norm(turn_text)
    labels = []
    if side == "AI":
        if text.strip().endswith("?") or any(
                p in text for p in OFFER_PHRASES):
            labels.append("P-11")
        if any(p in text for p in (
                "would you like me to", "shall i", "i can also")):
            labels.append("P-14")
    else:
        if any(p in text for p in SHOW_AND_TELL_MARKERS):
            labels.append("P-19")
        has_completion = _has_completion_signal(turn_text)
        has_elaboration = any(
            p in text for p in ELABORATION_MARKERS)
        if has_elaboration and (has_completion or True):
            # the visible half of P-20 is the marker; whether it is
            # 'past completion' needs the sequence (hand coding)
            labels.append("P-20*")
        if any(p in text for p in META_PHRASES) \
                or text.strip().endswith("eh?") \
                or text.strip().endswith("right?"):
            labels.append("P-21")
    return labels


# -- loading ---------------------------------------------------------------

def load_specimen(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    turns = data.get("turns", [])
    for turn in turns:
        if "p_codes" not in turn or "ai_p_codes" not in turn:
            raise SystemExit(
                f"turn {turn.get('i')} carries no P-codes; "
                "--patterns needs a P-coded specimen "
                "(see specimen_002_turns.json)")
    return data


# -- the three computations -------------------------------------------------

def distribution(data: dict) -> dict:
    """The turn-type distribution: which P-codes appear, by side."""
    counts = {"AI": Counter(), "user": Counter()}
    for turn in data["turns"]:
        for code in turn.get("p_codes", []):
            counts["user"][code] += 1
        for code in turn.get("ai_p_codes", []):
            counts["AI"][code] += 1
    return {
        "user_side": dict(counts["user"].most_common()),
        "ai_side": dict(counts["AI"].most_common()),
    }


def _flat_sequence(data: dict) -> list:
    """The P-code sequence, turn by turn (multi-code turns keep their
    coded order). The unit of the transition network and variants."""
    seq = []
    for turn in data["turns"]:
        seq.extend(turn.get("p_codes", []))
        seq.extend(turn.get("ai_p_codes", []))
    return seq


def transition_network(data: dict) -> dict:
    """TNA: directed edges P-code -> P-code with counts, plus the
    dominant user->AI and AI->user edge classes (the loop detector)."""
    seq = _flat_sequence(data)
    edges = Counter(zip(seq, seq[1:]))
    user_codes = {c for c, (_, side) in P_CODE_NAMES.items()
                  if side == "user"}
    ai_codes = {c for c, (_, side) in P_CODE_NAMES.items()
                if side == "AI"}
    user_to_ai = sum(n for (a, b), n in edges.items()
                     if a in user_codes and b in ai_codes)
    ai_to_user = sum(n for (a, b), n in edges.items()
                     if a in ai_codes and b in user_codes)
    return {
        "edges": {f"{a} -> {b}": n for (a, b), n in
                  sorted(edges.items(), key=lambda kv: -kv[1])},
        "user_to_ai_transitions": user_to_ai,
        "ai_to_user_transitions": ai_to_user,
    }


def top_variants(data: dict, n: int = 3, limit: int = 5) -> dict:
    """The modal n-grams of the P-code sequence (conversation
    mining's 'variants' - the frequent traces). The loop is visible
    as the top variant."""
    seq = _flat_sequence(data)
    grams = Counter(zip(*[seq[i:] for i in range(n)]))
    variants = {" -> ".join(g): c for g, c in
                grams.most_common(limit)}
    return {
        "n": n,
        "top_variants": variants,
        "full_trace": seq,
    }


# -- s4.20: the user-probe named patterns -----------------------------------

def user_probe_named(data: dict) -> dict:
    """The user's own patterns, named, with the s4.20 closing line.
    Counts are of user turns carrying the code (hand coding), plus
    the corrections-of-framing count (P-21 turns that correct the AI
    rather than joke - distinguished by the p_code_notes)."""
    turns = data["turns"]
    elaborations = sum(1 for t in turns if "P-20" in t["p_codes"])
    show_and_tell = sum(1 for t in turns if "P-19" in t["p_codes"])
    for_its_own_sake = sum(1 for t in turns
                           if "P-21" in t["p_codes"])
    corrections = sum(
        1 for t in turns if "P-21" in t["p_codes"]
        and "correction" in (t.get("p_code_notes") or ""))
    drift = sum(1 for t in turns if "P-22" in t["p_codes"])
    lines = [
        "User-probe patterns this week:",
        f"  {elaborations} elaborations past completion "
        "('also', 'one more', 'you forgot')",
        f"  {corrections} corrections of the AI's framing",
        f"  {show_and_tell} show-and-tell "
        "(achievement offered before being asked)",
        f"  {for_its_own_sake} conversation-for-its-own-sake "
        "(joke, rhetorical question)",
        f"  {drift} task-anchor drift",
        "You named none of these as probes in the review.",
    ]
    return {
        "counts": {
            "elaborations_past_completion": elaborations,
            "corrections_of_framing": corrections,
            "show_and_tell": show_and_tell,
            "conversation_for_its_own_sake": for_its_own_sake,
            "task_anchor_drift": drift,
        },
        "text": "\n".join(lines),
    }


# -- the documented counts cross-check ---------------------------------------

def documented_counts(data: dict) -> dict:
    """The audit's summary numbers (completion signals 2, AI
    deflections 4, user elaborations 5, task-anchor drift 1),
    recomputed from the coding. Completion signals count user turns
    whose text carries a completion marker (structural, rule-based);
    AI deflections count the P-12 deflection turns; user elaborations
    and task-anchor drift count the P-coded user turns."""
    completions = 0
    for turn in data["turns"]:
        if _has_completion_signal(turn["excerpt"]):
            completions += 1
    return {
        "completion_signals": completions,
        "ai_deflections": sum(
            1 for t in data["turns"] if "P-12" in t["ai_p_codes"]),
        "user_elaborations": sum(
            1 for t in data["turns"] if "P-20" in t["p_codes"]),
        "task_anchor_drift": sum(
            1 for t in data["turns"] if "P-22" in t["p_codes"]),
    }


def build_patterns(data: dict) -> str:
    out = [f"# Conversation patterns - {data['specimen_id']}",
           f"provenance: see the turns file",
           ""]
    dist = distribution(data)
    out.append("## Turn-type distribution")
    out.append("user side: " + ", ".join(
        f"{code} x{n}" for code, n in dist["user_side"].items()))
    out.append("AI side: " + ", ".join(
        f"{code} x{n}" for code, n in dist["ai_side"].items()))
    out.append("")
    net = transition_network(data)
    out.append("## Transition network (which P-code follows which)")
    for edge, n in list(net["edges"].items())[:10]:
        out.append(f"  {edge}: {n}")
    out.append(f"user->AI transitions: {net['user_to_ai_transitions']}; "
               f"AI->user transitions: {net['ai_to_user_transitions']}")
    out.append("")
    var = top_variants(data)
    out.append(f"## Top variants (modal {var['n']}-grams)")
    for variant, n in var["top_variants"].items():
        out.append(f"  {variant}: {n}")
    out.append("")
    out.append("## " + user_probe_named(data)["text"])
    out.append("")
    dc = documented_counts(data)
    out.append("## The documented counts, recomputed")
    for key, value in dc.items():
        out.append(f"  {key}: {value}")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("turns_json")
    parser.add_argument("--patterns", action="store_true",
                        help="the turn-type distribution, transition "
                             "network, top variants, user-probe "
                             "named patterns")
    args = parser.parse_args()
    if not args.patterns:
        parser.print_help()
        return 0
    data = load_specimen(Path(args.turns_json))
    print(build_patterns(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
