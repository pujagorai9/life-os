from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
tracked = subprocess.run(
    ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
).stdout.splitlines()

blocked = [
    path
    for path in tracked
    if path == ".env"
    or path.startswith("private/")
    or path.endswith((".db", ".sqlite", ".sqlite3"))
]

if blocked:
    raise SystemExit("Private or runtime files are tracked:\n" + "\n".join(blocked))
print("Public tree check passed: no private profile, .env, or database is tracked.")
