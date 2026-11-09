"""The topic-locked research pass (v0.5.0): a declared question, a
minute budget, bounded sources, and the answer kept for cold review.
D-069's grace-period tests arrive in v0.6.0 (mechanism 5)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.profiles import CATEGORY_DOMAINS

from test_plumbing import DhritiTestCase


class TestTopicLockPass(DhritiTestCase):
    def test_pass_records_the_declared_question(self):
        session = self.start_session()
        rp = self.passes.open(session["id"],
                              "why does the JWT test fail on refresh",
                              minutes=10)
        self.assertEqual(rp["question"],
                         "why does the JWT test fail on refresh")
        self.assertEqual(rp["state"], "OPEN")

    def test_default_sources_are_the_ai_chat_surfaces(self):
        session = self.start_session()
        rp = self.passes.open(session["id"], "q", minutes=5)
        self.assertEqual(sorted(rp["sources"]),
                         sorted(CATEGORY_DOMAINS.get("ai_chat", [])))

    def test_sources_allowed_only_inside_the_window(self):
        session = self.start_session()
        self.passes.open(session["id"], "q", minutes=10)
        self.assertTrue(self.passes.active_sources())
        self.clock.advance(minutes=11)
        # expired: the pass is expired, sources gone
        self.passes.expire_overdue()
        self.assertEqual(self.passes.active_sources(), [])

    def test_returned_answer_is_kept_for_review(self):
        session = self.start_session()
        self.passes.open(session["id"], "q", minutes=5)
        row = self.passes.return_pass("the answer")
        self.assertEqual(row["state"], "RETURNED")
        self.assertEqual(row["answer"], "the answer")

    def test_second_pass_while_open_refused(self):
        session = self.start_session()
        self.passes.open(session["id"], "q1", minutes=5)
        from dhriti.research_pass import ResearchPassError
        with self.assertRaises(ResearchPassError):
            self.passes.open(session["id"], "q2", minutes=5)
        # after returning, a new pass may open
        self.passes.return_pass("a1")
        second = self.passes.open(session["id"], "q2", minutes=5)
        self.assertEqual(self.passes.active()["id"], second["id"])

    def test_hard_expiry_at_expires_at(self):
        """v0.5.0 expiry was hard at expires_at. v0.6.0 (mechanism 5)
        adds a grace window; the hard form is still reachable with
        grace_seconds=0 and the grace tests live here too."""
        session = self.start_session()
        rp = self.passes.open(session["id"], "q", minutes=1)
        self.clock.advance(seconds=61)
        expired = self.passes.expire_overdue(grace_seconds=0)
        self.assertIn(rp["id"], expired)
        row = self.db.query_one(
            "SELECT state FROM research_pass WHERE id=?", (rp["id"],))
        self.assertEqual(row["state"], "EXPIRED")

    def test_grace_period_accepts_answer(self):
        """Mechanism 5: a pass that expires mid-paragraph gets 120s
        to close; sources are gone but the answer is accepted."""
        session = self.start_session()
        self.passes.open(session["id"], "typed during the pass",
                         minutes=1)
        self.clock.advance(seconds=90)  # 30s into grace
        self.assertEqual(self.passes.active_sources(), [])  # gone
        self.assertIsNone(self.passes.active())
        row = self.passes.return_pass("the answer, 30s late")
        self.assertEqual(row["state"], "RETURNED")
        self.assertEqual(row["answer"], "the answer, 30s late")

    def test_grace_period_ends_and_expires(self):
        session = self.start_session()
        rp = self.passes.open(session["id"], "typed", minutes=1)
        # the spec's example advanced 130s, which is 70s INTO a 120s
        # grace (60s pass + 120s grace = 180s) — recorded in
        # DECISIONS_PROPOSED. Past the boundary means past 180s:
        self.clock.advance(seconds=190)  # past expiry + grace
        self.passes.expire_overdue(grace_seconds=120)
        events = self.ledger.events(event_type="research_pass_expired")
        self.assertEqual(len(events), 1)
        row = self.db.query_one(
            "SELECT state FROM research_pass WHERE id=?", (rp["id"],))
        self.assertEqual(row["state"], "EXPIRED")


if __name__ == "__main__":
    unittest.main()
