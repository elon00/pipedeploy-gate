"""Offline artifact digest gate. No deployment, signatures, or provenance claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX256 = re.compile(r"[0-9a-f]{64}\Z")


class GateError(ValueError):
    """Invalid manifest or failed local artifact verification."""


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise GateError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def verify(manifest_path: Path, root: Path) -> int:
    """Verify files beneath root against a strict SHA-256 manifest; return count."""
    manifest_path = Path(manifest_path)
    root = Path(root)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise GateError("manifest must be a regular, non-symlink file")
    if manifest_path.stat().st_size > 1024 * 1024:
        raise GateError("manifest exceeds 1 MiB")
    if not root.is_dir() or root.is_symlink():
        raise GateError("root must be a non-symlink directory")
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("invalid UTF-8 JSON manifest") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "artifacts"}:
        raise GateError("manifest must contain only schema_version and artifacts")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise GateError("unsupported schema version")
    artifacts = doc["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise GateError("artifacts must be a nonempty list")
    if len(artifacts) > 10000:
        raise GateError("too many artifacts")
    seen: set[str] = set()
    count = 0
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise GateError("artifact must have only path and sha256")
        rel, expected = item["path"], item["sha256"]
        if not isinstance(rel, str) or not isinstance(expected, str) or not HEX256.fullmatch(expected):
            raise GateError("invalid path or lowercase SHA-256")
        parts = rel.split("/")
        if (not rel or rel.startswith("/") or "\\" in rel or ":" in rel
                or any(p in ("", ".", "..") or p.startswith(".") for p in parts)):
            raise GateError("unsafe artifact path")
        normalized = rel.casefold()
        if normalized in seen:
            raise GateError("duplicate artifact path")
        seen.add(normalized)
        candidate = root
        for part in parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise GateError("symlink in artifact path")
        if not candidate.is_file():
            raise GateError("missing or non-file artifact")
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise GateError("artifact SHA-256 mismatch")
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline artifact SHA-256 verification; does not deploy")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = verify(args.manifest, args.root)
    except (GateError, OSError) as exc:
        parser.exit(1, f"REJECTED: {exc}\n")
    print(f"VERIFIED: {count} local artifact digest(s); no provenance/deployment certification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
