"""Real filesystem/subprocess regressions for the offline digest gate."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from release_gate import GateError, verify  # noqa: E402


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "artifacts"
        self.root.mkdir()
        self.file = self.root / "build.bin"
        self.file.write_bytes(b"known build bytes\n")
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.doc = {"schema_version": 1, "artifacts": [{"path": "build.bin", "sha256": hashlib.sha256(self.file.read_bytes()).hexdigest()}]}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.doc), encoding="utf-8")

    def assert_rejected(self):
        with self.assertRaises(GateError):
            verify(self.manifest, self.root)

    def test_real_digest_passes(self):
        self.assertEqual(verify(self.manifest, self.root), 1)

    def test_tampered_bytes_rejected(self):
        self.file.write_bytes(b"modified")
        self.assert_rejected()

    def test_missing_file_rejected(self):
        self.file.unlink()
        self.assert_rejected()

    def test_path_traversal_rejected(self):
        self.doc["artifacts"][0]["path"] = "../manifest.json"
        self.write_manifest()
        self.assert_rejected()

    def test_absolute_path_rejected(self):
        self.doc["artifacts"][0]["path"] = str(self.file)
        self.write_manifest()
        self.assert_rejected()

    def test_hidden_file_rejected(self):
        self.doc["artifacts"][0]["path"] = ".env"
        self.write_manifest()
        self.assert_rejected()

    def test_duplicate_paths_rejected(self):
        self.doc["artifacts"].append(dict(self.doc["artifacts"][0]))
        self.write_manifest()
        self.assert_rejected()

    def test_invalid_hash_rejected(self):
        self.doc["artifacts"][0]["sha256"] = "not-a-sha"
        self.write_manifest()
        self.assert_rejected()

    def test_empty_artifacts_rejected(self):
        self.doc["artifacts"] = []
        self.write_manifest()
        self.assert_rejected()

    def test_unsupported_schema_rejected(self):
        self.doc["schema_version"] = 2
        self.write_manifest()
        self.assert_rejected()

    def test_extra_field_rejected(self):
        self.doc["unexpected"] = "ignore-me"
        self.write_manifest()
        self.assert_rejected()

    def test_duplicate_json_keys_rejected(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1,"artifacts":[]}', encoding="utf-8")
        self.assert_rejected()

    def test_symlink_rejected(self):
        link = self.root / "linked.bin"
        try:
            link.symlink_to(self.file)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.doc["artifacts"][0]["path"] = "linked.bin"
        self.write_manifest()
        self.assert_rejected()

    def test_cli_failure_is_nonzero(self):
        self.file.write_bytes(b"tampered")
        p = subprocess.run([sys.executable, str(ROOT / "src/release_gate.py"), "--manifest", str(self.manifest), "--root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("REJECTED", p.stderr)

    def test_cli_success_is_zero(self):
        p = subprocess.run([sys.executable, str(ROOT / "src/release_gate.py"), "--manifest", str(self.manifest), "--root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0)
        self.assertIn("VERIFIED: 1 local artifact", p.stdout)


if __name__ == "__main__":
    unittest.main()
