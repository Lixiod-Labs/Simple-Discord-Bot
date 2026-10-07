# Copyright (C) 2026 Lixiod Technologies

import asyncio
import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_locks: dict[str, asyncio.Lock] = {}


def _lock_for(name: str) -> asyncio.Lock:
    if name not in _locks:
        _locks[name] = asyncio.Lock()
    return _locks[name]


def _path_for(name: str) -> Path:
    safe_name = os.path.basename(name)
    return DATA_DIR / f"{safe_name}.json"


async def read_json(name: str, default: Any = None) -> Any:
    path = _path_for(name)
    async with _lock_for(name):
        return await asyncio.to_thread(_read_sync, path, default)


async def write_json(name: str, data: Any) -> None:
    path = _path_for(name)
    async with _lock_for(name):
        await asyncio.to_thread(_write_sync, path, data)


def _read_sync(path: Path, default: Any) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default if default is not None else {}


def _write_sync(path: Path, data: Any) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)
