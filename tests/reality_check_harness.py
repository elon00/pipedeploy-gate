"""Legacy entry point: run actual offline artifact verification regression tests."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(subprocess.call([
        sys.executable, "-m", "unittest", "discover",
        "-s", str(root / "tests"), "-p", "test_*.py", "-v"
    ]))
