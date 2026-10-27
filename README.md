# Pipedeploy Gate — offline artifact integrity check

This repository is the **tests** component (QMOOSA-0890) of the QMOOSA-1000 deployment-pipeline family. Its implemented scope is **local SHA-256 artifact integrity verification**, not a deployment system.

## Run locally (Python 3.11+, standard library only)

```bash
python -m compileall -q src tests
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/reality_check_harness.py
cargo fmt --all -- --check
cargo test --all-targets
```

To verify your own artifacts, prepare a UTF-8 JSON manifest with a nonempty artifact list:

```json
{
  "schema_version": 1,
  "artifacts": [
    {"path": "build.bin", "sha256": "<64 lowercase hex SHA-256 characters>"}
  ]
}
```

```bash
python src/release_gate.py --manifest ./release-manifest.json --root ./dist
```

The command exits nonzero if a manifest is malformed, an artifact is missing, the SHA-256 digest differs, or a path is unsafe. It rejects symlink paths, hidden files, duplicate names, traversal, and unknown manifest fields. The tests use real temporary filesystem artifacts, tampering, and subprocesses; no fake network responses.

## Security limits and status

SHA-256 equality proves only that local bytes match a **trusted expected digest**. It does **not** authenticate who produced the digest, prove a reproducible build, prevent post-verification file replacement (TOCTOU), validate provenance/signatures, or establish deployment safety. The CLI does not deploy anything, use secrets, access RPC endpoints, implement PQC, or interact with a blockchain. The Rust binary is an informational stub, not a protocol engine.

**IMPLEMENTED (limited offline gate): yes on this PR branch. CI_VERIFIED: requires successful PR-head workflows. SECURITY_APPROVED: no. DEPLOYMENT_READY: no. Production/FIPS certified: no.** Do not merge or promote readiness until all required checks and independent reviews are complete.
