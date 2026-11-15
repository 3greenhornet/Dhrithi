"""v0.7.0 Part 4 tests: the rituals — witness protocol (§4.1, §4.6),
compost (§4.2), absence (§4.3), physical register (§4.4), ceremony
(§4.5), meta-commitment (§4.7), quiet hour (§4.8), debrief (§4.9),
letters (§4.10), voice archive (§4.11), 90-day archive (§4.13),
confession (§4.14), five aftermath views (§4.15), complexity budget
(§4.17), identity revision (§4.18), the earned ladder line (§4.19),
Dhriti Lite (§4.21)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datetime as _dt
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from dhriti.rituals import (AbsenceTest, ArchiveService,
                            CeremonyService, CompostRitual,
                            ConfessionService, DebriefService,
                            LetterService, MetaCommitment,
                            QuietHour, VoiceArchive)
from dhriti.review import build_digest_v070
from dhriti.lite import LiteMode

from test_plumbing import DhritiTestCase, daily_payload


class TestWitness(DhritiTestCase):
    def test_one_true_thing_prefers_unanswered_passes(self):
        session = self.start_session()
        self.passes.open(session["id"], "how do tokens expire",
                         minutes=5)
        self.clock.advance(minutes=10)
        self.passes.expire_overdue(grace_seconds=0)
        record = self.breaks.initiate(None)
        self.clock.advance(seconds=70)
        self.breaks.confirm(record["id"],
                            "the honest reason for this break here")
        text = build_digest_v070(self.db, self.ledger,
                                 self.today.isoformat(),
                                 self.config, self.clock)
        self.assertIn("The one true thing from this week:", text)
        # unanswered passes outrank breaks (the deterministic rule)
        self.assertIn("expired unanswered", text)

    def test_witness_sentence_leads(self):
        session = self.start_session()
        self.passes.open(session["id"], "a question", minutes=5)
        self.clock.advance(minutes=10)
        self.passes.expire_overdue(grace_seconds=0)
        text = build_digest_v070(self.db, self.ledger,
                                 self.today.isoformat(),
                                 self.config, self.clock)
        self.assertIn("This week, in one sentence:", text)


class TestCompost(DhritiTestCase):
    def _aged_item(self):
        from dhriti.mirror.store import MirrorStore
        store = MirrorStore(self.db, {"mirror": {}}, self.clock,
                            self.ledger)
        source = store.add_source("youtube_liked", "LL", "Liked")
        row = store.upsert_item(source["id"], "v1",
                                "An old course, never opened")
        old = (self.clock.now_utc()
               - _dt.timedelta(days=120)).strftime(
                   "%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            "UPDATE content_item SET saved_at_utc=? WHERE id=?",
            (old, row["id"]))
        return row

    def test_due_when_something_is_old(self):
        self._aged_item()
        compost = CompostRitual(self.db, self.config, self.clock,
                                self.ledger)
        self.assertTrue(compost.due())

    def test_complete_marks_and_records(self):
        row = self._aged_item()
        compost = CompostRitual(self.db, self.config, self.clock,
                                self.ledger)
        counts = compost.complete(
            {row["id"]: "not watching it was the point of saving it",
             "missing-id": "skip"})
        self.assertEqual(counts["composted"], 1)
        self.assertEqual(counts["kept"], 0)
        marked = self.db.query_one(
            "SELECT * FROM content_item WHERE id=?", (row["id"],))
        self.assertTrue(marked["abandoned_at"])
        self.assertIn("composted", marked["abandoned_reason"])
        self.assertEqual(len(self.ledger.events(
            event_type="compost_ritual_completed")), 1)

    def test_skip_keeps_the_item(self):
        row = self._aged_item()
        compost = CompostRitual(self.db, self.config, self.clock,
                                self.ledger)
        counts = compost.complete({row["id"]: "skip"})
        self.assertEqual(counts["kept"], 1)
        marked = self.db.query_one(
            "SELECT abandoned_at FROM content_item WHERE id=?",
            (row["id"],))
        self.assertIsNone(marked["abandoned_at"])


class TestAbsence(DhritiTestCase):
    def test_declared_and_active(self):
        absence = AbsenceTest(self.db, self.config, self.clock,
                              self.ledger)
        absence.declare(self.today.isoformat())
        self.assertTrue(absence.is_active(self.today.isoformat()))
        self.assertFalse(absence.is_active("2026-12-25"))
        self.assertEqual(len(self.ledger.events(
            event_type="absence_test_day")), 1)

    def test_one_day_per_month_cap(self):
        absence = AbsenceTest(self.db, self.config, self.clock,
                              self.ledger)
        absence.declare("2026-11-02")
        with self.assertRaises(ValueError):
            absence.declare("2026-11-20")
        # a different month is a different test
        absence.declare("2026-12-05")

    def test_the_aftermath_asks_the_one_question(self):
        absence = AbsenceTest(self.db, self.config, self.clock,
                              self.ledger)
        absence.declare(self.today.isoformat())
        self.seal_today()
        md = self.aftermath.day_report(
            self.today.isoformat())["md"]
        self.assertIn("you ran the day without the system. "
                      "Did you miss it?", md)


class TestEmergencyContactsOnWall(DhritiTestCase):
    def test_contacts_served_only_when_a_break_is_open(self):
        from dhriti.reflection_bank import EmergencyContacts
        from dhriti.daemon import Daemon
        contacts = EmergencyContacts(self.db, self.clock, self.ledger)
        contacts.add("mom", "+91-...")
        contacts.add("dad", "+91-...")
        session = self.start_session()
        daemon = self.make_daemon()
        try:
            payload = {}
            daemon._emergency_contacts_on_wall(payload)
            # no break initiated yet: nothing on the wall
            self.assertIsNone(payload["emergency_contacts"])
            self.breaks.initiate(session["id"])
            payload = {}
            daemon._emergency_contacts_on_wall(payload)
            self.assertEqual(len(payload["emergency_contacts"]), 2)
            self.assertEqual(payload["emergency_contacts"][0]
                             ["label"], "mom")
        finally:
            daemon.release_lock()
            daemon.db.close()


class TestFoqosBarcodeSharing(DhritiTestCase):
    def test_physical_tier_accepts_foqos_registered_codes(self):
        from dhriti.break_glass_friction import FrictionLadder
        foqos_dir = self.home / "foqos-barcodes"
        foqos_dir.mkdir()
        (foqos_dir / "KITCHEN-PANTRY-0042").write_text(
            "foqos registration", encoding="utf-8")
        self.config["stack"]["foqos"] = {
            "enabled": True, "barcode_dir": str(foqos_dir)}
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        # not registered with dhriti's own table — but foqos has it
        self.assertFalse(ladder.verify_barcode("NOT-A-CODE"))
        self.assertTrue(ladder.verify_barcode("KITCHEN-PANTRY-0042"))


class TestPhysicalRegister(DhritiTestCase):
    def test_body_line_in_the_aftermath(self):
        payload = daily_payload()
        payload["workspace_dir"] = str(self.home)
        payload["body_register"] = ("sleep was bad Mon-Wed; walked "
                                    "Thu-Sat")
        self.contracts.seal(self.today.isoformat(), payload)
        md = self.aftermath.day_report(
            self.today.isoformat())["md"]
        self.assertIn("Body this week:", md)
        self.assertIn("sleep was bad Mon-Wed", md)

    def test_absent_when_never_asked(self):
        self.seal_today()
        md = self.aftermath.day_report(
            self.today.isoformat())["md"]
        self.assertNotIn("Body this week:", md)


class TestCeremony(DhritiTestCase):
    def test_the_file_keeps_the_feeling_the_ledger_the_fact(self):
        ceremony = CeremonyService(self.db, self.config, self.home,
                                   self.clock, self.ledger)
        result = ceremony.write(
            "2026-11-02",
            "It felt like the wall was right and I walked around it "
            "anyway, and the walking around was worse than the work.",
            contract_line="reverse the array",
            identity="I am the person who writes the compiler")
        self.assertTrue((self.home / "broken_contracts.md").exists())
        text = (self.home / "broken_contracts.md").read_text()
        self.assertIn("worse than the work", text)
        events = self.ledger.events(
            event_type="broken_contract_ceremony")
        self.assertEqual(len(events), 1)
        observed = json.loads(events[0]["observed_payload"])
        self.assertIn("word_count", observed)
        self.assertNotIn("worse than the work",
                         events[0]["observed_payload"])

    def test_short_paragraph_refused(self):
        ceremony = CeremonyService(self.db, self.config, self.home,
                                   self.clock, self.ledger)
        with self.assertRaises(ValueError):
            ceremony.write("2026-11-02", "it was fine i guess")


class TestMetaCommitment(DhritiTestCase):
    def test_off_by_default(self):
        meta = MetaCommitment(self.db, self.config, self.clock,
                              self.ledger)
        self.assertFalse(meta.active())
        # off means no refusal even mid-bootcamp
        meta.check_config_change(bootcamp_active=True)

    def test_refused_mid_bootcamp_when_on(self):
        self.config["meta_commitment"] = {"enabled": True}
        meta = MetaCommitment(self.db, self.config, self.clock,
                              self.ledger)
        with self.assertRaises(PermissionError):
            meta.check_config_change(bootcamp_active=True)

    def test_review_outcomes(self):
        meta = MetaCommitment(self.db, self.config, self.clock,
                              self.ledger)
        self.assertEqual(meta.review("a", "the metric was wrong")
                         ["outcome"], "lifted for this change")
        self.assertEqual(meta.review("b", "just avoid it")
                         ["outcome"], "refused")
        self.assertEqual(meta.review("c", "not sure")
                         ["outcome"], "deferred 24h")
        with self.assertRaises(ValueError):
            meta.review("d", "")


class TestQuietHour(DhritiTestCase):
    def test_off_by_default(self):
        quiet = QuietHour(self.db, self.config, self.clock,
                          self.ledger)
        self.assertFalse(quiet.active_now())

    def test_active_inside_the_window(self):
        # local now is 10:00 (Asia/Kolkata); the hour is now
        self.config["quiet_hour"] = {"enabled": True,
                                     "start_local": "10:00",
                                     "duration_minutes": 60}
        quiet = QuietHour(self.db, self.config, self.clock,
                          self.ledger)
        self.assertTrue(quiet.active_now())

    def test_inactive_outside_the_window(self):
        self.config["quiet_hour"] = {"enabled": True,
                                     "start_local": "16:00",
                                     "duration_minutes": 60}
        quiet = QuietHour(self.db, self.config, self.clock,
                          self.ledger)
        self.assertFalse(quiet.active_now())

    def test_mark_observed_records_no_log(self):
        quiet = QuietHour(self.db, self.config, self.clock,
                          self.ledger)
        quiet.mark_observed("2026-11-02")
        events = self.ledger.events(
            event_type="quiet_hour_observed")
        self.assertEqual(len(events), 1)
        self.assertIn("no log required",
                      events[0]["action_taken"])


class TestDebrief(DhritiTestCase):
    def test_recorded_when_answered(self):
        debrief = DebriefService(self.db, self.config, self.clock,
                                 self.ledger)
        result = debrief.record("s1", "the test passed after the "
                                       "retry")
        self.assertFalse(result["skipped"])
        events = self.ledger.events(event_type="session_debrief")
        self.assertEqual(len(events), 1)

    def test_skippable(self):
        debrief = DebriefService(self.db, self.config, self.clock,
                                 self.ledger)
        result = debrief.record("s1", "")
        self.assertTrue(result["skipped"])
        self.assertEqual(len(self.ledger.events(
            event_type="session_debrief")), 0)


class TestLetters(DhritiTestCase):
    def test_write_and_due_six_months_later(self):
        letters = LetterService(self.db, self.config, self.home,
                                self.clock, self.ledger)
        result = letters.write(
            "Dear future me: the tests pass now, and the pile is "
            "smaller than it was. Keep the window open.")
        self.assertTrue((self.home / "letters" / "2026-11-02.txt")
                        .exists())
        self.assertIsNone(letters.due())
        self.clock.advance(days=183)
        due = letters.due()
        self.assertIsNotNone(due)
        self.assertIn("Dear future me", due["text"])
        self.assertEqual(len(self.ledger.events(
            event_type="letter_written")), 1)

    def test_short_letter_refused(self):
        letters = LetterService(self.db, self.config, self.home,
                                self.clock, self.ledger)
        with self.assertRaises(ValueError):
            letters.write("hi")


class TestVoiceArchive(DhritiTestCase):
    def test_typed_memo_archived(self):
        voice = VoiceArchive(self.db, self.config, self.home,
                             self.clock, self.ledger)
        result = voice.record_typed(
            "today the wall held and I did not fight it")
        self.assertEqual(result["mode"], "typed")
        self.assertTrue((self.home / "voice" / "2026-11-02.md")
                        .exists())
        self.assertEqual(len(self.ledger.events(
            event_type="voice_memo_recorded")), 1)


class TestArchive(DhritiTestCase):
    def test_quarter_document_generated(self):
        self.seal_today()
        archive = ArchiveService(self.db, self.config, self.home,
                                 self.clock, self.ledger)
        result = archive.generate(2026, 4)
        path = Path(result["path"])
        self.assertTrue(path.exists())
        text = path.read_text()
        self.assertIn("# Dhriti archive — 2026-Q4", text)
        self.assertIn("Contracts (1)", text)
        self.assertIn("reverse the array", text)


class TestConfession(DhritiTestCase):
    def test_two_turn_echo_no_offers(self):
        confession = ConfessionService(self.db, self.config,
                                       self.clock, self.ledger)
        first = confession.mirror_turn(
            "I'm not opening the JWT test")
        self.assertIn("I'm not opening the JWT test", first)
        self.assertIn("Why?", first)
        # the close does not ask anything
        close = confession.close_turn(
            "Because I don't understand async")
        self.assertNotIn("?", close.replace("async", ""))

    def test_record_keeps_only_the_fact(self):
        confession = ConfessionService(self.db, self.config,
                                       self.clock, self.ledger)
        confession.record("I'm not opening the JWT test",
                          "Because I don't understand async",
                          "break-1")
        events = self.ledger.events(event_type="confession_event")
        self.assertEqual(len(events), 1)
        self.assertNotIn("JWT", events[0]["observed_payload"])

    def test_cli_offers_before_the_break(self):
        self.config["confession"] = {"enabled": True}
        session = self.start_session()
        answers = iter(["I'm not opening the JWT test",
                        "Because I don't understand async"])
        out = io.StringIO()
        from dhriti import cli
        import argparse
        ctx = self.make_cli_context()
        try:
            with redirect_stdout(out), \
                    mock.patch("builtins.input",
                               lambda *_: next(answers)):
                cli.cmd_break_initiate(
                    argparse.Namespace(yes=False), ctx)
        finally:
            ctx.close()
        self.assertIn("Before you break: name it.", out.getvalue())
        self.assertIn("[two turns. no offers.", out.getvalue())
        events = self.ledger.events(event_type="confession_event")
        self.assertEqual(len(events), 1)


class TestFiveViews(DhritiTestCase):
    def test_five_view_headers_and_coverage(self):
        self.seal_today()
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        for view in ("## View: the Wall", "## View: the Mirror",
                     "## View: the Conversation Boundary",
                     "## View: the Evidence Record",
                     "## View: the Experiment"):
            self.assertIn(view, md)
        self.assertEqual(md.count("Coverage missing:"), 5)

    def test_flat_format_when_disabled(self):
        self.config["aftermath_views"] = {"five_views": False}
        self.seal_today()
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertNotIn("## View: the Wall", md)
        self.assertIn("## Reality (what was observed)", md)


class TestIdentityRevision(DhritiTestCase):
    def test_history_of_the_current_state_field(self):
        from dhriti.contract import ContractService
        payload = daily_payload()
        payload["workspace_dir"] = str(self.home)
        payload["main_belief_current_state"] = "I am failing the course"
        self.contracts.seal("2026-11-01", payload)
        payload["main_belief_current_state"] = \
            "I am behind but the tests pass"
        self.contracts.seal("2026-11-02", payload)
        contracts = ContractService(self.db, self.clock, self.ledger)
        history = contracts.get_history_of_field(
            "main_belief_current_state")
        self.assertEqual([row["value"] for row in history],
                         ["I am failing the course",
                          "I am behind but the tests pass"])
        md = self.aftermath.day_report("2026-11-02")["md"]
        self.assertIn("Your current state, over time", md)
        self.assertIn("I am failing the course", md)


class TestComplexityBudget(DhritiTestCase):
    def test_budget_vs_actual_fact(self):
        payload = daily_payload()
        payload["workspace_dir"] = str(self.home)
        payload["complexity_budget_minutes"] = 15
        self.contracts.seal(self.today.isoformat(), payload)
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Complexity budget: 15 minutes/week", md)
        self.assertIn("Actual this week:", md)


class TestEarnedLadderLine(DhritiTestCase):
    def test_break_month_line_in_the_aftermath(self):
        record = self.breaks.initiate(None)
        self.clock.advance(seconds=70)
        self.breaks.confirm(record["id"],
                            "the honest reason for the break here")
        self.seal_today()
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Break-glass this month: 1.", md)
        self.assertIn("Current tier: 'baseline'", md)


class TestLite(DhritiTestCase):
    def test_the_smallest_day(self):
        lite = LiteMode(self.db, self.home, self.clock, self.ledger)
        day = lite.start("reverse the array",
                         "open the editor, write the loop",
                         "machine")
        with self.assertRaises(ValueError):
            lite.start("a second", "task", "manual")
        with self.assertRaises(ValueError):
            lite.finish()  # finish means proof
        lite.submit_evidence("the test file ran green")
        done = lite.finish()
        self.assertTrue(done["finished_at"])
        self.assertEqual(len(self.ledger.events(
            event_type="lite_day_completed")), 1)

    def test_guard_blocks_other_commands(self):
        lite = LiteMode(self.db, self.home, self.clock, self.ledger)
        lite.start("one thing", "the smallest action", "manual")
        self.assertTrue(lite.active())
        with self.assertRaises(PermissionError):
            lite.guard_other_commands()

    def test_cli_dispatch_refuses_all_but_lite(self):
        from dhriti import cli
        lite = LiteMode(self.db, self.home, self.clock, self.ledger)
        lite.start("one thing", "the smallest action", "manual")
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) \
                as ctx:
            cli.main(["--home", str(self.home), "status"])
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("a lite day is open", out.getvalue())
        # lite itself is the exit
        lite.submit_evidence("done")
        out2 = io.StringIO()
        with redirect_stdout(out2):
            cli.main(["--home", str(self.home), "lite", "finish"])
        self.assertIn("one lite day done", out2.getvalue())


if __name__ == "__main__":
    unittest.main()
