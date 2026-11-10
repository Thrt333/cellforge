"""Staging ordering and failure boundaries; no USB or device writes."""
import hashlib
import unittest
from unittest.mock import patch

from scripts import module_runtime as runtime


class StagingTests(unittest.TestCase):
    def stage(self, fail_sync=None, bad_hash=False):
        self.commands = []
        self.files = {name: b"fixture\n" for name in
                      ("cellforge.sh", "recovery-worker.sh", "auto-recover.sh", "web/index.html")}

        def run(device, command):
            self.commands.append(command)
            if command == "sync" and self.commands.count("sync") == fail_sync:
                raise runtime.adb.ecm.ToolError("Synchronization failed")
            if command.startswith("sha256sum "):
                name = next(name for name in self.files if command.endswith("/" + name + ".new"))
                return ("0" * 64 if bad_hash else hashlib.sha256(self.files[name]).hexdigest()) + "  file"
            return ""

        with patch.object(runtime, "package", return_value=("a" * 16, self.files)), \
                patch.object(runtime, "run", side_effect=run):
            return runtime.stage(object())

    def test_payload_is_synced_before_activation_and_link_before_success(self):
        result = self.stage()
        syncs = [i for i, command in enumerate(self.commands) if command == "sync"]
        activation = next(i for i, command in enumerate(self.commands) if "ln -sfn" in command)
        syntax = [i for i, command in enumerate(self.commands) if command.startswith("sh -n ")]
        self.assertEqual(len(syncs), 2)
        self.assertLess(max(syntax), syncs[0])
        self.assertLess(syncs[0], activation)
        self.assertLess(activation, syncs[1])
        self.assertEqual(result["revision"], "a" * 16)
        self.assertEqual(set(result["files"]), set(self.files))

    def test_first_sync_failure_does_not_activate_or_retry(self):
        with self.assertRaisesRegex(runtime.adb.ecm.ToolError, "Synchronization failed"):
            self.stage(fail_sync=1)
        self.assertEqual(self.commands.count("sync"), 1)
        self.assertFalse(any("ln -sfn" in command for command in self.commands))

    def test_link_sync_failure_is_reported_without_retry(self):
        with self.assertRaisesRegex(runtime.adb.ecm.ToolError, "Synchronization failed"):
            self.stage(fail_sync=2)
        self.assertEqual(self.commands.count("sync"), 2)
        self.assertEqual(sum("ln -sfn" in command for command in self.commands), 1)

    def test_hash_mismatch_does_not_activate(self):
        with self.assertRaisesRegex(runtime.adb.ecm.ToolError, "hash mismatch"):
            self.stage(bad_hash=True)
        self.assertNotIn("sync", self.commands)
        self.assertFalse(any("ln -sfn" in command for command in self.commands))
