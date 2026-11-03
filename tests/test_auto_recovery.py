"""State/semantic and executor fault fixtures. No real USB or device data writes."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


MODULE = Path(__file__).resolve().parent.parent / "module"


class AutomaticPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "state").write_text("")

    def sample(self, **changes):
        value = dict(now=100, usb="CONFIGURED", sleep=0, host_at=100, uplink_at=100,
                     peer_known=1, sim=1, alarm=0, radio=4, probe_seq=1, probe_result="ok",
                     busy=0, phase="none", deadline=0, done=0, guard_done=0,
                     used=0, blocked=0, last_action=0)
        value.update(changes)
        (self.root / "obs").write_text("".join("%s %s\n" % pair for pair in value.items()))
        subprocess.run(["awk", "-v", "state_out=" + str(self.root / "next"),
                        "-v", "decision_out=" + str(self.root / "decision"),
                        "-f", str(MODULE / "recovery.awk"), str(self.root / "state"),
                        str(self.root / "obs")], check=True, capture_output=True)
        (self.root / "next").replace(self.root / "state")
        mode, reason, action, finish, clear = (self.root / "decision").read_text().split()
        return mode, reason, int(action), int(finish), int(clear)

    def fail(self, now, seq, **extra):
        values = dict(now=now, host_at=0, uplink_at=now, probe_seq=seq, probe_result="fail")
        values.update(extra)
        return self.sample(**values)

    def eligible(self):
        self.sample()
        self.fail(101, 2)
        self.fail(132, 3)
        self.fail(148, 4)
        return self.fail(164, 5)

    def test_grace_and_three_distinct_failures_required(self):
        self.sample()
        self.assertEqual(self.fail(101, 2)[2], 0)
        self.assertEqual(self.fail(130, 3)[2], 0)
        self.assertEqual(self.fail(132, 4)[2], 0)
        self.assertEqual(self.fail(133, 4)[2], 0)
        self.assertEqual(self.fail(148, 5)[2], 0)
        self.assertEqual(self.fail(164, 6)[2], 1)

    def test_missing_target_unknown_sleep_radio_and_uplink_never_reset(self):
        for extra in ({"peer_known": 0}, {"probe_result": "missing"}, {"sleep": "none"},
                      {"sleep": 1}, {"sim": 0}, {"alarm": 1}, {"radio": "none"}, {"uplink_at": 0}):
            (self.root / "state").write_text("")
            self.sample()
            for seq, now in enumerate((101, 132, 148, 164, 180), 2):
                self.assertEqual(self.fail(now, seq, **extra)[2], 0, extra)

    def test_no_initial_baseline_or_new_attachment_never_resets(self):
        for seq, now in enumerate((100, 132, 148, 164, 180), 1):
            self.assertEqual(self.fail(now, seq)[2], 0)
        self.sample(now=200, host_at=200, uplink_at=200)
        self.sample(now=201, usb="CONNECTED", host_at=0)
        for seq, now in enumerate((202, 235, 251, 267), 10):
            self.assertEqual(self.fail(now, seq)[2], 0)

    def test_sleep_resume_grace_without_require_sleep_event(self):
        self.sample()
        self.fail(101, 2, sleep=1)
        self.assertEqual(self.fail(200, 3)[1], "resume_grace")
        self.assertEqual(self.fail(229, 4)[2], 0)
        self.assertEqual(self.fail(231, 5)[2], 0)
        self.assertEqual(self.fail(247, 6)[2], 0)
        self.assertEqual(self.fail(263, 7)[2], 1)
        (self.root / "state").write_text("")
        self.assertEqual(self.eligible()[2], 1)

    def test_spent_incident_and_boot_budget_survive_new_state_file(self):
        for limit in ({"used": 1, "blocked": 1}, {"used": 3}):
            (self.root / "state").write_text("")
            self.sample(**limit)
            for seq, now in enumerate((101, 132, 148, 164, 180), 2):
                self.assertEqual(self.fail(now, seq, **limit)[2], 0)

    def test_owned_detach_does_not_end_incident_or_trigger_another_action(self):
        self.assertEqual(self.eligible()[2], 1)
        result = self.fail(166, 6, usb="DISCONNECTED", busy=1, phase="connecting",
                           used=1, blocked=1, deadline=314)
        self.assertEqual(result[:3], ("recovering", "connecting", 0))
        self.assertEqual(self.fail(210, 7, used=1, blocked=1)[2], 0)

    def test_confirmation_requires_contiguous_healthy_time_and_cooldown(self):
        for now in range(200, 231):
            result = self.sample(now=now, host_at=now, uplink_at=now, busy=1,
                                 phase="waiting", deadline=350, used=1, blocked=1, last_action=190)
            self.assertEqual(result[3], int(now == 230))
        self.assertEqual(self.sample(now=231, host_at=231, uplink_at=231, busy=1,
                                     phase="confirmed", done=1, guard_done=1,
                                     deadline=350, used=1, blocked=1, last_action=190)[3], 1)
        for now in range(232, 311):
            result = self.sample(now=now, host_at=now, uplink_at=now,
                                 used=1, blocked=1, last_action=190)
            self.assertEqual(result[4], int(now == 310))

    def test_unknown_observation_gap_does_not_count_as_stable(self):
        self.sample(now=200, host_at=200, uplink_at=200, used=1, blocked=1, last_action=0)
        result = self.sample(now=240, host_at=240, uplink_at=240, used=1, blocked=1, last_action=0)
        self.assertEqual(result[4], 0)

    def test_response_timeout_and_faults_do_not_clear_pending_owner(self):
        result = self.fail(200, 4, busy=1, phase="waiting", deadline=200,
                           used=1, blocked=1, done=0, guard_done=0)
        self.assertEqual(result[:4], ("failed", "response_timeout", 0, 0))
        result = self.fail(201, 5, busy=1, phase="failed", deadline=200,
                           used=1, blocked=1, done=1, guard_done=1)
        self.assertEqual(result[3], 1)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "work").mkdir()

    def shell(self, override="", command="auto_cycle", source="auto-recover.sh"):
        body = '''set -- library; . %s
AUTO=%s; WORK=$AUTO/work; LOG=$AUTO/events.tsv
: > "$WORK/events"
auto_clock() { echo 200; }
auto_check() { return 0; }
auto_owner() { return 0; }
auto_guard_alive() { return 0; }
auto_control() { return 0; }
auto_born() { echo 1; }
auto_event() { echo "event $1 $2" >> "$WORK/events"; }
auto_write() { echo "write $1" >> "$WORK/events"; }
flock() { return 0; }; sleep() { :; }; sync() { :; }
echo '1 1' > "$WORK/actor.pid"
%s
%s
''' % (shlex.quote(str(MODULE / source)), shlex.quote(str(self.root)), override, command)
        result = subprocess.run(["sh", "-c", body], text=True, capture_output=True)
        return result, (self.root / "work/events").read_text()

    def test_cycle_exactly_once_and_cannot_be_reissued(self):
        result, events = self.shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count("write 0\n"), 1)
        self.assertEqual(events.count("write 1\n"), 1)
        result, events = self.shell()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("write ", events)

    def test_failed_log_or_collector_never_disables(self):
        for extra in ("auto_event() { return 1; }", "auto_owner() { return 1; }",
                      "auto_check() { return 1; }", "auto_guard_alive() { return 1; }"):
            result, events = self.shell(extra)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("write ", events)

    def test_timeout_still_restores_once_without_false_success(self):
        result, events = self.shell('auto_write() { echo "write $1" >> "$WORK/events"; test "$1" != 0 || return 143; }')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events.count("write 1\n"), 1)
        self.assertEqual((self.root / "work/disconnect.result").read_text().strip(), "timeout")

    def test_restore_failure_retains_pending_without_loop(self):
        result, events = self.shell('auto_write() { echo "write $1" >> "$WORK/events"; test "$1" != 1 || return 143; }')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / "work/pending").exists())
        self.assertEqual(events.count("write 1\n"), 1)

    def test_guard_refuses_busy_lock_and_only_restores_if_needed(self):
        (self.root / "work/issued").write_text("100\n")
        result, events = self.shell("flock() { return 1; }", "auto_guard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("write ", events)
        self.assertEqual((self.root / "work/guard.done").read_text().strip(), "operation_busy")
        result, events = self.shell("auto_control() { return 1; }", "auto_guard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events.count("write 1\n"), 1)
        self.assertNotIn("write 0", events)


class PeerTests(unittest.TestCase):
    def test_bound_peer_survives_incomplete_arp_and_discovery_is_bounded(self):
        rows = """IP address HW type Flags HW address Mask Device
192.168.225.22 0x1 0x0 aa:bb:cc:dd:ee:ff * bridge0
192.168.225.23 0x1 0x2 aa:bb:cc:dd:ee:f1 * bridge0
192.168.225.24 0x1 0x2 aa:bb:cc:dd:ee:f2 * bridge0
192.168.225.999 0x1 0x2 aa:bb:cc:dd:ee:f3 * bridge0
192.168.225.25 0x1 0x2 aa:bb:cc:dd:ee:f4 * other0
"""
        def peers(cached):
            return subprocess.run(["awk", "-v", "cached=" + cached, "-f", str(MODULE / "peers.awk")],
                                  input=rows, text=True, capture_output=True, check=True).stdout.split()
        self.assertEqual(peers("192.168.225.22"), ["192.168.225.22", "192.168.225.23"])
        self.assertEqual(peers(""), ["192.168.225.23", "192.168.225.24"])
        self.assertEqual(peers("192.168.225.999"), ["192.168.225.23", "192.168.225.24"])


class BudgetAndLogTests(unittest.TestCase):
    def test_boot_budget_is_not_reset_by_worker_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            code = '''set -- library; . %s; AUTO=%s; clock() { echo 100; }
auto_init; echo 2 > "$AUTO/used"; echo 75 > "$AUTO/last"; : > "$AUTO/blocked"
auto_init; auto_read; printf '%%s %%s %%s\n' "$auto_used" "$auto_last" "$auto_blocked"
echo invalid > "$AUTO/used"; auto_read; echo "$auto_used"
''' % (shlex.quote(str(MODULE / "recovery-worker.sh")), shlex.quote(directory))
            result = subprocess.run(["sh", "-c", code], text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ["2 75 1", "3"])

    def test_orphan_action_with_missing_budget_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "action1").mkdir()
            code = 'set -- library; . %s; AUTO=%s; auto_init; auto_read; echo "$auto_used $auto_blocked"' % (
                shlex.quote(str(MODULE / "recovery-worker.sh")), shlex.quote(directory))
            result = subprocess.run(["sh", "-c", code], text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.strip(), "3 1")

    def test_event_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            code = '''set -- library; . %s; AUTO=%s; LOG=$AUTO/events.tsv; NUMBER=1
flock() { return 0; }; sync() { :; }; auto_clock() { echo 100; }
n=0; while test "$n" -lt 40; do auto_event calls returned || exit 1; n=$((n + 1)); done
''' % (shlex.quote(str(MODULE / "auto-recover.sh")), shlex.quote(directory))
            subprocess.run(["sh", "-c", code], check=True, capture_output=True)
            data = (Path(directory) / "events.tsv").read_bytes()
            self.assertEqual(len(data.splitlines()), 32)
            self.assertLessEqual(len(data), 8192)
