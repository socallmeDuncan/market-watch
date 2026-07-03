"""Objective history summaries."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def summarize_history(
    rows: list[dict[str, Any]],
    *,
    windows_minutes: list[int],
    latest_timestamp: str | datetime,
) -> dict[str, Any]:
    latest = _parse_timestamp(latest_timestamp)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    group_order: list[tuple[str, str]] = []

    for row in rows:
        sample = _parse_sample(row)
        if sample is None:
            continue

        key = (sample["asset_type"], sample["code"])
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append(sample)

    items: list[dict[str, Any]] = []
    for key in group_order:
        samples = sorted(groups[key], key=lambda sample: sample["timestamp"])
        for window_minutes in windows_minutes:
            cutoff = latest - timedelta(minutes=window_minutes)
            window_samples = [
                sample
                for sample in samples
                if cutoff <= sample["timestamp"] <= latest
            ]
            if not window_samples:
                continue

            first = window_samples[0]
            last = window_samples[-1]
            prices = [sample["price"] for sample in window_samples]
            price_change = last["price"] - first["price"]
            price_change_pct = (
                (price_change / first["price"]) * 100
                if first["price"] not in (None, 0)
                else None
            )

            items.append(
                {
                    "code": last["code"],
                    "name": last["name"],
                    "asset_type": last["asset_type"],
                    "window_minutes": window_minutes,
                    "sample_count": len(window_samples),
                    "first_timestamp": first["timestamp"].strftime(TIMESTAMP_FORMAT),
                    "last_timestamp": last["timestamp"].strftime(TIMESTAMP_FORMAT),
                    "first_price": _format_number(first["price"]),
                    "last_price": _format_number(last["price"]),
                    "price_change": _format_number(price_change),
                    "price_change_pct": _format_number(price_change_pct),
                    "window_high": _format_number(max(prices)),
                    "window_low": _format_number(min(prices)),
                    "latest_amount": _format_number(last["amount"]),
                }
            )

    return {"windows_minutes": windows_minutes, "items": items}


def _parse_sample(row: dict[str, Any]) -> dict[str, Any] | None:
    timestamp = _try_parse_timestamp(row.get("timestamp"))
    price = _parse_number(row.get("price"))
    if timestamp is None or price is None:
        return None

    return {
        "timestamp": timestamp,
        "asset_type": str(row.get("asset_type", "")),
        "code": str(row.get("code", "")),
        "name": str(row.get("name", "")),
        "price": price,
        "amount": _parse_number(row.get("amount")),
    }


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.strptime(value, TIMESTAMP_FORMAT)


def _try_parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        value = value.replace(",", "")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _format_number(value: float | None) -> int | float | None:
    if value is None:
        return None

    rounded = round(value, 4)
    if rounded == 0:
        return 0
    if rounded.is_integer():
        return int(rounded)
    return rounded
