import contextlib
import dataclasses
import io
import unittest
from unittest import mock

from scripts import module_access as access
from test_module_access import Device


class AuthorizationDevice(Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.authorizations = 0
        self.auth_error = False
        self.full_revision = access.FULL_REVISION
        self.challenge_reply = "+QADBKEY: 12345678\nOK"

    def command(self, cmd, reset=False):
        if cmd == "AT+QGMR":
            self.calls.append(cmd)
            return self.full_revision + "\nOK"
        if cmd == "AT+QADBKEY?":
            self.calls.append(cmd)
            return self.challenge_reply
        return super().command(cmd, reset)

    def submit_authorization(self, password):
        self.authorizations += 1
        if self.auth_error:
            raise access.ecm.ToolError("authorization rejected")


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_one_authorization_then_one_bit_write_then_one_restart(self):
        for pending in (False, True):
            dev = AuthorizationDevice()
            dev.readback_error = pending  # Original value until reboot is now explicitly permitted.
            self.assertTrue(access.authorize_and_enable(dev, lambda: True))
            self.assertEqual(dev.authorizations, 1)
            self.assertEqual(dev.composition_writes, [access.composition_command(access.WITH_ADB)])
            self.assertEqual(dev.calls.count("AT+CFUN=1,1"), 1)

    def test_cancel_unknown_revision_and_unknown_challenge_never_authorize(self):
        cancelled = AuthorizationDevice()
        self.assertFalse(access.authorize_and_enable(cancelled, lambda: False))
        self.assertEqual(cancelled.authorizations, 0)
        for setting, value in (("full_revision", "OTHER"),
                               ("challenge_reply", "+QADBKEY: UNKNOWN\nOK")):
            dev = AuthorizationDevice()
            setattr(dev, setting, value)
            with self.assertRaises(access.ecm.ToolError):
                access.authorize_and_enable(dev, lambda: True)
            self.assertEqual(dev.authorizations, 0)
            self.assertEqual(dev.composition_writes, [])

    def test_authorization_rejection_never_changes_composition_or_restarts(self):
        dev = AuthorizationDevice()
        dev.auth_error = True
        with self.assertRaises(access.ecm.ToolError):
            access.authorize_and_enable(dev, lambda: True)
        self.assertEqual(dev.authorizations, 1)
        self.assertEqual(dev.composition_writes, [])
        self.assertNotIn("AT+CFUN=1,1", dev.calls)

    def test_only_adb_bit_may_be_pending_and_all_other_state_is_exact(self):
        before = access.ecm.State(1, access.ORIGINAL, "QDC507", "QDC507GLEFM21")
        access.validate_pending(before, before)
        access.validate_pending(before, dataclasses.replace(before, composition=access.WITH_ADB))
        for after in (dataclasses.replace(before, mode=0),
                      dataclasses.replace(before, firmware="changed"),
                      dataclasses.replace(before, composition=access.WITH_ADB[:-1] + (1,))):
            with self.assertRaises(access.ecm.ToolError):
                access.validate_pending(before, after)

    def test_sensitive_transport_failure_is_redacted_and_never_retried(self):
        dev = access.USB()
        with mock.patch.object(dev, "_exchange", side_effect=OSError("0jXKXQwSwMxYoeg")) as exchange:
            with self.assertRaises(access.ecm.ToolError) as error:
                dev.submit_authorization("0jXKXQwSwMxYoeg")
            self.assertNotIn("0jXKXQwSwMxYoeg", str(error.exception))
            with self.assertRaises(access.ecm.ToolError):
                dev.submit_authorization("0jXKXQwSwMxYoeg")
            self.assertEqual(exchange.call_count, 1)
