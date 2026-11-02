import contextlib
import io
import unittest
from unittest import mock

from scripts import module_access as access
from test_ecm_tool import Module


class Device(Module):
    def __init__(self, composition=access.ORIGINAL, **kwargs):
        super().__init__(mode=1, composition=",".join(hex(x) for x in composition), **kwargs)
        self.composition_writes = []

    def command(self, cmd, reset=False):
        if cmd.startswith('AT+QCFG="usbcfg",'):
            self.calls.append(cmd)
            self.composition_writes.append(cmd)
            if self.write_error:
                raise access.ecm.ToolError("rejected or uncertain write")
            if not self.readback_error:
                self.composition = cmd.split(",", 1)[1]
            return "OK"
        return super().command(cmd, reset)


class ModuleAccessTests(unittest.TestCase):
    def setUp(self):
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_enable_and_restore_only_change_adb_bit_once_and_restart_once(self):
        for source, target in [(access.ORIGINAL, access.WITH_ADB),
                               (access.WITH_ADB, access.ORIGINAL)]:
            dev = Device(source)
            self.assertTrue(access.transition(dev, target, lambda: True))
            self.assertEqual(dev.composition_writes, [access.composition_command(target)])
            self.assertEqual(dev.calls.count("AT+CFUN=1,1"), 1)
            self.assertFalse(any(x.startswith('AT+QCFG="usbnet",') for x in dev.calls))

    def test_cancel_noop_and_changed_confirmation_never_write(self):
        dev = Device()
        self.assertFalse(access.transition(dev, access.WITH_ADB, lambda: False))
        self.assertFalse(access.transition(dev, access.ORIGINAL, mock.Mock(side_effect=AssertionError)))
        self.assertEqual(dev.composition_writes, [])
        def changed():
            dev.firmware = "changed"
            return True
        with self.assertRaises(access.ecm.ToolError):
            access.transition(dev, access.WITH_ADB, changed)
        self.assertEqual(dev.composition_writes, [])

    def test_wrong_baseline_or_arbitrary_target_never_write(self):
        for dev, target in [(Device(firmware="OTHER"), access.WITH_ADB),
                            (Device(composition=(1, 2, 3)), access.WITH_ADB),
                            (Device(), (1, 2, 3))]:
            with self.assertRaises(access.ecm.ToolError):
                access.transition(dev, target, lambda: True)
            self.assertEqual(dev.composition_writes, [])

    def test_rejected_write_or_readback_mismatch_never_retry_or_restart(self):
        for error in ("write_error", "readback_error"):
            dev = Device()
            setattr(dev, error, True)
            with self.assertRaises(access.ecm.ToolError):
                access.transition(dev, access.WITH_ADB, lambda: True)
            self.assertEqual(len(dev.composition_writes), 1)
            self.assertNotIn("AT+CFUN=1,1", dev.calls)

    def test_transport_allowlist_and_reset_flag_remain_enforced(self):
        dev = access.USB()
        for cmd in ('AT+QADBKEY="guess"', 'AT+QCFG="usbcfg",1', "AT+CGSN"):
            with self.assertRaises(access.ecm.ToolError):
                dev.command(cmd)
        with self.assertRaises(access.ecm.ToolError):
            dev.command(access.composition_command(access.WITH_ADB), reset=True)
        with mock.patch.object(dev, "_exchange", return_value="OK") as exchange:
            dev.command(access.composition_command(access.WITH_ADB))
            exchange.assert_called_once()

    def test_cli_defaults_to_read_only_status(self):
        dev = Device()
        with mock.patch.object(access, "USB", return_value=dev):
            self.assertEqual(access.main([]), 0)
        self.assertEqual(dev.composition_writes, [])
        self.assertNotIn("AT+CFUN=1,1", dev.calls)
