"""Load SYNTHETIC fixture responses. Every fixture must carry a `_synthetic` label."""

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def load_fixture(fixtures_dir: Path, name: str) -> Any:
    path = fixtures_dir / f"{name}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no fixture: {name}")
    data = json.loads(path.read_text())
    if "_synthetic" not in data:
        raise HTTPException(status_code=500, detail=f"fixture {name} is not SYNTHETIC-labelled")
    return data
