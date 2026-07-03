from __future__ import annotations

import pandas as pd
import pytest

from market_watch.fetchers import SourceDataError
from market_watch.intraday import (
    INTRADAY_FIELDS,
    build_intraday_time_range,
    normalize_intraday_frame,
    summarize_intraday,
)


def target(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "code": "300857",
        "name": "协创数据",
        "role": "primary",
    }
    item.update(overrides)
    return item


def minute_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "时间": "2026-07-03 09:31:00",
                "开盘": "294.5",
                "收盘": "295.2",
                "最高": "296.0",
                "最低": "294.0",
                "成交量": "1,234",
                "成交额": "5678900",
                "均价": "295.1",
            },
            {
                "时间": "2026-07-03 09:32:00",
                "开盘": 295.2,
                "收盘": 296.0,
                "最高": 296.5,
                "最低": 295.0,
                "成交量": 2345,
                "成交额": 6789000,
                "均价": 295.8,
            },
        ]
    )


def test_build_intraday_time_range_uses_regular_a_share_session() -> None:
    assert build_intraday_time_range("2026-07-03") == (
        "2026-07-03 09:30:00",
        "2026-07-03 15:00:00",
    )


def test_normalize_intraday_frame_maps_minute_rows_to_schema() -> None:
    rows = normalize_intraday_frame(
        minute_frame(),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    assert list(rows[0].keys()) == INTRADAY_FIELDS
    assert rows[0] == {
        "timestamp": "2026-07-03 09:31:00",
        "trade_date": "2026-07-03",
        "asset_type": "stock",
        "code": "300857",
        "name": "协创数据",
        "role": "primary",
        "period": "1m",
        "open": 294.5,
        "high": 296,
        "low": 294,
        "close": 295.2,
        "volume": 1234,
        "amount": 5678900,
        "average_price": 295.1,
        "source": "akshare_em_intraday_1m",
    }
    assert rows[1]["close"] == 296
    assert rows[1]["volume"] == 2345


def test_normalize_intraday_frame_preserves_fetcher_source_marker() -> None:
    frame = minute_frame()
    frame["_market_watch_source"] = "akshare_sina_minute_1m"

    rows = normalize_intraday_frame(
        frame,
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    assert rows[0]["source"] == "akshare_sina_minute_1m"


def test_normalize_intraday_frame_raises_when_required_column_missing() -> None:
    frame = minute_frame().drop(columns=["成交额"])

    with pytest.raises(SourceDataError, match="Source frame is missing required column: 成交额"):
        normalize_intraday_frame(
            frame,
            target(),
            asset_type="stock",
            trade_date="2026-07-03",
        )


def test_normalize_intraday_frame_keeps_missing_average_price_as_none() -> None:
    frame = minute_frame().drop(columns=["均价"])

    rows = normalize_intraday_frame(
        frame,
        target(),
        asset_type="index",
        trade_date="2026-07-03",
    )

    assert rows[0]["asset_type"] == "index"
    assert rows[0]["average_price"] is None


def test_normalize_intraday_frame_skips_rows_with_invalid_timestamp_or_close() -> None:
    frame = pd.DataFrame(
        [
            {
                "时间": "not a timestamp",
                "开盘": 294.5,
                "收盘": 295.2,
                "最高": 296,
                "最低": 294,
                "成交量": 1234,
                "成交额": 5678900,
            },
            {
                "时间": None,
                "开盘": 294.5,
                "收盘": 295.2,
                "最高": 296,
                "最低": 294,
                "成交量": 1234,
                "成交额": 5678900,
            },
            {
                "时间": "2026-07-03 09:31:00",
                "开盘": 294.5,
                "收盘": "--",
                "最高": 296,
                "最低": 294,
                "成交量": 1234,
                "成交额": 5678900,
            },
            {
                "时间": "2026-07-03 09:32:00",
                "开盘": 295.2,
                "收盘": None,
                "最高": 296.5,
                "最低": 295,
                "成交量": 2345,
                "成交额": 6789000,
            },
            {
                "时间": "2026-07-03 09:33:00",
                "开盘": 296,
                "收盘": 296.8,
                "最高": 297,
                "最低": 295.8,
                "成交量": 3456,
                "成交额": 7890000,
            },
        ]
    )

    rows = normalize_intraday_frame(
        frame,
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-07-03 09:33:00"
    assert rows[0]["close"] == 296.8


def test_summarize_intraday_computes_objective_facts_only() -> None:
    rows = normalize_intraday_frame(
        minute_frame(),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    summary = summarize_intraday(rows)

    assert summary == {
        "items": [
            {
                "asset_type": "stock",
                "code": "300857",
                "name": "协创数据",
                "role": "primary",
                "period": "1m",
                "first_timestamp": "2026-07-03 09:31:00",
                "last_timestamp": "2026-07-03 09:32:00",
                "first_close": 295.2,
                "last_close": 296,
                "day_high": 296.5,
                "day_low": 294,
                "close_change": 0.8,
                "close_change_pct": 0.271,
                "total_volume": 3579,
                "total_amount": 12467900,
                "row_count": 2,
            }
        ]
    }


def test_summarize_intraday_uses_chronological_first_and_last_rows() -> None:
    rows = normalize_intraday_frame(
        minute_frame(),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    summary = summarize_intraday(list(reversed(rows)))

    item = summary["items"][0]
    assert item["first_timestamp"] == "2026-07-03 09:31:00"
    assert item["last_timestamp"] == "2026-07-03 09:32:00"
    assert item["first_close"] == 295.2
    assert item["last_close"] == 296
    assert item["close_change"] == 0.8


def test_summarize_intraday_handles_zero_first_close_without_dividing_by_zero() -> None:
    rows = normalize_intraday_frame(
        pd.DataFrame(
            [
                {
                    "时间": "2026-07-03 09:31:00",
                    "开盘": 0,
                    "收盘": 0,
                    "最高": 0,
                    "最低": 0,
                    "成交量": 10,
                    "成交额": 0,
                },
                {
                    "时间": "2026-07-03 09:32:00",
                    "开盘": 0,
                    "收盘": 1,
                    "最高": 1,
                    "最低": 0,
                    "成交量": 20,
                    "成交额": 20,
                },
            ]
        ),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    summary = summarize_intraday(rows)

    assert summary["items"][0]["close_change"] == 1
    assert summary["items"][0]["close_change_pct"] is None


def test_summarize_intraday_formats_percent_change_to_four_decimal_places() -> None:
    rows = normalize_intraday_frame(
        pd.DataFrame(
            [
                {
                    "时间": "2026-07-03 09:31:00",
                    "开盘": 3,
                    "收盘": 3,
                    "最高": 3,
                    "最低": 3,
                    "成交量": 10,
                    "成交额": 30,
                },
                {
                    "时间": "2026-07-03 09:32:00",
                    "开盘": 3,
                    "收盘": 4,
                    "最高": 4,
                    "最低": 3,
                    "成交量": 20,
                    "成交额": 80,
                },
            ]
        ),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    summary = summarize_intraday(rows)

    assert summary["items"][0]["close_change_pct"] == 33.3333
