from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / "private" / "profile.toml"
source = ROOT / "config" / "profile.example.toml"

destination.parent.mkdir(parents=True, exist_ok=True)
if destination.exists():
    raise SystemExit(f"Refusing to overwrite {destination}")
shutil.copyfile(source, destination)
print(f"Created private profile at {destination}")
