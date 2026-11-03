"""USB inventory formats, bounded observer and executor fault fixtures. No USB I/O."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from scripts import usb_enable_trial as trial


TARGET = {"idVendor": 0x2CA3, "idProduct": 0x4006, "IORegistryEntryID": 11}
SCRIPT = Path(__file__).resolve().parent.parent / "module/enable-trial.sh"


class HostTrialTests(unittest.TestCase):
    def test_dictionary_array_empty_and_reenumerated_inventories(self):
        tree = {"IORegistryEntryChildren": [dict(TARGET)]}
        self.assertEqual(trial.usb_entries(tree), frozenset({11}))
        self.assertEqual(trial.usb_entries([tree]), frozenset({11}))
        self.assertEqual(trial.usb_entries({}), frozenset())
        self.assertEqual(trial.usb_entries([]), frozenset())
        changed = dict(TARGET, IORegistryEntryID=12)
        self.assertNotEqual(trial.usb_entries(changed), trial.usb_entries(tree))

    def test_unknown_format_and_multiple_targets_fail_closed(self):
        for value in (None, "bad", ["bad"], {"IORegistryEntryChildren": {}},
                      dict(TARGET, IORegistryEntryID=True),
                      [TARGET, dict(TARGET, IORegistryEntryID=12)]):
            with self.assertRaises(trial.Error):
                trial.usb_entries(value)

    def test_interface_lookup_does_not_assume_en7(self):
        self.assertEqual(trial.usb_interface("Hardware Port: Baiwang\nDevice: en9\n"), "en9")
        self.assertIsNone(trial.usb_interface("Hardware Port: Wi-Fi\nDevice: en0\n"))
        with self.assertRaises(trial.Error):
            trial.usb_interface("Hardware Port: Baiwang\nDevice: en7\nHardware Port: Baiwang\nDevice: en8\n")

    def test_stale_missing_and_wrong_state_never_count_as_healthy(self):
        data = dict(version="1.0.0", state="active", usb_state="CONFIGURED", usb_sleep=0,
                    updated_uptime=100, host_age=1, uplink_age=2)
        self.assertTrue(trial.healthy(data))
        for change in ({"host_age": None}, {"host_age": 31}, {"usb_sleep": 1},
                       {"state": "limited"}, {"updated_uptime": True}, {"uplink_age": -1}):
            self.assertFalse(trial.healthy(dict(data, **change)))

    def observe(self, scan, sample=None, address=lambda _: True):
        now = [0.0]
        events = []
        def pause(seconds):
            now[0] += seconds
        result = trial.observe(frozenset({11}), 100, lambda stage, _: events.append(stage),
                               scan=lambda: scan(now[0]), locate=lambda: "en9",
                               address=address, clock=lambda: now[0], pause=pause,
                               sample=sample or (lambda *a, **k: {"updated_uptime": 200 + int(now[0])}))
        return result, events

    def test_observer_requires_new_enumeration_and_sustained_fresh_data(self):
        result, events = self.observe(lambda t: frozenset() if t < 1 else frozenset({12}))
        self.assertTrue(result)
        self.assertEqual(events, ["enumeration", "address", "communication", "stable"])

    def test_observer_does_not_accept_unchanged_device_or_stalled_status(self):
        result, events = self.observe(lambda _: frozenset({11}))
        self.assertFalse(result)
        self.assertEqual(events, ["enumeration_timeout"])
        result, events = self.observe(lambda _: frozenset({12}),
                                      sample=lambda *a, **k: {"updated_uptime": 200})
        self.assertFalse(result)
        self.assertEqual(events[-1], "stability_lost")

    def test_observer_bounds_dhcp_wait_and_rejects_link_loss(self):
        result, events = self.observe(lambda _: frozenset({12}), address=lambda _: False)
        self.assertFalse(result)
        self.assertEqual(events[-1], "address_timeout")
        result, events = self.observe(lambda t: frozenset({12}) if t < 5 else frozenset())
        self.assertFalse(result)
        self.assertEqual(events[-1], "stability_lost")


class ExecutorFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def execute(self, override="", command="trial_execute"):
        # Replace the device/lock/clock/sleep seams only after sourcing library
        # mode. This verifies decisions, not real flock, signals or kernel calls.
        harness = '''set -- library; . %s
TRIAL=%s
: > "$TRIAL/events"
flock() { return 0; }
sleep() { :; }
sync() { :; }
trial_preflight() { return 0; }
trial_guard_alive() { return 0; }
trial_control_matches() { return 0; }
trial_clock() { echo 200; }
trial_note() { echo "note $1 $2" >> "$TRIAL/events"; }
trial_write() { echo "write $1" >> "$TRIAL/events"; }
%s
%s
''' % (shlex.quote(str(SCRIPT)), shlex.quote(str(self.directory)), override, command)
        result = subprocess.run(["sh", "-c", harness], text=True, capture_output=True)
        return result, (self.directory / "events").read_text()

    def test_exactly_one_disable_restore_and_no_second_trial(self):
        result, events = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count("write 0\n"), 1)
        self.assertEqual(events.count("write 1\n"), 1)
        result, events = self.execute()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("write ", events)

    def test_bad_preflight_or_uncommitted_intent_never_disables(self):
        for override in ("trial_preflight() { return 1; }", "trial_note() { return 1; }",
                         "trial_guard_alive() { return 1; }"):
            result, events = self.execute(override)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("write ", events)

    def test_timeout_is_unknown_and_restore_is_still_attempted_once(self):
        result, events = self.execute('trial_write() { echo "write $1" >> "$TRIAL/events"; test "$1" != 0 || return 143; }')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("note disconnect_returned timeout", events)
        self.assertEqual(events.count("write 1\n"), 1)

    def test_journal_failure_after_disable_does_not_block_restore(self):
        result, events = self.execute('trial_note() { echo "note $1 $2" >> "$TRIAL/events"; test "$1" = disconnect_requested; }')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count("write 1\n"), 1)
        self.assertTrue((self.directory / "emergency-main").exists())

    def test_guard_never_steals_busy_operation_lock(self):
        (self.directory / "issued").write_text("100\n")
        result, events = self.execute('flock() { return 1; }', "trial_guard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("write ", events)
        self.assertEqual((self.directory / "guard.result").read_text().strip(), "operation_busy")

    def test_guard_fallback_only_restores_and_never_claims_host_recovery(self):
        (self.directory / "issued").write_text("100\n")
        result, events = self.execute('trial_control_matches() { return 1; }', "trial_guard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, "write 1\n")
        self.assertEqual((self.directory / "guard.result").read_text().strip(), "restore_call_ok")
