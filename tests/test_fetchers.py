from __future__ import annotations

import pandas as pd
import pytest

from market_watch.fetchers import (
    SourceDataError,
    _filter_by_codes,
    fetch_index_intraday,
    fetch_indices,
    fetch_stock_intraday,
    fetch_stocks,
)


class StockProvider:
    def stock_zh_a_spot_em(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"代码": "300857", "名称": "协创数据"},
                {"代码": "300475", "名称": "香农芯创"},
                {"代码": "000001", "名称": "平安银行"},
            ]
        )


class IndexProvider:
    def __init__(self) -> None:
        self.symbols: list[str] = []

    def stock_zh_index_spot_em(self, *, symbol: str) -> pd.DataFrame:
        self.symbols.append(symbol)
        return pd.DataFrame(
            [
                {"代码": "000001", "名称": "上证指数"},
                {"代码": "399006", "名称": "创业板指"},
                {"代码": "399001", "名称": "深证成指"},
            ]
        )


def test_fetch_stocks_filters_requested_codes_in_order() -> None:
    result = fetch_stocks(["300475", "000001"], provider=StockProvider())

    assert result["代码"].tolist() == ["300475", "000001"]
    assert result["名称"].tolist() == ["香农芯创", "平安银行"]


def test_fetch_indices_passes_symbol_and_filters_requested_codes() -> None:
    provider = IndexProvider()

    result = fetch_indices(["399006"], symbol="沪深重要指数", provider=provider)

    assert provider.symbols == ["沪深重要指数"]
    assert result["代码"].tolist() == ["399006"]
    assert result["名称"].tolist() == ["创业板指"]


def test_filter_by_codes_raises_when_code_column_is_missing() -> None:
    frame = pd.DataFrame([{"名称": "协创数据"}])

    with pytest.raises(
        SourceDataError, match="Source frame is missing required column: 代码"
    ):
        _filter_by_codes(frame, ["300857"])


def test_filter_by_codes_matches_numeric_source_codes_by_requested_width() -> None:
    frame = pd.DataFrame(
        [
            {"代码": 1, "名称": "平安银行"},
            {"代码": 300857, "名称": "协创数据"},
        ]
    )

    result = _filter_by_codes(frame, ["000001"])

    assert len(result) == 1
    assert result.iloc[0]["代码"] == 1
    assert result.iloc[0]["名称"] == "平安银行"


class IntradayProvider:
    def __init__(self) -> None:
        self.stock_calls: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def stock_zh_a_hist_min_em(
        self,
        *,
        symbol: str,
        period: str,
        adjust: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.stock_calls.append(
            {
                "symbol": symbol,
                "period": period,
                "adjust": adjust,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return pd.DataFrame([{"时间": "2026-07-03 09:31:00", "收盘": 295.2}])

    def index_zh_a_hist_min_em(
        self,
        *,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.index_calls.append(
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return pd.DataFrame([{"时间": "2026-07-03 09:31:00", "收盘": 2310.2}])


def test_fetch_stock_intraday_calls_akshare_with_one_minute_parameters() -> None:
    provider = IntradayProvider()

    result = fetch_stock_intraday(
        "300857",
        start="2026-07-03 09:30:00",
        end="2026-07-03 15:00:00",
        provider=provider,
    )

    assert provider.stock_calls == [
        {
            "symbol": "300857",
            "period": "1",
            "adjust": "",
            "start_date": "2026-07-03 09:30:00",
            "end_date": "2026-07-03 15:00:00",
        }
    ]
    assert result.iloc[0]["收盘"] == 295.2


def test_fetch_index_intraday_calls_akshare_with_one_minute_parameters() -> None:
    provider = IntradayProvider()

    result = fetch_index_intraday(
        "399006",
        start="2026-07-03 09:30:00",
        end="2026-07-03 15:00:00",
        provider=provider,
    )

    assert provider.index_calls == [
        {
            "symbol": "399006",
            "period": "1",
            "start_date": "2026-07-03 09:30:00",
            "end_date": "2026-07-03 15:00:00",
        }
    ]
    assert result.iloc[0]["收盘"] == 2310.2


def test_fetch_stock_intraday_accepts_positional_start_and_end() -> None:
    provider = IntradayProvider()

    result = fetch_stock_intraday(
        "300857",
        "2026-07-03 09:30:00",
        "2026-07-03 15:00:00",
        provider=provider,
    )

    assert provider.stock_calls == [
        {
            "symbol": "300857",
            "period": "1",
            "adjust": "",
            "start_date": "2026-07-03 09:30:00",
            "end_date": "2026-07-03 15:00:00",
        }
    ]
    assert result.iloc[0]["收盘"] == 295.2


def test_fetch_index_intraday_accepts_positional_start_and_end() -> None:
    provider = IntradayProvider()

    result = fetch_index_intraday(
        "399006",
        "2026-07-03 09:30:00",
        "2026-07-03 15:00:00",
        provider=provider,
    )

    assert provider.index_calls == [
        {
            "symbol": "399006",
            "period": "1",
            "start_date": "2026-07-03 09:30:00",
            "end_date": "2026-07-03 15:00:00",
        }
    ]
    assert result.iloc[0]["收盘"] == 2310.2
