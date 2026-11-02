import json
import unittest
from unittest import mock

from scripts import probe_module as probe


class AuthorizationProbeTests(unittest.TestCase):
    def test_only_summary_is_exported_and_firmware_is_allowlisted(self):
        dev = mock.Mock()
        dev.command.side_effect = ["AT+QGMR\n+PRIVATE: hidden\nQDC507GLEFM21_01.001.02.004\nOK",
                                   "+QADBKEY: 12345678\nOK"]
        result = probe.authorization_summary(dev)
        self.assertEqual(result["full_revision"]["value"], "QDC507GLEFM21_01.001.02.004")
        self.assertTrue(result["adb_challenge"]["eight_digit_numeric"])
        self.assertNotIn("12345678", json.dumps(result))
        self.assertNotIn("hidden", json.dumps(result))
        self.assertEqual(dev.command.call_args_list,
                         [mock.call("AT+QGMR"), mock.call("AT+QADBKEY?")])

    def test_unknown_or_duplicate_formats_never_export_challenge(self):
        for reply in ("+QADBKEY: secret-value\nOK",
                      "+QADBKEY: 12345678\n+QADBKEY: secret-value\nOK", "OK"):
            dev = mock.Mock()
            dev.command.side_effect = ["OK", reply]
            result = probe.authorization_summary(dev)
            self.assertNotIn("secret-value", json.dumps(result))
            self.assertNotIn("12345678", json.dumps(result))
            self.assertFalse(result["adb_challenge"].get("eight_digit_numeric", False))

    def test_explicit_command_rejection_is_reported_as_capability_result(self):
        dev = mock.Mock()
        dev.command.side_effect = probe.ecm.ToolError("Module rejected the AT command; no automatic retry.")
        result = probe.authorization_summary(dev)
        self.assertEqual(result["adb_challenge"]["status"], "command_rejected")

    def test_transport_failure_is_not_reclassified_or_retried(self):
        dev = mock.Mock()
        dev.command.side_effect = probe.ecm.Unavailable("Read-only AT query timed out.")
        with self.assertRaises(probe.ecm.Unavailable):
            probe.authorization_summary(dev)
        self.assertEqual(dev.command.call_count, 1)

    def test_inspection_transport_rejects_unlock_or_reset_variants(self):
        dev = probe.InspectionUSB()
        for cmd, reset in [('AT+QADBKEY="guess"', False), ("AT+QADBKEY?", True),
                           ("AT+QGMR", True)]:
            with self.assertRaises(probe.ecm.ToolError):
                dev.command(cmd, reset)
