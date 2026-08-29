from __future__ import annotations

import os
import tomllib
from pathlib import Path

from life_os.models import Profile


def load_profile(path: str | Path | None = None) -> Profile:
    profile_path = Path(path or os.getenv("LIFE_OS_PROFILE", "config/profile.example.toml"))
    if not profile_path.exists():
        return Profile()
    with profile_path.open("rb") as handle:
        return Profile.model_validate(tomllib.load(handle))
