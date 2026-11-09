#!/usr/bin/env python3
"""Surface lint: the design laws applied to files, not just code
(operator toolkit #8, pre-commit companion).

Checks:
  L-1/L-2 — the wall page (extension/blocked.html, blocked.js) must
            carry no affordances (links, buttons, forms, onclick) and
            no forbidden/coaching phrases.
  L-2/L-7 — no shame, praise, or softening phrases on any shipped
            user-facing surface (extension pages, CLI-facing markdown
            templates rendered at build time are checked via their
            source phrase lists in tests).
  version pins — extension manifest version matches dhriti.__version__.

Exit code 0 = clean; 1 = violations (printed, one per line).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# L-2: judging the person (either direction) is forbidden.
FORBIDDEN_PHRASES = (
    "you're lazy", "you failed", "you are lazy", "shame on",
    "you finally", "proud of you", "you're doing great",
    "you are doing great", "bad user", "good user",
)

# L-7: cushioning the record is forbidden (the record is faced).
SOFTENING_PHRASES = (
    "it's okay", "it is okay", "no pressure", "no worries",
    "take your time", "we've all been there", "everyone does this",
    "don't worry", "you're doing", "you are doing",
    "great job", "well done", "congrat", "awesome", "amazing",
    "good job", "nice work", "keep going", "you've got this",
    "almost there", "one step at a time", "progress is progress",
    "small steps", "look on the bright side", "silver lining",
)

AFFORDANCE_RE = re.compile(
    r"<(?:a\b[^>]*href|button|form|input\b[^>]*type=[\"']submit)",
    re.IGNORECASE)


def lint_file(path: Path, phrases) -> list:
    problems = []
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for phrase in phrases:
        if phrase.lower() in lowered:
            problems.append(f"{path}: forbidden phrase {phrase!r}")
    if path.suffix == ".html":
        if AFFORDANCE_RE.search(text):
            problems.append(f"{path}: affordance found (L-1: the wall "
                            "must not offer a click)")
        if "onclick" in lowered:
            problems.append(f"{path}: onclick handler (L-1)")
    return problems


def lint_manifest_versions() -> list:
    problems = []
    manifest = ROOT / "extension" / "manifest.json"
    init = ROOT / "dhriti" / "__init__.py"
    if manifest.exists() and init.exists():
        try:
            mv = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        except Exception as exc:
            return [f"{manifest}: unreadable ({exc})"]
        m = re.search(r'__version__\s*=\s*"([^"]+)"',
                      init.read_text(encoding="utf-8"))
        pv = m.group(1) if m else "?"
        if mv != pv:
            problems.append(
                f"version pin mismatch: extension/manifest.json {mv} != "
                f"dhriti/__init__.py {pv}")
    return problems


def main() -> int:
    problems = []
    wall_dir = ROOT / "extension"
    for name in ("blocked.html", "blocked.js", "blocked.css",
                 "background.js", "suppress.js", "config.js"):
        target = wall_dir / name
        if target.exists():
            problems += lint_file(target, FORBIDDEN_PHRASES)
            problems += lint_file(target, SOFTENING_PHRASES)
    problems += lint_manifest_versions()
    for problem in problems:
        print(problem)
    if problems:
        print(f"lint_surfaces: {len(problems)} violation(s)")
        return 1
    print("lint_surfaces: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
