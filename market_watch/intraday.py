"""Normalize intraday minute bars into the project schema."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from market_watch.fetchers import SourceDataError


INTRADAY_FIELDS = [
    "timestamp",
    "trade_date",
    "asset_type",
    "code",
    "name",
    "role",
    "period",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "average_price",
    "source",
]

REQUIRED_COLUMNS = ["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
SOURCE_NAME = "akshare_em_intraday_1m"
PERIOD = "1m"


def build_intraday_time_range(trade_date: str) -> tuple[str, str]:
    return f"{trade_date} 09:30:00", f"{trade_date} 15:00:00"


def normalize_intraday_frame(
    frame: pd.DataFrame,
    target: dict[str, object],
    *,
    asset_type: str,
    trade_date: str,
) -> list[dict[str, Any]]:
    for column in REQUIRED_COLUMNS:
        if column not in frame.columns:
            raise SourceDataError(f"Source frame is missing required column: {column}")

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        timestamp = _parse_timestamp(row.get("时间"))
        close = _parse_optional_number(row.get("收盘"))
        if timestamp is None or close is None:
            continue

        record = {
            "timestamp": timestamp,
            "trade_date": trade_date,
            "asset_type": asset_type,
            "code": str(target["code"]),
            "name": str(target["name"]),
            "role": str(target["role"]),
            "period": PERIOD,
            "open": _parse_optional_number(row.get("开盘")),
            "high": _parse_optional_number(row.get("最高")),
            "low": _parse_optional_number(row.get("最低")),
            "close": close,
            "volume": _parse_optional_number(row.get("成交量")),
            "amount": _parse_optional_number(row.get("成交额")),
            "average_price": _parse_optional_number(row.get("均价")),
            "source": SOURCE_NAME,
        }
        records.append({field: record.get(field) for field in INTRADAY_FIELDS})

    return records


def summarize_intraday(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["asset_type"]), str(row["code"]))
        groups.setdefault(key, []).append(row)

    items: list[dict[str, Any]] = []
    for group_rows in groups.values():
        chronological_rows = sorted(group_rows, key=lambda row: str(row["timestamp"]))
        first = chronological_rows[0]
        last = chronological_rows[-1]
        first_close = first["close"]
        last_close = last["close"]
        close_change = _round_optional(last_close - first_close)
        close_change_pct = None
        if first_close != 0:
            close_change_pct = _round_optional((close_change / first_close) * 100)

        items.append(
            {
                "asset_type": first["asset_type"],
                "code": first["code"],
                "name": first["name"],
                "role": first["role"],
                "period": first["period"],
                "first_timestamp": first["timestamp"],
                "last_timestamp": last["timestamp"],
                "first_close": first_close,
                "last_close": last_close,
                "day_high": _max_present(row["high"] for row in chronological_rows),
                "day_low": _min_present(row["low"] for row in chronological_rows),
                "close_change": close_change,
                "close_change_pct": close_change_pct,
                "total_volume": _sum_present(row["volume"] for row in chronological_rows),
                "total_amount": _sum_present(row["amount"] for row in chronological_rows),
                "row_count": len(chronological_rows),
            }
        )

    return {"items": items}


def _parse_timestamp(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        parsed = pd.to_datetime(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _parse_optional_number(value: Any) -> int | float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in {"", "-", "--"}:
            return None
        value = value.replace(",", "")

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(parsed):
        return None
    if parsed.is_integer():
        return int(parsed)
    return parsed


def _round_optional(value: int | float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(value, 4)
    if rounded == 0:
        rounded = 0
    if float(rounded).is_integer():
        return int(rounded)
    return rounded


def _max_present(values: Any) -> int | float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def _min_present(values: Any) -> int | float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


def _sum_present(values: Any) -> int | float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    total = sum(present)
    if float(total).is_integer():
        return int(total)
    return total
