"""CSV storage and atomic output helpers."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from market_watch.intraday import INTRADAY_FIELDS
from market_watch.normalize import SNAPSHOT_FIELDS


def snapshot_path(snapshot_dir: str | Path, trade_date: str) -> Path:
    return Path(snapshot_dir) / f"{trade_date}.csv"


def append_snapshots(
    snapshot_dir: str | Path,
    trade_date: str,
    records: Iterable[dict[str, Any]],
) -> Path:
    path = snapshot_path(snapshot_dir, trade_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SNAPSHOT_FIELDS, extrasaction="ignore")
        if should_write_header:
            writer.writeheader()
        writer.writerows(records)

    return path


def read_snapshots_for_trade_date(
    snapshot_dir: str | Path,
    trade_date: str,
) -> list[dict[str, str]]:
    path = snapshot_path(snapshot_dir, trade_date)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def intraday_path(
    intraday_dir: str | Path,
    trade_date: str,
    period: str = "1m",
) -> Path:
    return Path(intraday_dir) / f"{trade_date}-{period}.csv"


def write_intraday_rows(
    intraday_dir: str | Path,
    trade_date: str,
    records: Iterable[dict[str, Any]],
    period: str = "1m",
) -> Path:
    destination = intraday_path(intraday_dir, trade_date, period)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".tmp",
            newline="",
            encoding="utf-8",
        ) as temp_file:
            temp_name = temp_file.name
            writer = csv.DictWriter(
                temp_file,
                fieldnames=INTRADAY_FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(records)
        os.replace(temp_name, destination)
    except Exception:
        if temp_name is not None:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()
        raise

    return destination


def read_intraday_rows(
    intraday_dir: str | Path,
    trade_date: str,
    period: str = "1m",
) -> list[dict[str, str]]:
    path = intraday_path(intraday_dir, trade_date, period)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def atomic_write_text(path: str | Path, content: str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".tmp",
            encoding="utf-8",
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(content)
        os.replace(temp_name, destination)
    except Exception:
        if temp_name is not None:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()
        raise

    return destination


def atomic_write_json(path: str | Path, payload: Any) -> Path:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return atomic_write_text(path, content)
