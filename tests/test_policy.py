import dataclasses
import unittest

from cellforge.policy import Controller, Observation, Settings, Traffic


def observed(**changes):
    base = Observation(attached=True, usb="configured", sim_ready=True,
                       radio="lte", strong_signal=True, host_ok=True,
                       host_seen=0, uplink_ok=True, uplink_seen=0,
                       wakeup_supported=True, wakeup_armed=True)
    return dataclasses.replace(base, **changes)


class ConnectionPolicyTests(unittest.TestCase):
    def test_fresh_two_sided_evidence_and_zero_traffic_are_active(self):
        self.assertEqual(Controller().tick(observed(), 0).led, "blue_solid")

    def test_expiry_has_bounded_grace_and_dashboard_is_not_required(self):
        c = Controller()
        c.tick(observed(), 0)
        self.assertEqual(c.tick(observed(), 31).led, "blue_solid")
        result = c.tick(observed(), 36)
        self.assertEqual(result.state, "checking")
        self.assertIsNone(result.led)
        self.assertIsNone(result.intent)

    def test_missing_or_future_evidence_never_initially_lights_blue(self):
        for change in ({"host_seen": None}, {"uplink_seen": None},
                       {"host_seen": 10}, {"host_ok": None}, {"sim_ready": None}):
            with self.subTest(change=change):
                self.assertNotEqual(Controller().tick(observed(**change), 0).led,
                                    "blue_solid")

    def test_suspend_requires_both_implementation_and_host_permission(self):
        for changes in ({"wakeup_supported": False}, {"wakeup_armed": False},
                        {"wakeup_armed": None}):
            result = Controller().tick(observed(usb="suspended", **changes), 0)
            self.assertEqual(result.state, "limited")
            self.assertIsNone(result.intent)

    def test_one_pending_action_and_strict_attempt_budget(self):
        c = Controller(Settings(max_attempts=2))
        obs = observed(usb="suspended")
        first = c.tick(obs, 0)
        self.assertEqual(first.led, "blue_blink")
        self.assertEqual(first.intent.kind, "request_usb_wakeup")
        self.assertIsNone(c.tick(obs, 1).intent)
        self.assertTrue(c.complete(first.intent.token, 2))
        self.assertFalse(c.complete(first.intent.token, 2))
        self.assertEqual(c.tick(obs, 3).state, "backoff")
        second = c.tick(obs, 17)
        self.assertIsNotNone(second.intent)
        self.assertFalse(c.complete(first.intent.token, 18))
        self.assertTrue(c.complete(second.intent.token, 18))
        self.assertEqual(c.tick(obs, 33).reason, "attempt_budget_exhausted")

    def test_timeout_is_unknown_outcome_then_backoff_not_immediate_retry(self):
        c = Controller()
        obs = observed(usb="suspended")
        first = c.tick(obs, 0)
        self.assertEqual(c.tick(obs, 5).reason, "wakeup_timeout")
        self.assertFalse(c.complete(first.intent.token, 6))
        self.assertEqual(c.tick(obs, 6).state, "backoff")

    def test_request_completion_does_not_prove_reconnection(self):
        c = Controller()
        result = c.tick(observed(usb="suspended"), 10)
        c.complete(result.intent.token, 11)
        self.assertNotEqual(c.tick(observed(), 12).led, "blue_solid")
        self.assertEqual(c.tick(observed(host_seen=13, uplink_seen=13), 13).led,
                         "blue_solid")

    def test_confirmed_detach_cancels_actions_and_old_evidence(self):
        c = Controller()
        pending = c.tick(observed(usb="suspended"), 0).intent
        result = c.tick(observed(attached=False), 1)
        self.assertEqual(result.state, "detached")
        self.assertEqual(c.attempts, 0)
        self.assertFalse(c.complete(pending.token, 2))
        self.assertNotEqual(c.tick(observed(), 3).led, "blue_solid")

    def test_unknown_attachment_cannot_start_recovery(self):
        result = Controller().tick(observed(attached=None, usb="suspended"), 0)
        self.assertEqual(result.state, "unknown")
        self.assertIsNone(result.intent)

    def test_red_faults_override_pending_recovery(self):
        for changes, led in [({"sim_ready": False}, "red_solid"),
                             ({"radio": "none"}, "red_blink")]:
            c = Controller()
            pending = c.tick(observed(usb="suspended"), 0).intent
            self.assertEqual(c.tick(observed(**changes), 1).led, led)
            self.assertFalse(c.complete(pending.token, 2))

    def test_green_yellow_strength_matrix_after_confirmed_failure(self):
        for radio, color in [("lte", "green"), ("legacy", "yellow")]:
            for strong, pattern in [(True, "solid"), (False, "blink")]:
                obs = observed(radio=radio, strong_signal=strong, host_ok=False)
                result = Controller().tick(obs, 0)
                self.assertEqual(result.led, color + "_" + pattern)
                self.assertIsNone(result.intent)

    def test_missing_signal_does_not_invent_led_and_uplink_failure_never_reboots(self):
        obs = observed(strong_signal=None, uplink_ok=False)
        result = Controller().tick(obs, 0)
        self.assertIsNone(result.led)
        self.assertIsNone(result.intent)

    def test_invalid_times_and_configuration_are_rejected(self):
        for changes in ({"evidence_ttl": 0}, {"action_timeout": float("nan")},
                        {"max_attempts": 0}):
            with self.assertRaises(ValueError):
                Settings(**changes)
        c = Controller()
        c.tick(observed(), 2)
        with self.assertRaises(ValueError):
            c.tick(observed(), 1)


class TrafficTests(unittest.TestCase):
    def test_counter_baseline_speed_and_idle(self):
        t = Traffic()
        self.assertEqual(t.sample(0, "a", 100, 200)["quality"], "limited")
        result = t.sample(2, "a", 120, 260)
        self.assertEqual(result["upload_bytes"], 20)
        self.assertEqual(result["download_bytes_per_second"], 30)
        self.assertEqual(t.sample(4, "a", 120, 260)["upload_bytes_per_second"], 0)

    def test_missing_sample_retains_totals_and_invalidates_gap_speed(self):
        t = Traffic()
        t.sample(0, "a", 0, 0)
        self.assertEqual(t.sample(1)["quality"], "missing")
        result = t.sample(2, "a", 20, 40)
        self.assertEqual(result["upload_bytes"], 20)
        self.assertIsNone(result["upload_bytes_per_second"])
        self.assertEqual(t.sample(3, "a", 25, 50)["quality"], "available")

    def test_reset_or_interface_replacement_does_not_lose_total_or_invent_speed(self):
        t = Traffic()
        t.sample(0, "a", 100, 100)
        t.sample(1, "a", 120, 150)
        reset = t.sample(2, "a", 0, 0)
        self.assertEqual(reset["download_bytes"], 50)
        self.assertIsNone(reset["download_bytes_per_second"])
        replaced = t.sample(3, "b", 9000, 9000)
        self.assertEqual(replaced["upload_bytes"], 20)
        self.assertEqual(replaced["discontinuities"], 2)

    def test_partial_sample_is_missing_and_invalid_counters_are_rejected(self):
        t = Traffic()
        self.assertEqual(t.sample(0, "a", 1, None)["quality"], "missing")
        with self.assertRaises(ValueError):
            t.sample(1, "a", -1, 2)
        with self.assertRaises(ValueError):
            Traffic().sample(0, "a", 1.5, 2)
