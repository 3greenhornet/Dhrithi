"""Dhriti Agent-Free Capability Block & Closed-World Drill Engine.

Addresses the core placement readiness gap identified in operator research:
- Closes the world: Blocks AI-chat distraction and tool-building avoidance (D-035).
- Provides unaided practice on core DSA (e.g., Palindrome, Two Sum) and
  Quantitative Aptitude (e.g., Time & Work, Speed & Distance).
- Machine-checks solutions locally without generative AI hallucinations.
- Valid solutions emit MACHINE_CHECKED evidence directly to the daily contract,
  satisfying targets_met (The Day Can Be Won) and earning project hours.
- Follows L-2 Honesty: accept_nonzero_exit records honest attempts without punishment.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any, Callable, Dict, List, Optional, Tuple


CAPABILITY_DRILL_BANK = [
    {
        "id": "palindrome",
        "title": "Palindrome Verification (String & Number)",
        "category": "dsa_basic",
        "subtopic": "Strings & Pointers",
        "problem_statement": (
            "Implement a function `is_palindrome(val)` that checks if a string or integer "
            "reads the same forwards and backwards. For strings, ignore non-alphanumeric characters "
            "and casing (e.g., 'A man a plan a canal Panama' is True). Negative numbers are False."
        ),
        "entry_point": "is_palindrome",
        "scaffold": '''def is_palindrome(val) -> bool:
    """Check if string or integer is a palindrome unaided."""
    # Write your solution below:
    pass
''',
        "test_cases": [
            ("racecar", True),
            ("hello", False),
            ("A man, a plan, a canal: Panama", True),
            (121, True),
            (-121, False),
            (10, False),
            ("0P", False),
            ("", True),
        ]
    },
    {
        "id": "time_and_work",
        "title": "Quantitative Aptitude: Time and Work",
        "category": "quant_aptitude",
        "subtopic": "Reciprocal Rate Mathematics",
        "problem_statement": (
            "A can complete a piece of work in `a_days` and B in `b_days`. "
            "If they work together for `worked_days`, calculate the fraction of work "
            "completed and the fraction remaining. Return as tuple (completed, remaining) "
            "with both rounded to 4 decimal places. If finished completely, remaining is 0.0."
        ),
        "entry_point": "remaining_work",
        "scaffold": '''def remaining_work(a_days: float, b_days: float, worked_days: float) -> tuple[float, float]:
    """Calculate (completed_fraction, remaining_fraction) unaided."""
    # Write your solution below:
    pass
''',
        "test_cases": [
            ((12.0, 18.0, 4.0), (0.5556, 0.4444)),
            ((10.0, 15.0, 5.0), (0.8333, 0.1667)),
            ((20.0, 30.0, 12.0), (1.0, 0.0)),
            ((6.0, 12.0, 2.0), (0.5, 0.5)),
        ]
    },
    {
        "id": "two_sum",
        "title": "Two Sum (Array Indices)",
        "category": "dsa_basic",
        "subtopic": "Hash Map & Complements",
        "problem_statement": (
            "Given a list of integers `nums` and an integer `target`, return the zero-based indices "
            "of the two numbers such that they add up to `target`. You may assume that each input "
            "has exactly one solution, and you may not use the same element twice. Return [idx1, idx2]."
        ),
        "entry_point": "two_sum",
        "scaffold": '''def two_sum(nums: list[int], target: int) -> list[int]:
    """Find two indices whose values sum to target unaided."""
    # Write your solution below:
    pass
''',
        "test_cases": [
            (([2, 7, 11, 15], 9), [0, 1]),
            (([3, 2, 4], 6), [1, 2]),
            (([3, 3], 6), [0, 1]),
            (([1, 5, 8, 3, 12], 15), [3, 4]),
        ]
    },
    {
        "id": "speed_distance",
        "title": "Quantitative Aptitude: Speed, Time & Distance",
        "category": "quant_aptitude",
        "subtopic": "Relative Speed & Unit Conversions",
        "problem_statement": (
            "A train of length `train_len_meters` passes a stationary pole in `seconds`. "
            "Calculate the speed of the train in km/h. Return as float rounded to 2 decimal places."
        ),
        "entry_point": "train_speed_kmh",
        "scaffold": '''def train_speed_kmh(train_len_meters: float, seconds: float) -> float:
    """Calculate train speed in km/h unaided."""
    # Write your solution below:
    pass
''',
        "test_cases": [
            ((150.0, 9.0), 60.0),
            ((200.0, 10.0), 72.0),
            ((100.0, 6.0), 60.0),
            ((300.0, 15.0), 72.0),
        ]
    }
]


class CapabilityError(Exception):
    """Raised when capability block operations encounter validation or execution failures."""
    pass


class CapabilityService:
    def __init__(self, db=None, ledger=None, home: Optional[Path] = None):
        self.db = db
        self.ledger = ledger
        self.home = home or Path.home() / ".dhriti"

    def list_drills(self) -> List[Dict[str, Any]]:
        """List all available capability drills."""
        out = []
        for d in CAPABILITY_DRILL_BANK:
            out.append({
                "id": d["id"],
                "title": d["title"],
                "category": d["category"],
                "subtopic": d["subtopic"],
                "problem_statement": d["problem_statement"],
                "entry_point": d["entry_point"]
            })
        return out

    def get_drill(self, drill_id: str) -> Dict[str, Any]:
        """Fetch drill definition by ID."""
        for d in CAPABILITY_DRILL_BANK:
            if d["id"] == drill_id:
                return d
        raise CapabilityError(f"Unknown capability drill ID: {drill_id}")

    def start_drill(
        self,
        drill_id: str,
        out_dir: Optional[Path] = None,
        duration_min: int = 25
    ) -> Dict[str, Any]:
        """Initiates an agent-free capability block and generates scaffold file."""
        drill = self.get_drill(drill_id)
        
        target_dir = out_dir or (self.home / "capability_drills")
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{drill_id}.py"

        # Scaffold file content with instruction header
        content = (
            f'"""\n'
            f'DHRITI AGENT-FREE CAPABILITY BLOCK ({duration_min} minutes closed-world practice)\n'
            f'Topic: {drill["title"]}\n'
            f'Category: {drill["category"]} ({drill["subtopic"]})\n\n'
            f'PROBLEM STATEMENT:\n{drill["problem_statement"]}\n\n'
            f'RULES (L-12 / L-13):\n'
            f'- Solve unaided. No AI agents, LLM prompts, or copy-pasting.\n'
            f'- Run local test via: dhriti capability check {drill_id} {file_path.name}\n'
            f'"""\n\n'
            f'{drill["scaffold"]}\n'
        )

        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")

        # Record to ledger
        if self.ledger:
            self.ledger.record(
                "capability_block_started",
                observed={
                    "drill_id": drill_id,
                    "title": drill["title"],
                    "duration_min": duration_min,
                    "scaffold_path": str(file_path)
                }
            )

        return {
            "ok": True,
            "drill_id": drill_id,
            "title": drill["title"],
            "file_path": str(file_path),
            "duration_min": duration_min,
            "instructions": f"Open {file_path} and solve unaided. Verify with: dhriti capability check {drill_id}"
        }

    def verify_drill(
        self,
        drill_id: str,
        code_or_file: str,
        scope_date: Optional[str] = None,
        accept_nonzero_exit: bool = True
    ) -> Dict[str, Any]:
        """Machine-checks drill solution against strict test vectors and logs proof."""
        drill = self.get_drill(drill_id)
        entry_point = drill["entry_point"]
        test_cases = drill["test_cases"]

        # 1. Obtain code string
        p = Path(code_or_file)
        if p.exists() and p.is_file():
            code_text = p.read_text(encoding="utf-8")
        else:
            code_text = code_or_file

        if not code_text or not code_text.strip():
            raise CapabilityError("No solution code provided to verify.")

        code_hash = hashlib.sha256(code_text.encode("utf-8")).hexdigest()

        # 2. Execute in restricted namespace
        local_env: Dict[str, Any] = {}
        try:
            exec(code_text, {}, local_env)
        except Exception as e:
            if self.ledger:
                self.ledger.record(
                    "capability_drill_attempted",
                    observed={
                        "drill_id": drill_id,
                        "error": str(e),
                        "code_hash": code_hash
                    }
                )
            if accept_nonzero_exit:
                return {
                    "ok": True,
                    "verified": False,
                    "passed_tests": 0,
                    "total_tests": len(test_cases),
                    "code_hash": code_hash,
                    "message": f"Syntax or execution error: {e}. Attempt logged (L-2)."
                }
            raise CapabilityError(f"Execution error in drill code: {e}")

        func = local_env.get(entry_point)
        if not callable(func):
            raise CapabilityError(f"Function `{entry_point}` was not found or is not callable in submitted code.")

        # 3. Test verification
        passed_count = 0
        failures = []

        for inp, expected in test_cases:
            try:
                if isinstance(inp, tuple):
                    actual = func(*inp)
                else:
                    actual = func(inp)

                # Comparison logic
                match = False
                if isinstance(expected, float):
                    match = abs(actual - expected) < 1e-4
                elif isinstance(expected, tuple) and all(isinstance(x, float) for x in expected):
                    match = len(actual) == len(expected) and all(abs(a - e) < 1e-3 for a, e in zip(actual, expected))
                else:
                    match = (actual == expected)

                if match:
                    passed_count += 1
                else:
                    failures.append({
                        "input": str(inp),
                        "expected": str(expected),
                        "actual": str(actual)
                    })
            except Exception as ex:
                failures.append({
                    "input": str(inp),
                    "expected": str(expected),
                    "error": str(ex)
                })

        total = len(test_cases)
        is_verified = (passed_count == total)
        today = scope_date or dt.date.today().isoformat()
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        # 4. Record to ledger and database evidence
        if is_verified:
            if self.ledger:
                self.ledger.record(
                    "capability_drill_verified",
                    observed={
                        "drill_id": drill_id,
                        "title": drill["title"],
                        "passed_tests": f"{passed_count}/{total}",
                        "code_hash": code_hash,
                        "date": today
                    }
                )
            
            # Map into contract evidence table if database available
            if self.db:
                self._record_contract_evidence(drill, code_hash, today, now)

            return {
                "ok": True,
                "verified": True,
                "passed_tests": passed_count,
                "total_tests": total,
                "code_hash": code_hash,
                "message": f"Drill verified! All {total} test cases passed without error."
            }
        else:
            if self.ledger:
                self.ledger.record(
                    "capability_drill_attempted",
                    observed={
                        "drill_id": drill_id,
                        "passed_tests": f"{passed_count}/{total}",
                        "code_hash": code_hash,
                        "date": today
                    }
                )
            return {
                "ok": True,
                "verified": False,
                "passed_tests": passed_count,
                "total_tests": total,
                "failures": failures,
                "code_hash": code_hash,
                "message": f"{passed_count}/{total} test cases passed. Attempt logged honestly (L-2)."
            }

    def _record_contract_evidence(
        self,
        drill: Dict[str, Any],
        code_hash: str,
        today: str,
        now: str
    ) -> None:
        """Inserts MACHINE_CHECKED evidence row linking to active contract target."""
        row = self.db.query_one(
            "SELECT id, payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
            (today,)
        )
        if not row:
            return

        contract_id = row["id"]
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            return

        targets = payload.get("targets", [])
        if not targets:
            return

        # Find matching target (placement, capability, dsa, aptitude, learning, or first target)
        matched_target_id = None
        target_label = "Placement Drill"
        for t in targets:
            lbl = (t.get("label") or "").lower()
            if any(k in lbl for k in ("capability", "drill", "dsa", "aptitude", "placement", "leetcode", "practice")):
                matched_target_id = t.get("id")
                target_label = t.get("label", target_label)
                break
        if not matched_target_id:
            matched_target_id = targets[0].get("id")
            target_label = targets[0].get("label", target_label)

        # Check if session exists for today
        sess = self.db.query_one(
            "SELECT s.id FROM session s JOIN day d ON s.day_id=d.id WHERE d.date=? AND s.state='ACTIVE' LIMIT 1",
            (today,)
        )
        if not sess:
            sess = self.db.query_one(
                "SELECT s.id FROM session s JOIN day d ON s.day_id=d.id WHERE d.date=? ORDER BY s.started_at DESC LIMIT 1",
                (today,)
            )
        session_id = sess["id"] if sess else f"cap-sess-{secrets.token_hex(4)}"

        detail_json = json.dumps({
            "target_id": matched_target_id,
            "target_label": target_label,
            "drill_id": drill["id"],
            "drill_title": drill["title"],
            "sha256": code_hash,
            "verified_at": now,
            "method": "capability_block_test_run"
        })

        try:
            self.db.insert("evidence", {
                "id": f"ev-cap-{secrets.token_hex(6)}",
                "session_id": session_id,
                "class": "MACHINE_CHECKED",
                "kind": "capability_drill",
                "submitted_at": now,
                "detail_json": detail_json,
                "verdict": "ACCEPTED",
                "verdict_reason": f"Verified machine check for {drill['title']}",
                "checked_at": now
            })
        except Exception:
            pass

        if self.ledger:
            self.ledger.record(
                "target_claimed",
                observed={
                    "target_id": matched_target_id,
                    "target_label": target_label,
                    "drill_id": drill["id"],
                    "code_hash": code_hash,
                    "date": today
                }
            )
            self.ledger.record(
                "learning_proof_verified",
                observed={
                    "contract_id": contract_id,
                    "target_id": matched_target_id,
                    "target_label": target_label,
                    "proof_hash": code_hash,
                    "date": today
                }
            )
