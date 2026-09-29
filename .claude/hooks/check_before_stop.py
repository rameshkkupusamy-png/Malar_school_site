"""Stop hook: before Claude finishes, run `ruff check .` and `pytest` if code has changed.

Follows the CLAUDE.md rule "Run pytest and ruff check before calling a change done".
Skips the run when nothing has changed since the last passing run, so plain
conversation turns stay fast. On failure it blocks the stop and hands Claude the output.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STAMP = Path(__file__).with_name(".last-pass")
CODE_SUFFIXES = {".py", ".html", ".css", ".txt", ".toml"}
GIT_FALLBACK = r"C:\Program Files\Git\cmd\git.exe"


def changed_code_fingerprint() -> str | None:
    """A hash of every uncommitted code file's path and contents, or None if there are none."""
    git = shutil.which("git") or GIT_FALLBACK
    status = subprocess.run(
        [git, "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    paths = sorted(
        line[3:].split(" -> ")[-1].strip('"')
        for line in status.stdout.splitlines()
        if Path(line[3:]).suffix in CODE_SUFFIXES
    )
    if not paths:
        return None
    digest = hashlib.sha256()
    for rel in paths:
        digest.update(rel.encode())
        file = ROOT / rel
        if file.is_file():
            digest.update(file.read_bytes())
    return digest.hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, errors="replace", check=False
    )


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    if payload.get("stop_hook_active"):
        return 0  # Already blocked once this turn; let Claude stop rather than loop.

    fingerprint = changed_code_fingerprint()
    if fingerprint is None:
        return 0
    if STAMP.exists() and STAMP.read_text() == fingerprint:
        return 0

    python = str(PYTHON) if PYTHON.exists() else sys.executable
    lint = run([python, "-m", "ruff", "check", "."])
    tests = run([python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"])

    if lint.returncode == 0 and tests.returncode == 0:
        STAMP.write_text(fingerprint)
        return 0

    report = []
    if lint.returncode != 0:
        report.append("ruff check . failed:\n" + lint.stdout[-3000:])
    if tests.returncode != 0:
        report.append("pytest failed:\n" + (tests.stdout + tests.stderr)[-4000:])
    reason = "Checks failed. Fix these before finishing:\n\n" + "\n\n".join(report)
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
