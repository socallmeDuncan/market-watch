from __future__ import annotations

import math

import pandas as pd

from market_watch.normalize import (
    SNAPSHOT_FIELDS,
    make_error,
    normalize_index_frame,
    normalize_stock_frame,
)


def test_snapshot_fields_are_exact() -> None:
    assert SNAPSHOT_FIELDS == [
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
        "turnover_rate",
        "speed",
        "five_min_change",
        "source",
    ]


def test_normalize_stock_frame_maps_akshare_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "300857",
                "名称": "协创数据",
                "最新价": 295.2,
                "涨跌幅": 0.55,
                "涨跌额": 1.61,
                "成交量": "1,234,567",
                "成交额": 1850000000,
                "振幅": 2.32,
                "最高": 298.8,
                "最低": 292.0,
                "今开": 298.0,
                "昨收": 293.59,
                "换手率": 8.1,
                "涨速": 0.22,
                "5分钟涨跌": 0.8,
            }
        ]
    )
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert list(records[0].keys()) == SNAPSHOT_FIELDS
    assert records[0] == {
        "timestamp": "2026-07-03 10:42:30",
        "trade_date": "2026-07-03",
        "asset_type": "stock",
        "code": "300857",
        "name": "协创数据",
        "role": "primary",
        "price": 295.2,
        "change_pct": 0.55,
        "change_amount": 1.61,
        "open": 298,
        "high": 298.8,
        "low": 292,
        "prev_close": 293.59,
        "volume": 1234567,
        "amount": 1850000000,
        "amplitude": 2.32,
        "turnover_rate": 8.1,
        "speed": 0.22,
        "five_min_change": 0.8,
        "source": "akshare_em",
    }


def test_normalize_index_frame_maps_common_fields_and_stock_only_fields_are_none() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "399006",
                "名称": "创业板指",
                "最新价": 2310.2,
                "涨跌幅": 0.4,
                "涨跌额": 9.2,
                "成交量": 123456789,
                "成交额": 220000000000,
                "振幅": 1.52,
                "最高": 2320.0,
                "最低": 2285.0,
                "今开": 2298.0,
                "昨收": 2301.0,
            }
        ]
    )
    targets = [{"code": "399006", "name": "创业板指", "role": "context"}]

    records, errors = normalize_index_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert list(records[0].keys()) == SNAPSHOT_FIELDS
    assert records[0]["asset_type"] == "index"
    assert records[0]["code"] == "399006"
    assert records[0]["price"] == 2310.2
    assert records[0]["volume"] == 123456789
    assert records[0]["turnover_rate"] is None
    assert records[0]["speed"] is None
    assert records[0]["five_min_change"] is None
    assert records[0]["source"] == "akshare_em"


def test_normalize_reports_missing_target() -> None:
    frame = pd.DataFrame([{"代码": "300475", "名称": "香农芯创", "最新价": 252.3}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors == [
        {
            "level": "warning",
            "stage": "normalize_stock",
            "code": "TARGET_MISSING",
            "message": "Configured target not found in source data: stock 300857",
            "target": {"asset_type": "stock", "code": "300857"},
            "timestamp": "2026-07-03 10:42:30",
        }
    ]


def test_invalid_required_numeric_field_skips_record() -> None:
    frame = pd.DataFrame([{"代码": "300857", "名称": "协创数据", "最新价": "-"}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors == [
        {
            "level": "error",
            "stage": "normalize_stock",
            "code": "INVALID_REQUIRED_FIELD",
            "message": "Invalid required numeric field 最新价 for stock 300857",
            "target": {"asset_type": "stock", "code": "300857"},
            "timestamp": "2026-07-03 10:42:30",
        }
    ]


def test_non_finite_required_numeric_field_skips_record() -> None:
    frame = pd.DataFrame([{"代码": "300857", "名称": "协创数据", "最新价": "nan"}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors[0]["code"] == "INVALID_REQUIRED_FIELD"


def test_non_finite_optional_numeric_field_becomes_none() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "300857",
                "名称": "协创数据",
                "最新价": 295.2,
                "换手率": "inf",
            }
        ]
    )
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert records[0]["turnover_rate"] is None


def test_numeric_source_code_matches_zero_padded_configured_index_code() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": 1,
                "名称": "上证指数",
                "最新价": 3205.8,
            }
        ]
    )
    targets = [{"code": "000001", "name": "上证指数", "role": "context"}]

    records, errors = normalize_index_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert records[0]["code"] == "000001"
    assert records[0]["name"] == "上证指数"


def test_source_frame_missing_code_returns_source_field_missing_error() -> None:
    frame = pd.DataFrame([{"名称": "协创数据", "最新价": 295.2}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors == [
        {
            "level": "error",
            "stage": "normalize_stock",
            "code": "SOURCE_FIELD_MISSING",
            "message": "Source frame is missing column: 代码",
            "target": None,
            "timestamp": "2026-07-03 10:42:30",
        }
    ]


def test_numeric_parser_handles_missing_and_nan_values_as_none() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "300857",
                "名称": "协创数据",
                "最新价": "295.20",
                "涨跌幅": "",
                "涨跌额": None,
                "成交量": "--",
                "成交额": math.nan,
                "振幅": "-",
                "最高": "298",
                "最低": "292.5",
                "今开": "2,980",
                "昨收": "293.59",
                "换手率": "8",
                "涨速": "",
                "5分钟涨跌": None,
            }
        ]
    )
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert records[0]["price"] == 295.2
    assert records[0]["change_pct"] is None
    assert records[0]["change_amount"] is None
    assert records[0]["volume"] is None
    assert records[0]["amount"] is None
    assert records[0]["amplitude"] is None
    assert records[0]["high"] == 298
    assert records[0]["low"] == 292.5
    assert records[0]["open"] == 2980
    assert records[0]["turnover_rate"] == 8
    assert records[0]["speed"] is None
    assert records[0]["five_min_change"] is None


def test_make_error_shape() -> None:
    error = make_error(
        level="warning",
        stage="fetch_indices",
        code="SOURCE_TIMEOUT",
        message="timed out",
        target=None,
        timestamp="2026-07-03 10:42:30",
    )

    assert list(error.keys()) == [
        "level",
        "stage",
        "code",
        "message",
        "target",
        "timestamp",
    ]
    assert error == {
        "level": "warning",
        "stage": "fetch_indices",
        "code": "SOURCE_TIMEOUT",
        "message": "timed out",
        "target": None,
        "timestamp": "2026-07-03 10:42:30",
    }
