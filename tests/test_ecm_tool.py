import contextlib
import io
import unittest
from unittest import mock

from scripts import cellforge as c


class Module:
    def __init__(self, mode=0, model="QDC507", firmware="QDC507GLEFM21",
                 composition="0x2ca3,0x4006,1,1,1,1,1,0,0"):
        self.mode, self.model, self.firmware = mode, model, firmware
        self.composition = composition
        self.calls = []
        self.write_error = False
        self.readback_error = False
        self.has_ecm = mode == 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def command(self, cmd, reset=False):
        self.calls.append(cmd)
        if cmd == "AT":
            return "AT\nOK"
        if cmd in ("AT+CGMM", "AT+CGMR"):
            return cmd + "\n" + (self.model if cmd == "AT+CGMM" else self.firmware) + "\nOK"
        if cmd == 'AT+QCFG="usbcfg"':
            return '+QCFG: "usbcfg",' + self.composition + "\nOK"
        if cmd == 'AT+QCFG="usbnet"':
            return '+QCFG: "usbnet",%d\nOK' % self.mode
        if cmd in ('AT+QCFG="usbnet",0', 'AT+QCFG="usbnet",1'):
            if not self.readback_error:
                self.mode = int(cmd[-1])
            if self.write_error:
                raise c.ToolError("uncertain acknowledgement")
            return "OK"
        if cmd == "AT+CFUN=1,1" and reset:
            return "OK"
        raise AssertionError("Unexpected command: " + cmd)

    @property
    def writes(self):
        return [x for x in self.calls if x.startswith('AT+QCFG="usbnet",')
                or x == "AT+CFUN=1,1"]


class FramingTests(unittest.TestCase):
    def test_chunked_reply_and_unsolicited_records(self):
        r = c.Reply()
        self.assertIsNone(r.feed(b"+QIND: SMS DONE\r\nAT\r\r\nO"))
        result = r.feed(b"K\r\n")
        self.assertIn("OK", result)

    def test_error_and_unterminated_ok(self):
        self.assertIsNone(c.Reply().feed(b"\r\nOK"))
        for data in [b"\r\nERROR\r\n", b"\r\n+CME ERROR: 10\r\n"]:
            with self.assertRaises(c.ToolError):
                c.Reply().feed(data)

    def test_bounded_response(self):
        with self.assertRaises(c.ToolError):
            c.Reply().feed(b"x" * 65537)

    def test_refuse_unrecognized_commands_before_usb(self):
        for cmd in ["AT+QCFG=\"usbcfg\",1", "AT+CGSN\rAT+CFUN=1,1", "AT+QGDCNT=0"]:
            with self.assertRaises(c.ToolError):
                c.USB().command(cmd)

    def test_device_selection_requires_exactly_one(self):
        for candidates in [[], [object(), object()]]:
            with self.assertRaises(c.ToolError):
                c.single_device(candidates)
        target = object()
        self.assertIs(c.single_device([target]), target)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_cancel_has_no_writes(self):
        dev = Module()
        self.assertFalse(c.change_mode(dev, 1, lambda _: False))
        self.assertEqual(dev.writes, [])

    def test_both_target_modes_are_noops_without_confirmation(self):
        for mode in (0, 1):
            dev = Module(mode)
            confirm = mock.Mock(side_effect=AssertionError("must not prompt"))
            self.assertFalse(c.change_mode(dev, mode, confirm))
            self.assertEqual(dev.writes, [])

    def test_enable_and_disable_write_once_then_restart_once(self):
        for source, target in ((0, 1), (1, 0)):
            dev = Module(source)
            self.assertTrue(c.change_mode(dev, target, lambda _: True))
            self.assertEqual(dev.writes, ['AT+QCFG="usbnet",%d' % target, "AT+CFUN=1,1"])
            self.assertEqual(dev.calls[-1], "AT+CFUN=1,1")
            self.assertNotIn("AT+CGSN", dev.calls)

    def test_different_firmware_and_composition_are_reported_and_accepted(self):
        dev = Module(firmware="QDC507_FUTURE", composition="0x2ca3,0x4006,1,0,1")
        state = c.read_state(dev)
        self.assertEqual(state.firmware, "QDC507_FUTURE")
        self.assertEqual(state.composition, (c.VID, c.PID, 1, 0, 1))
        self.assertTrue(c.change_mode(dev, 1, lambda _: True))

    def test_wrong_model_and_unsupported_modes_refused(self):
        for dev in (Module(model="OTHER"), Module(2), Module(3)):
            with self.assertRaises(c.ToolError):
                c.change_mode(dev, 1, lambda _: True)
            self.assertEqual(dev.writes, [])

    def test_malformed_or_ambiguous_queries_refused(self):
        for dev in (Module(firmware=""), Module(firmware="version1\nversion2"),
                    Module(composition="invalid"), Module(mode=4)):
            with self.assertRaises(c.ToolError):
                c.read_state(dev)
            self.assertEqual(dev.writes, [])

    def test_state_change_during_confirmation_refused(self):
        dev = Module()
        def confirm(_):
            dev.mode = 1
            return True
        with self.assertRaisesRegex(c.ToolError, "state changed"):
            c.change_mode(dev, 1, confirm)
        self.assertEqual(dev.writes, [])

    def test_uncertain_write_does_not_retry_or_restart(self):
        dev = Module()
        dev.write_error = True
        with self.assertRaises(c.ToolError):
            c.change_mode(dev, 1, lambda _: True)
        self.assertEqual(dev.writes, ['AT+QCFG="usbnet",1'])

    def test_readback_mismatch_does_not_restart(self):
        dev = Module()
        dev.readback_error = True
        with self.assertRaisesRegex(c.ToolError, "readback mismatch"):
            c.change_mode(dev, 1, lambda _: True)
        self.assertEqual(dev.writes, ['AT+QCFG="usbnet",1'])

    def test_cli_default_status_and_both_switch_commands(self):
        for args, source, expected in [
            ([], 1, []), (["status"], 1, []),
            (["enable-ecm", "--yes"], 0, ['AT+QCFG="usbnet",1', "AT+CFUN=1,1"]),
            (["disable-ecm", "--yes"], 1, ['AT+QCFG="usbnet",0', "AT+CFUN=1,1"]),
        ]:
            dev = Module(source)
            with mock.patch.object(c, "USB", return_value=dev) as factory:
                self.assertEqual(c.main(args), 0)
                factory.assert_called_once()
            self.assertEqual(dev.writes, expected)


if __name__ == "__main__":
    unittest.main()
