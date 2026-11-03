"""Fault/semantic fixtures for the disabled trial tool; never access USB or /data."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent.parent / "module/usb-recover.sh"


class RecoveryJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "journal"

    def call(self, command, check=True):
        # Stub sync only in fixtures. Production calls real sync.
        harness = 'set -- library; . %s; JOURNAL_DIR=%s; sync() { :; }; %s' % (
            shlex.quote(str(SCRIPT)), shlex.quote(str(self.directory)), command)
        return subprocess.run(["sh", "-c", harness], text=True,
                              capture_output=True, check=check)

    def begin(self):
        self.call("journal_begin 100.1")

    def until_connect(self, disconnect="ok", connect="ok"):
        self.begin()
        for phase, result in [("executor_ready", "ok"),
                              ("disconnect_requested", "pending"),
                              ("disconnect_returned", disconnect),
                              ("connect_requested", "pending"),
                              ("connect_returned", connect)]:
            self.call("journal_record 100.1 %s %s" % (phase, result))

    def test_call_success_is_not_communication_success(self):
        self.until_connect()
        self.assertIn("outcome=recovery_unconfirmed", self.call("journal_status").stdout)
        self.assertNotEqual(self.call("journal_record 100.1 communication_observed ok", False).returncode, 0)
        self.call("journal_record 100.1 enumeration_observed ok")
        self.call("journal_record 100.1 address_observed ok")
        self.call("journal_record 100.1 communication_observed ok")
        self.assertIn("outcome=communication_restored", self.call("journal_status").stdout)

    def test_uncertain_disconnect_allows_restore_but_not_false_success(self):
        self.until_connect(disconnect="timeout", connect="unknown")
        self.call("journal_record 100.1 enumeration_observed timeout")
        self.assertNotEqual(self.call("journal_record 100.1 address_observed ok", False).returncode, 0)
        self.assertIn("recovery_unconfirmed", self.call("journal_status").stdout)
        self.call("journal_record 100.1 failed error")
        self.assertIn("trial_stopped", self.call("journal_status").stdout)

    def test_existing_evidence_wrong_ticket_and_foreign_lock_are_preserved(self):
        self.begin()
        saved = (self.directory / "events.tsv").read_bytes()
        for command in ("journal_begin 200.1", "journal_record 200.1 executor_ready ok"):
            self.assertNotEqual(self.call(command, False).returncode, 0)
        (self.directory / "lock").mkdir()
        self.assertNotEqual(self.call("journal_record 100.1 executor_ready ok", False).returncode, 0)
        self.assertTrue((self.directory / "lock").is_dir())
        self.assertEqual(saved, (self.directory / "events.tsv").read_bytes())

    def test_cutoff_and_interrupted_update_refuse_writes(self):
        self.begin()
        saved = (self.directory / "events.tsv").read_bytes()
        self.assertNotEqual(self.call("JOURNAL_LIMIT=1; journal_record 100.1 executor_ready ok", False).returncode, 0)
        (self.directory / "events.new").write_text("interrupted")
        self.assertNotEqual(self.call("journal_record 100.1 executor_ready ok", False).returncode, 0)
        self.assertEqual(saved, (self.directory / "events.tsv").read_bytes())
        self.assertEqual((self.directory / "events.new").read_text(), "interrupted")

    def test_missing_record_and_vocabulary_do_not_create_evidence(self):
        self.assertEqual(self.call("journal_status").stdout.strip(), "no_trial_record")
        self.assertFalse(self.directory.exists())
        for command in ("journal_begin '../invalid'", "journal_record 100.1 password secret",
                        "journal_record 100.1 prepared ok"):
            self.assertNotEqual(self.call(command, False).returncode, 0)
        self.assertFalse(self.directory.exists())

    def test_old_mutation_commands_are_disabled(self):
        for mode in ("launch", "delayed", "run", "guard"):
            result = subprocess.run(["sh", str(SCRIPT), mode, "100.1", "100"],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 64)
            self.assertIn("USB mutation disabled", result.stderr)

    def test_truncated_record_cannot_report_restored(self):
        self.begin()
        with (self.directory / "events.tsv").open("a") as output:
            output.write("2\t100.1\tcommunication_observed\tok\n")
        result = self.call("journal_status", False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid_record", result.stdout)
        self.assertNotIn("communication_restored", result.stdout)
        self.assertNotEqual(self.call("journal_record 100.1 executor_ready ok", False).returncode, 0)
