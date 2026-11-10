import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class DevicePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / "state").write_text("")

    def sample(self, **changes):
        obs = dict(now=100, tx=1000, rx=2000, epoch=7, usb="CONFIGURED", sleep=0,
                   sim=1, radio=4, rssi=-54, radio_alarm=0, host_at=100, uplink_at=100,
                   probing=0, attempts=0, host_ip="192.168.225.22", cell_ip="10.0.0.2",
                   last_recovery="none", led_owned=1)
        obs.update(changes)
        (self.path / "obs").write_text("".join(str(k) + " " + str(v) + "\n" for k, v in obs.items()))
        result = subprocess.run(["awk", "-v", "state_out=" + str(self.path / "next"),
                                 "-v", "led_out=" + str(self.path / "led"),
                                 "-f", str(ROOT / "module/policy.awk"),
                                 str(self.path / "state"), str(self.path / "obs")],
                                text=True, capture_output=True, check=True)
        (self.path / "next").replace(self.path / "state")
        return json.loads(result.stdout)

    def test_actual_fresh_evidence_and_traffic_delta(self):
        first = self.sample()
        self.assertEqual(first["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(first["led"], "blue_solid")
        self.assertIsNone(first["upload_Bps"])
        next_sample = self.sample(now=102, tx=1200, rx=2600)
        self.assertEqual(next_sample["upload_bytes"], 200)
        self.assertEqual(next_sample["download_Bps"], 300)

    def test_signal_and_red_priority_matrix(self):
        for changes, led in [({"sim": 0}, "red_solid"),
                             ({"radio_alarm": 1}, "red_blink"),
                             ({"host_at": 0}, "green_solid"),
                             ({"host_at": 0, "rssi": -90}, "green_blink"),
                             ({"host_at": 0, "radio": 3}, "yellow_solid"),
                             ({"host_at": 0, "radio": 6, "rssi": -90}, "yellow_blink")]:
            with self.subTest(changes=changes):
                self.assertEqual(self.sample(**changes)["led"], led)

    def test_expired_or_suspended_link_cannot_be_blue_solid(self):
        self.assertNotEqual(self.sample(now=131)["led"], "blue_solid")
        self.assertNotEqual(self.sample(sleep=1)["led"], "blue_solid")
        self.assertEqual(self.sample(sleep=1, probing=1)["led"], "blue_blink")
        self.assertEqual(self.sample(sleep=1, attempts=3)["state"], "backoff")

    def test_missing_counter_gap_and_reset_preserve_totals_without_fake_speed(self):
        self.sample()
        self.sample(now=101, tx=1100, rx=2200)
        self.sample(now=102, tx="none", rx="none")
        resumed = self.sample(now=103, tx=1300, rx=2600)
        self.assertEqual(resumed["download_bytes"], 600)
        self.assertIsNone(resumed["download_Bps"])
        reset = self.sample(now=104, tx=0, rx=0)
        self.assertEqual(reset["download_bytes"], 600)
        self.assertEqual(reset["discontinuities"], 1)

    def test_suspend_keeps_session_but_confirmed_disconnect_starts_new_one(self):
        self.sample()
        self.sample(now=101, tx=1100, rx=2200, sleep=1)
        self.assertEqual(self.sample(now=102, tx=1200, rx=2400)["download_bytes"], 400)
        self.sample(now=103, usb="DISCONNECTED")
        self.sample(now=107, usb="DISCONNECTED")
        new_session = self.sample(now=108)
        self.assertEqual(new_session["download_bytes"], 0)
        self.assertEqual(new_session["session_seconds"], 0)

    def test_owned_recovery_preserves_session_and_marks_uncertainty(self):
        self.sample()
        self.sample(now=101, tx=1200, rx=2400)
        self.sample(now=102, tx=1200, rx=2400, recovery_owned=1, recovery_mode="recovering", host_at=0)
        during = self.sample(now=110, usb="DISCONNECTED", recovery_owned=1,
                             recovery_mode="recovering", tx=1400, rx=2800, host_at=0)
        self.assertEqual(during["download_bytes"], 800)
        self.assertTrue(during["session_uncertain"])
        self.assertIsNone(during["download_Bps"])
        after = self.sample(now=115, recovery_owned=0, host_at=115, uplink_at=115,
                            tx=1500, rx=3000, recovery_mode="cooldown")
        self.assertEqual(after["download_bytes"], 1000)
        self.assertEqual(after["session_seconds"], 15)
        self.assertFalse(after["session_uncertain"])
        self.assertEqual(after["discontinuities"], 1)

    def test_recovery_confirmation_cannot_use_old_blue_evidence(self):
        self.assertEqual(self.sample(recovery_owned=1, recovery_mode="confirming")["led"], "blue_blink")
        self.assertEqual(self.sample(sim=0, recovery_owned=1, recovery_mode="recovering")["led"], "red_solid")
