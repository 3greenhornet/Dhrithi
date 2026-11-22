"""Dhriti Placement Online Assessment (OA) Simulator (Package L3).

Delivers 10 daily drill questions covering:
1. Quantitative Aptitude (Work, Time & Speed, Permutations, Probability)
2. Logical & Analytical Reasoning (Syllogisms, Arrangements, Sequences)
3. Core Computer Science (Java, Collections, Concurrency, DSA Big-O, SQL, OS)

Evaluates performance with absolute honesty (L-2), logging verified proofs to the ledger.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any, Dict, List, Optional


DRILL_QUESTION_BANK = [
    # Quantitative Aptitude
    {
        "id": "oa-quant-1",
        "category": "Quantitative Aptitude",
        "subtopic": "Time & Work",
        "question": "A can finish a work in 12 days and B in 18 days. If they work together for 4 days, what fraction of work is left?",
        "options": ["A) 5/9", "B) 4/9", "C) 1/3", "D) 7/18"],
        "answer": "B",
        "explanation": "A's 1 day work = 1/12; B's 1 day work = 1/18. Combined 1 day work = 5/36. In 4 days: 4 * (5/36) = 20/36 = 5/9. Work remaining = 1 - 5/9 = 4/9."
    },
    {
        "id": "oa-quant-2",
        "category": "Quantitative Aptitude",
        "subtopic": "Speed, Time & Distance",
        "question": "A train 150m long passes an electric pole in 9 seconds. What is the speed of the train in km/h?",
        "options": ["A) 50 km/h", "B) 60 km/h", "C) 54 km/h", "D) 72 km/h"],
        "answer": "B",
        "explanation": "Speed = Distance / Time = 150 / 9 = 50/3 m/s. In km/h = (50/3) * (18/5) = 60 km/h."
    },
    {
        "id": "oa-quant-3",
        "category": "Quantitative Aptitude",
        "subtopic": "Permutations & Combinations",
        "question": "In how many ways can the letters of the word 'LEADER' be arranged?",
        "options": ["A) 720", "B) 360", "C) 120", "D) 240"],
        "answer": "B",
        "explanation": "Total letters = 6. Letter 'E' appears twice. Total ways = 6! / 2! = 720 / 2 = 360."
    },
    {
        "id": "oa-quant-4",
        "category": "Quantitative Aptitude",
        "subtopic": "Probability",
        "question": "Two dice are thrown simultaneously. What is the probability of getting two numbers whose product is even?",
        "options": ["A) 1/2", "B) 3/4", "C) 5/6", "D) 2/3"],
        "answer": "B",
        "explanation": "Product is odd only when both dice show odd numbers (3 * 3 = 9 outcomes out of 36). P(odd) = 9/36 = 1/4. P(even) = 1 - 1/4 = 3/4."
    },

    # Logical Reasoning
    {
        "id": "oa-logic-1",
        "category": "Logical Reasoning",
        "subtopic": "Syllogisms",
        "question": "Statements: (1) All dogs are pets. (2) Some pets are cats. Conclusions: I. Some dogs are cats. II. Some pets are dogs.",
        "options": ["A) Only I follows", "B) Only II follows", "C) Either I or II follows", "D) Neither follows"],
        "answer": "B",
        "explanation": "Since all dogs are pets, the converse 'Some pets are dogs' must be true (II follows). There is no guaranteed intersection between dogs and cats (I does not follow)."
    },
    {
        "id": "oa-logic-2",
        "category": "Logical Reasoning",
        "subtopic": "Number Series",
        "question": "Find the missing number in the series: 2, 6, 12, 20, 30, 42, ?",
        "options": ["A) 52", "B) 54", "C) 56", "D) 60"],
        "answer": "C",
        "explanation": "Differences are +4, +6, +8, +10, +12. Next difference is +14: 42 + 14 = 56. (Also n*(n+1): 1*2, 2*3, 3*4, 4*5, 5*6, 6*7, 7*8=56)."
    },

    # Core CS & Java
    {
        "id": "oa-cs-1",
        "category": "Core Computer Science",
        "subtopic": "Java Collections & Concurrency",
        "question": "Which Java collection implementation is thread-safe without locking the entire backing table during reads?",
        "options": ["A) Hashtable", "B) Collections.synchronizedMap()", "C) ConcurrentHashMap", "D) HashMap"],
        "answer": "C",
        "explanation": "ConcurrentHashMap uses bucket-level locking (or CAS operations in Java 8+) allowing concurrent non-blocking reads and lock-striping for writes."
    },
    {
        "id": "oa-cs-2",
        "category": "Core Computer Science",
        "subtopic": "DSA & Time Complexity",
        "question": "What is the worst-case time complexity of searching for an element in an unbalanced Binary Search Tree (BST)?",
        "options": ["A) O(1)", "B) O(log N)", "C) O(N)", "D) O(N log N)"],
        "answer": "C",
        "explanation": "When elements are inserted in sorted order, an unbalanced BST degenerates into a singly linked list with O(N) traversal time."
    },
    {
        "id": "oa-cs-3",
        "category": "Core Computer Science",
        "subtopic": "Operating Systems & Memory",
        "question": "What is the primary cause of 'Thrashing' in an operating system virtual memory subsystem?",
        "options": [
            "A) High CPU utilization from numerical computation",
            "B) A process spending more time paging in/out than executing instructions",
            "C) Deadlock between two mutex threads",
            "D) Cache line invalidation in L1 CPU cache"
        ],
        "answer": "B",
        "explanation": "Thrashing occurs when active working sets exceed physical RAM, causing the OS to constantly swap pages between memory and disk."
    },
    {
        "id": "oa-cs-4",
        "category": "Core Computer Science",
        "subtopic": "DBMS & Indexing",
        "question": "Why do relational databases commonly use B+ Trees rather than B-Trees for disk-backed index storage?",
        "options": [
            "A) B+ Trees store data records in non-leaf internal nodes",
            "B) B+ Tree internal nodes store only keys, maximizing branching factor and fitting more keys per disk page",
            "C) B+ Trees eliminate disk seeks entirely",
            "D) B+ Trees have O(1) worst-case insertion time"
        ],
        "answer": "B",
        "explanation": "Because internal nodes in B+ Trees omit data records, the fan-out is significantly higher, keeping tree height shallow (3-4 levels) and leaf nodes linked sequentially for range queries."
    }
]


class OASimulator:
    def __init__(self, db=None, ledger=None):
        self.db = db
        self.ledger = ledger

    def get_daily_drill(self, day_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the 10 questions for today's placement drill (answers stripped)."""
        drill = []
        for q in DRILL_QUESTION_BANK:
            drill.append({
                "id": q["id"],
                "category": q["category"],
                "subtopic": q["subtopic"],
                "question": q["question"],
                "options": q["options"]
            })
        return drill

    def submit_drill(self, answers: Dict[str, str], day_date: Optional[str] = None) -> Dict[str, Any]:
        """Evaluates answers, calculates accuracy, and records proof."""
        today = day_date or dt.date.today().isoformat()
        total = len(DRILL_QUESTION_BANK)
        correct_count = 0
        review = []

        for q in DRILL_QUESTION_BANK:
            qid = q["id"]
            user_ans = (answers.get(qid) or "").strip().upper()
            is_correct = (user_ans == q["answer"])
            if is_correct:
                correct_count += 1
            review.append({
                "id": qid,
                "category": q["category"],
                "subtopic": q["subtopic"],
                "user_answer": user_ans or "UNANSWERED",
                "correct_answer": q["answer"],
                "is_correct": is_correct,
                "explanation": q["explanation"]
            })

        score_pct = int(round((correct_count / total) * 100))
        
        # Log to ledger
        if self.ledger:
            self.ledger.record(
                "oa_drill_completed",
                observed={
                    "date": today,
                    "score": f"{correct_count}/{total}",
                    "score_pct": score_pct
                }
            )

        return {
            "ok": True,
            "date": today,
            "score": f"{correct_count}/{total}",
            "score_pct": score_pct,
            "correct": correct_count,
            "total": total,
            "review": review
        }
