"""PostToolUse hook: format and lint a Python file right after Claude edits it.

Remaining lint problems are sent back to Claude (exit code 2) so they get fixed straight away.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUFF = ROOT / ".venv" / "Scripts" / "ruff.exe"


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    tool_input = payload.get("tool_input") or {}
    path = Path(tool_input.get("file_path") or "")
    if path.suffix != ".py" or not path.is_file() or ROOT not in path.resolve().parents:
        return 0
    if ".venv" in path.parts or "migrations" in path.parts:
        return 0

    ruff = str(RUFF) if RUFF.exists() else "ruff"
    subprocess.run([ruff, "format", "--quiet", str(path)], cwd=ROOT, check=False)
    check = subprocess.run(
        [ruff, "check", "--fix", "--quiet", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        print(f"ruff found problems in {path.name}:\n{check.stdout}{check.stderr}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
