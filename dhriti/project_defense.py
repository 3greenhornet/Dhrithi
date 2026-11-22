"""Dhriti Project Defense Engine (L-4 Placement Readiness / Package L).

Prepares college graduates to defend their codebase in technical placement interviews:
1. Analyzes code files via AST structure (classes, methods, docstrings, exceptions).
2. Generates 5 structured interview defense flashcards (Architecture, Design Decisions,
   Request Tracing, Failure Modes, and Complexity Analysis).
3. Connects to local Ollama if running, with a reliable deterministic static analysis fallback.
4. Integrates directly into Vidura for Spaced Repetition review.
"""

from __future__ import annotations

import ast
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectDefenseService:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url.rstrip("/")

    def inspect_file(self, file_path: Path | str) -> Dict[str, Any]:
        """Analyzes a code file's AST, classes, functions, and docstrings."""
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"Source file not found: {p}")

        content = p.read_text(encoding="utf-8", errors="replace")
        info: Dict[str, Any] = {
            "path": str(p),
            "filename": p.name,
            "stem": p.stem,
            "lines": len(content.splitlines()),
            "docstring": "",
            "classes": [],
            "functions": [],
            "imports": [],
            "exceptions_handled": [],
            "raw_snippet": content[:1200]
        }

        if p.suffix.lower() == ".py":
            try:
                tree = ast.parse(content, filename=str(p))
                info["docstring"] = ast.get_docstring(tree) or ""
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        info["classes"].append({
                            "name": node.name,
                            "docstring": ast.get_docstring(node) or "",
                            "methods": methods[:8]
                        })
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Only top-level functions or major methods
                        info["functions"].append({
                            "name": node.name,
                            "docstring": ast.get_docstring(node) or "",
                            "args": [a.arg for a in node.args.args]
                        })
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            info["imports"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        info["imports"].append(mod)
                    elif isinstance(node, ast.ExceptHandler):
                        if isinstance(node.type, ast.Name):
                            info["exceptions_handled"].append(node.type.id)
            except Exception:
                pass

        return info

    def generate_defense_questions(self, file_path: Path | str) -> Dict[str, Any]:
        """Generates 5 interview defense questions with answers."""
        info = self.inspect_file(file_path)
        
        # 1. Try local Ollama if available
        llm_questions = self._try_ollama(info)
        if llm_questions:
            return {
                "ok": True,
                "source": "ollama",
                "file": info["path"],
                "questions": llm_questions
            }

        # 2. Deterministic Sovereign AST Analysis Fallback
        deterministic_questions = self._generate_deterministic_questions(info)
        return {
            "ok": True,
            "source": "ast_analyzer",
            "file": info["path"],
            "questions": deterministic_questions
        }

    def _try_ollama(self, info: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Queries local Ollama if active and has a model loaded."""
        try:
            # Check models
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                if not models:
                    return None
                model = models[0]

            prompt = (
                f"You are a Senior Principal Interviewer conducting a Technical Placement Defense.\n"
                f"Analyze this source code file '{info['filename']}':\n"
                f"Classes: {[c['name'] for c in info['classes'][:5]]}\n"
                f"Functions: {[f['name'] for f in info['functions'][:5]]}\n"
                f"Snippet:\n{info['raw_snippet']}\n\n"
                f"Generate exactly 5 placement defense questions testing:\n"
                f"1. Role & Architecture\n2. Design Pattern & Alternatives\n3. Request Tracing / Execution Flow\n4. Failure Modes & Edge Cases\n5. Complexity & Scaling\n"
                f"Output strictly valid JSON array of objects with keys: 'category', 'question', 'sample_answer'."
            )

            gen_req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(gen_req, timeout=8) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                response_text = result.get("response", "")
                parsed = json.loads(response_text)
                if isinstance(parsed, list) and len(parsed) >= 3:
                    return parsed
        except Exception:
            pass
        return None

    def _generate_deterministic_questions(self, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generates authentic defense questions using AST structure."""
        stem = info["stem"].replace("_", " ").title()
        primary_class = info["classes"][0]["name"] if info["classes"] else f"{stem}Service"
        methods = info["classes"][0]["methods"] if info["classes"] else [f["name"] for f in info["functions"][:4]]
        key_method = methods[0] if methods else "execute"
        imports_str = ", ".join(info["imports"][:4]) or "standard library"

        return [
            {
                "category": "Role & Architecture",
                "question": f"What is the single responsibility of `{info['filename']}` in Dhriti, and why does it live in this module?",
                "key_points": [
                    f"Encapsulates {stem} logic cleanly.",
                    "Decouples core business invariants from presentation and CLI.",
                    f"Dependencies include: {imports_str}."
                ],
                "sample_answer": (
                    f"`{info['filename']}` is responsible for {stem} management. "
                    f"It exposes class `{primary_class}` to isolate state mutations and ensure transactional integrity."
                )
            },
            {
                "category": "Design Patterns & Trade-offs",
                "question": f"Why was `{primary_class}` chosen to handle this lifecycle instead of a procedural script or global module state?",
                "key_points": [
                    "Dependency injection of database/clock/ledger allows strict deterministic unit testing.",
                    "Encapsulation prevents mutable state leaking across test suites.",
                    "Thread safety and resource lifecycle boundaries."
                ],
                "sample_answer": (
                    f"`{primary_class}` encapsulates dependencies via constructor injection, allowing isolated testing "
                    f"with temporary SQLite ledgers without mutating global environment state."
                )
            },
            {
                "category": "Execution Path & Request Flow",
                "question": f"Trace the execution flow when an input triggers `{key_method}()`. What validations occur before state changes?",
                "key_points": [
                    "Input sanitization and constraints validation.",
                    "Ledger event recording (prev_hash / entry_hash chaining).",
                    "Database state persistence."
                ],
                "sample_answer": (
                    f"When `{key_method}()` is invoked, it validates input parameters against system constraints, "
                    f"queries existing state, applies deterministic domain rules, and records an audit event."
                )
            },
            {
                "category": "Failure Modes & Edge Cases",
                "question": f"What happens if a database lock, network timeout, or schema conflict occurs during execution of `{info['filename']}`?",
                "key_points": [
                    "Explicit error handling rather than silent failure.",
                    "Exception hierarchy or transactional rollback.",
                    "Zero data corruption guarantees."
                ],
                "sample_answer": (
                    f"Exceptions are trapped and converted to domain errors without corrupting the database. "
                    f"NTFS file-locking semantics and SQLite PRAGMA journal_mode=DELETE protect the audit chain."
                )
            },
            {
                "category": "Algorithmic Complexity & Scaling",
                "question": f"Analyze the time and space complexity of `{info['filename']}` when processing high transaction volumes.",
                "key_points": [
                    "Time complexity: O(1) indexed lookups vs O(N) linear scans.",
                    "Space complexity: in-memory memory footprint bounded by pagination.",
                    "SQLite indexing and query optimization."
                ],
                "sample_answer": (
                    f"Primary operations operate in O(1) or O(log N) due to SQLite indexing on primary keys and dates. "
                    f"Memory consumption is strictly bounded by query LIMIT clauses to prevent memory exhaustion."
                )
            }
        ]

    def save_to_vidura(self, corpus, file_path: Path | str, questions: List[Dict[str, Any]]) -> List[str]:
        """Saves generated defense flashcards to Vidura for daily Spaced Review."""
        p = Path(file_path)
        saved_ids = []
        for idx, q in enumerate(questions):
            ext_id = f"defense:{p.name}:{idx+1}"
            title = f"Project Defense: {q['category']} — {p.name}"
            description = f"Q: {q['question']}\n\nSample Answer:\n{q.get('sample_answer', '')}"
            item_id = corpus.add_item(
                url=f"file:///{p.resolve().as_posix()}#q{idx+1}",
                title=title,
                kind="defense",
                source="project_defense",
                description=description,
                external_id=ext_id,
                topic_labels=["Placement Project Defense", "Technical Interview Prep", p.stem]
            )
            saved_ids.append(item_id)
        return saved_ids
