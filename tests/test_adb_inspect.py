import struct
import time
import unittest

from scripts import adb_inspect as adb


class Wire(adb.USBADB):
    def __init__(self, chunks):
        super().__init__()
        self.chunks = iter(chunks)
        self.sent = []
        self.deadline = time.monotonic() + 1

    def _read_chunk(self):
        return next(self.chunks)

    def _write(self, data):
        self.sent.append(data)


class ADBInspectionTests(unittest.TestCase):
    def test_fragmented_and_coalesced_packets_preserve_all_bytes(self):
        first = adb.encode(b"CNXN", 0x01000000, 4096, b"device::\0")
        second = adb.encode(b"OKAY", 7, 1)
        wire = Wire([first[:7], first[7:] + second])
        self.assertEqual(wire._receive(), (b"CNXN", 0x01000000, 4096, b"device::\0"))
        self.assertEqual(wire._receive(), (b"OKAY", 7, 1, b""))

    def test_invalid_magic_checksum_and_oversize_stop(self):
        packet = adb.encode(b"CNXN", 1, 4096, b"x")
        malformed = bytearray(packet)
        malformed[20] ^= 1
        oversized = struct.pack("<6I", int.from_bytes(b"CNXN", "little"),
                                0, 0, 4097, 0, int.from_bytes(b"CNXN", "little") ^ 0xffffffff)
        for data in (bytes(malformed), packet[:-1] + b"y", oversized):
            with self.assertRaises(adb.ecm.ToolError):
                Wire([data])._receive()

    def test_adb_auth_request_stops_without_key_generation(self):
        wire = Wire([adb.encode(b"AUTH", 1, 0, b"private-token")])
        with self.assertRaises(adb.ecm.ToolError) as error:
            wire.connect()
        self.assertNotIn("private-token", str(error.exception))
        self.assertEqual(len(wire.sent), 2)  # CNXN header and banner only.

    def test_root_shell_reads_and_acknowledges_matching_stream_only(self):
        response = (adb.encode(b"OKAY", 7, 1)
                    + adb.encode(b"WRTE", 7, 1, b"0\n")
                    + adb.encode(b"CLSE", 7, 1))
        wire = Wire([response])
        wire.remote_max = 4096
        self.assertEqual(wire.shell("id -u"), b"0\n")
        with self.assertRaises(adb.ecm.ToolError):
            wire.shell("touch /data/anything")

    def test_mismatched_stream_cannot_supply_root_evidence(self):
        wire = Wire([adb.encode(b"OKAY", 7, 1) + adb.encode(b"WRTE", 8, 1, b"0\n")])
        wire.remote_max = 4096
        with self.assertRaises(adb.ecm.ToolError):
            wire.shell("id -u")

    def test_inventory_fits_legacy_payload_and_avoids_sensitive_dumps(self):
        for command in (adb.INVENTORY, adb.DETAILS, adb.CONTROLS, adb.FACTORY):
            self.assertLessEqual(len(b"shell:" + command.encode("ascii") + b"\0"), 4096)
            for forbidden in ("CGSN", "printenv", "/proc/1/cmdline", "adb push", "mount -o", "chmod"):
                self.assertNotIn(forbidden, command)
