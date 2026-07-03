"""Normalize AKShare rows into the project schema."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


SNAPSHOT_FIELDS = [
    "timestamp",
    "trade_date",
    "asset_type",
    "code",
    "name",
    "role",
    "price",
    "change_pct",
    "change_amount",
    "open",
    "high",
    "low",
    "prev_close",
    "volume",
    "amount",
    "amplitude",
    "volume_ratio",
    "turnover_rate",
    "pe_dynamic",
    "pb_ratio",
    "total_market_value",
    "circulating_market_value",
    "speed",
    "five_min_change",
    "sixty_day_change_pct",
    "year_to_date_change_pct",
    "source",
]

COMMON_FIELD_MAP = {
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change_amount": "涨跌额",
    "open": "今开",
    "high": "最高",
    "low": "最低",
    "prev_close": "昨收",
    "volume": "成交量",
    "amount": "成交额",
    "amplitude": "振幅",
}

ETF_FIELD_MAP = {
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change_amount": "涨跌额",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "prev_close": "昨收",
    "volume": "成交量",
    "amount": "成交额",
    "amplitude": "振幅",
}

STOCK_ONLY_FIELD_MAP = {
    "volume_ratio": "量比",
    "turnover_rate": "换手率",
    "pe_dynamic": "市盈率-动态",
    "pb_ratio": "市净率",
    "total_market_value": "总市值",
    "circulating_market_value": "流通市值",
    "speed": "涨速",
    "five_min_change": "5分钟涨跌",
    "sixty_day_change_pct": "60日涨跌幅",
    "year_to_date_change_pct": "年初至今涨跌幅",
}

ETF_OPTIONAL_FIELD_MAP = {
    "volume_ratio": "量比",
    "turnover_rate": "换手率",
    "total_market_value": "总市值",
    "circulating_market_value": "流通市值",
}

REQUIRED_NUMERIC_FIELDS = {"price"}
SOURCE_NAME = "akshare_em"


def make_error(
    *,
    level: str,
    stage: str,
    code: str,
    message: str,
    target: dict[str, Any] | None,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "level": level,
        "stage": stage,
        "code": code,
        "message": message,
        "target": target,
        "timestamp": timestamp,
    }


def normalize_stock_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _normalize_frame(
        frame,
        targets,
        asset_type="stock",
        timestamp=timestamp,
        trade_date=trade_date,
        stage="normalize_stock",
        optional_map=STOCK_ONLY_FIELD_MAP,
    )


def normalize_index_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _normalize_frame(
        frame,
        targets,
        asset_type="index",
        timestamp=timestamp,
        trade_date=trade_date,
        stage="normalize_index",
        optional_map={},
    )


def normalize_etf_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _normalize_frame(
        frame,
        targets,
        asset_type="etf",
        timestamp=timestamp,
        trade_date=trade_date,
        stage="normalize_etf",
        optional_map=ETF_OPTIONAL_FIELD_MAP,
        field_map=ETF_FIELD_MAP,
    )


def _normalize_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    asset_type: str,
    timestamp: str,
    trade_date: str,
    stage: str,
    optional_map: dict[str, str],
    field_map: dict[str, str] = COMMON_FIELD_MAP,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if "代码" not in frame.columns:
        return [], [
            make_error(
                level="error",
                stage=stage,
                code="SOURCE_FIELD_MISSING",
                message="Source frame is missing column: 代码",
                target=None,
                timestamp=timestamp,
            )
        ]

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    working = frame.copy()

    for target in targets:
        code = str(target["code"])
        target_ref = {"asset_type": asset_type, "code": code}
        comparable_codes = working["代码"].map(
            lambda value: _normalize_source_code(value, target_code=code)
        )
        matches = working[comparable_codes == code]
        if matches.empty:
            errors.append(
                make_error(
                    level="warning",
                    stage=stage,
                    code="TARGET_MISSING",
                    message=f"Configured target not found in source data: {asset_type} {code}",
                    target=target_ref,
                    timestamp=timestamp,
                )
            )
            continue

        row = matches.iloc[0].to_dict()
        record, row_errors = _build_record(
            row,
            target,
            asset_type=asset_type,
            timestamp=timestamp,
            trade_date=trade_date,
            stage=stage,
            field_map=field_map,
        )
        errors.extend(row_errors)
        if record is None:
            continue

        for field, source_field in optional_map.items():
            record[field] = _parse_optional_number(row.get(source_field))
        records.append({field: record.get(field) for field in SNAPSHOT_FIELDS})

    return records, errors


def _build_record(
    row: dict[str, Any],
    target: dict[str, Any],
    *,
    asset_type: str,
    timestamp: str,
    trade_date: str,
    stage: str,
    field_map: dict[str, str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    code = str(target["code"])
    record: dict[str, Any] = {
        "timestamp": timestamp,
        "trade_date": trade_date,
        "asset_type": asset_type,
        "code": code,
        "name": str(target["name"]),
        "role": str(target["role"]),
        "source": str(row.get("_market_watch_source") or SOURCE_NAME),
    }

    for field, source_field in field_map.items():
        value = _parse_optional_number(row.get(source_field))
        if field in REQUIRED_NUMERIC_FIELDS and value is None:
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="INVALID_REQUIRED_FIELD",
                    message=f"Invalid required numeric field {source_field} for {asset_type} {code}",
                    target={"asset_type": asset_type, "code": code},
                    timestamp=timestamp,
                )
            ]
        record[field] = value

    for field in STOCK_ONLY_FIELD_MAP:
        record[field] = None
    return record, []


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


def _normalize_source_code(value: Any, *, target_code: str) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, str):
        source_code = value.strip()
        if (
            len(source_code) > 2
            and source_code[:2].lower() in {"sh", "sz", "bj"}
            and source_code[2:].isdigit()
        ):
            source_code = source_code[2:]
    elif isinstance(value, float) and value.is_integer():
        source_code = str(int(value))
    else:
        source_code = str(value)
    return source_code.zfill(len(target_code))
