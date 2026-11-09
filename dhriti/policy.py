"""Deterministic policy engine (dossier 3.2, 8.1, 8.3).

Rules only. No model, no network, no similarity scores. The engine:

  * builds a versioned, immutable policy snapshot when a session seals —
    the snapshot is what enforces, so mid-session rule changes are
    impossible (Principle 1: commitment precedes temptation);
  * evaluates URLs / app names against allowlists, blocklists and
    categories;
  * honors three work modes (closed_world / bounded_research /
    open_exploration) and never collapses them into one score;
  * temporarily allows a bounded research pass's declared sources until
    its expiry — the only "dynamic" rule, and it is still deterministic;
  * applies control-engineering stability: decisions are stateless per
    event; cooldown/hysteresis live in break-glass and research expiry,
    not here (dossier 8.3).

Enforcement tiers (bootcamp taper, PDF 9.3) scale how decisions act:
  stage 1 FULL_LOCK    -> BLOCK stays BLOCK
  stage 2 REDUCED_LOCK -> BLOCK stays BLOCK (allowlist may be wider)
  stage 3 CHECKPOINT   -> BLOCK becomes WARN (override logged)
  stage 4 ADVISORY     -> BLOCK becomes WARN (tool optional)
"""

import json
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from .db import Database
from .models import Action, PolicyDecision, TaperStage, WorkMode
from .profiles import CATEGORY_DOMAINS
from .timeutil import Clock, RealClock, parse_iso

RULE_VERSION = "rules-v1"


def _host(url_or_host: str) -> str:
    raw = (url_or_host or "").strip().lower()
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.split(":")[0].split("@")[-1]


def _matches(host: str, domain: str) -> bool:
    domain = domain.lower().lstrip(".")
    return host == domain or host.endswith("." + domain)


class PolicyEngine:
    def __init__(self, db: Database, clock: Optional[Clock] = None):
        self.db = db
        self.clock = clock or RealClock()

    # -- snapshot lifecycle -------------------------------------------------
    def build_snapshot(self, profile: dict, contract_payload: dict,
                       work_mode: WorkMode, research_sources: Optional[list],
                       research_expires_at: Optional[str],
                       taper_stage: int = 1,
                       contract_id: Optional[str] = None,
                       day_id: Optional[str] = None,
                       suppress_surfaces: bool = True,
                       extra_blocked_domains: Optional[list] = None) -> dict:
        version = (self.db.query_one(
            "SELECT MAX(version) AS v FROM policy_snapshot") or {"v": 0})["v"] or 0
        version = int(version) + 1
        policy = {
            "version": version,
            "rule_version": RULE_VERSION,
            "created_at": self.clock.iso(),
            "enforce": taper_stage in (TaperStage.FULL_LOCK,
                                       TaperStage.REDUCED_LOCK),
            "taper_stage": int(taper_stage),
            "work_mode": work_mode.value,
            "profile": profile,
            "contract": {
                "contract_line": contract_payload.get("contract_line", ""),
                "core_belief": contract_payload.get("core_belief", ""),
                "identity_statement":
                    contract_payload.get("identity_statement", ""),
            },
            "allowed_domains": sorted(set(
                profile.get("allowed_domains", [])
                + contract_payload.get("allowed_tools", []))),
            "blocked_domains": sorted(set(
                list(contract_payload.get("blocked_tools", []))
                + list(extra_blocked_domains or []))),
            "blocked_categories": profile.get("blocked_categories", []),
            "suppress_surfaces": bool(suppress_surfaces),
            "research": {
                "sources": research_sources or [],
                "expires_at": research_expires_at,
            },
        }
        snap_id = str(uuid.uuid4())
        self.db.insert("policy_snapshot", {
            "id": snap_id, "version": version,
            "created_at": policy["created_at"],
            "policy_json": json.dumps(policy, default=str),
            "contract_id": contract_id, "day_id": day_id,
        })
        self.db.execute(
            "INSERT INTO policy_state(id, current_version, updated_at) "
            "VALUES(1, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "current_version=excluded.current_version, "
            "updated_at=excluded.updated_at",
            (version, policy["created_at"]))
        return policy

    def current_snapshot(self) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT policy_json FROM policy_snapshot ORDER BY version DESC "
            "LIMIT 1")
        return json.loads(row["policy_json"]) if row else None

    # -- evaluation ---------------------------------------------------------
    def evaluate_url(self, policy: dict, url: str) -> PolicyDecision:
        host = _host(url)
        if not host:
            return PolicyDecision(Action.ALLOW, "rule:no-host")

        if policy.get("work_mode") == WorkMode.OPEN_EXPLORATION.value:
            return PolicyDecision(Action.ALLOW, "rule:open-exploration")

        # 1. explicit allowlist wins (closed world)
        for domain in policy.get("allowed_domains", []):
            if _matches(host, domain):
                return PolicyDecision(Action.ALLOW, "rule:allowlist",
                                      category="allowed")

        # 2. bounded research sources are temporarily allowed until expiry
        research = policy.get("research") or {}
        if research.get("sources") and research.get("expires_at"):
            if self.clock.iso() <= research["expires_at"]:
                for domain in research["sources"]:
                    if _matches(host, domain):
                        return PolicyDecision(
                            Action.ALLOW, "rule:research-pass",
                            category="permitted_research")
            else:  # expired pass: source list no longer applies
                pass

        # 3. explicit blocked domains
        for domain in policy.get("blocked_domains", []):
            if _matches(host, domain):
                return self._scale(policy, Action.BLOCK, "rule:blocked-domain",
                                   "blocked")

        # 4. categories
        for category in policy.get("blocked_categories", []):
            for domain in CATEGORY_DOMAINS.get(category, []):
                if _matches(host, domain):
                    return self._scale(
                        policy, Action.BLOCK,
                        f"rule:category:{category}", category)

        # 5. closed world: anything not explicitly allowed is blocked
        if policy.get("work_mode") == WorkMode.CLOSED_WORLD.value:
            return self._scale(policy, Action.BLOCK, "rule:closed-world",
                               "unlisted")
        return PolicyDecision(Action.ALLOW, "rule:default-open")

    def evaluate_app(self, policy: dict, app_name: str) -> PolicyDecision:
        name = (app_name or "").strip().lower()
        if not name:
            return PolicyDecision(Action.ALLOW, "rule:no-app")
        if policy.get("work_mode") == WorkMode.OPEN_EXPLORATION.value:
            return PolicyDecision(Action.ALLOW, "rule:open-exploration")
        allowed_apps = [a.lower() for a in policy.get("profile", {}).get(
            "allowed_apps", [])]
        if name in allowed_apps:
            return PolicyDecision(Action.ALLOW, "rule:app-allowlist",
                                  category="allowed")
        blocked = [b.lower() for b in policy.get("blocked_domains", [])]
        if name in blocked:
            return self._scale(policy, Action.BLOCK, "rule:app-blocked",
                               "blocked")
        if policy.get("work_mode") == WorkMode.CLOSED_WORLD.value:
            return self._scale(policy, Action.BLOCK, "rule:app-closed-world",
                               "unlisted-app")
        return PolicyDecision(Action.ALLOW, "rule:app-default-open")

    def _scale(self, policy: dict, action: Action, rule_id: str,
               category: str) -> PolicyDecision:
        """Apply the taper stage to a BLOCK decision (PDF 9.3)."""
        if action is Action.BLOCK:
            stage = policy.get("taper_stage", 1)
            if stage >= TaperStage.CHECKPOINT:  # checkpoint/advisory: log only
                return PolicyDecision(Action.WARN, rule_id, category,
                                      "taper stage >= 3: block downgraded "
                                      "to WARN (override logged)")
        return PolicyDecision(action, rule_id, category)

    # -- extension-facing view -----------------------------------------------
    def extension_rules(self, policy: dict) -> dict:
        """Flatten the policy into what the extension needs: DNR domain
        rules + the user's own contract line + TTL. Reason strings and
        category detail stay out of the wall page (Wall Principle)."""
        blocked = []
        for category in policy.get("blocked_categories", []):
            blocked.extend(CATEGORY_DOMAINS.get(category, []))
        blocked.extend(policy.get("blocked_domains", []))
        if policy.get("work_mode") == WorkMode.CLOSED_WORLD.value:
            mode = "closed_world"
        else:
            mode = policy.get("work_mode", "closed_world")
        return {
            "version": policy["version"],
            "enforce": bool(policy.get("enforce")),
            "taper_stage": policy.get("taper_stage", 1),
            "work_mode": mode,
            "blocked_domains": sorted(set(blocked)),
            "allowed_domains": sorted(set(policy.get("allowed_domains", []))),
            "suppress_surfaces": bool(policy.get("suppress_surfaces", True)),
            "contract_line": (policy.get("contract", {})
                              .get("contract_line", "")),
            "expires_at": policy.get("expires_at"),
        }
