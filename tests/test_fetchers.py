from __future__ import annotations

import pandas as pd
import pytest

from market_watch.fetchers import (
    SourceDataError,
    _filter_by_codes,
    _tencent_prefix,
    fetch_index_intraday,
    fetch_indices,
    fetch_etf_intraday,
    fetch_etfs,
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


class FallbackStockProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def stock_zh_a_spot_em(self) -> pd.DataFrame:
        self.calls.append("eastmoney")
        raise RuntimeError("eastmoney offline")

    def stock_zh_a_spot(self) -> pd.DataFrame:
        self.calls.append("sina")
        return pd.DataFrame(
            [
                {"代码": "sz300857", "名称": "协创数据", "最新价": 300.41},
                {"代码": "sz300475", "名称": "香农芯创", "最新价": 264.25},
                {"代码": "sz300442", "名称": "润泽科技", "最新价": 85.44},
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


class FallbackIndexProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.symbols: list[str] = []

    def stock_zh_index_spot_em(self, *, symbol: str) -> pd.DataFrame:
        self.calls.append("eastmoney")
        self.symbols.append(symbol)
        raise RuntimeError("eastmoney offline")

    def stock_zh_index_spot_sina(self) -> pd.DataFrame:
        self.calls.append("sina")
        return pd.DataFrame(
            [
                {"代码": "sh000001", "名称": "上证指数", "最新价": 4043.64},
                {"代码": "sz399006", "名称": "创业板指", "最新价": 4019.93},
            ]
        )


class EtfProvider:
    def __init__(self) -> None:
        self.spot_calls = 0
        self.intraday_calls: list[dict[str, object]] = []

    def fund_etf_spot_em(self) -> pd.DataFrame:
        self.spot_calls += 1
        return pd.DataFrame(
            [
                {"代码": "159915", "名称": "创业板ETF易方达", "最新价": 4.037},
                {"代码": "588000", "名称": "科创50ETF华夏", "最新价": 2.102},
                {"代码": "512480", "名称": "UC半导体ETF国联安", "最新价": 1.331},
            ]
        )

    def fund_etf_hist_min_em(
        self,
        *,
        symbol: str,
        period: str,
        adjust: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.intraday_calls.append(
            {
                "symbol": symbol,
                "period": period,
                "adjust": adjust,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return pd.DataFrame([{"时间": "2026-07-03 09:31:00", "收盘": 4.037}])


def test_fetch_stocks_filters_requested_codes_in_order() -> None:
    result = fetch_stocks(["300475", "000001"], provider=StockProvider())

    assert result["代码"].tolist() == ["300475", "000001"]
    assert result["名称"].tolist() == ["香农芯创", "平安银行"]
    assert result["_market_watch_source"].tolist() == ["akshare_em", "akshare_em"]


def test_fetch_stocks_falls_back_to_sina_when_eastmoney_fails() -> None:
    provider = FallbackStockProvider()

    result = fetch_stocks(["300475", "300442"], provider=provider)

    assert provider.calls == ["eastmoney", "sina"]
    assert result["代码"].tolist() == ["sz300475", "sz300442"]
    assert result["名称"].tolist() == ["香农芯创", "润泽科技"]
    assert result["_market_watch_source"].tolist() == [
        "akshare_sina_spot",
        "akshare_sina_spot",
    ]


def test_fetch_indices_passes_symbol_and_filters_requested_codes() -> None:
    provider = IndexProvider()

    result = fetch_indices(["399006"], symbol="沪深重要指数", provider=provider)

    assert provider.symbols == ["沪深重要指数"]
    assert result["代码"].tolist() == ["399006"]
    assert result["名称"].tolist() == ["创业板指"]
    assert result["_market_watch_source"].tolist() == ["akshare_em"]


def test_fetch_indices_falls_back_to_sina_when_eastmoney_fails() -> None:
    provider = FallbackIndexProvider()

    result = fetch_indices(["000001", "399006"], symbol="沪深重要指数", provider=provider)

    assert provider.calls == ["eastmoney", "sina"]
    assert provider.symbols == ["沪深重要指数"]
    assert result["代码"].tolist() == ["sh000001", "sz399006"]
    assert result["名称"].tolist() == ["上证指数", "创业板指"]
    assert result["_market_watch_source"].tolist() == [
        "akshare_sina_index_spot",
        "akshare_sina_index_spot",
    ]


def test_fetch_etfs_filters_requested_codes_and_marks_source() -> None:
    provider = EtfProvider()

    result = fetch_etfs(["588000", "159915"], provider=provider)

    assert provider.spot_calls == 1
    assert result["代码"].tolist() == ["588000", "159915"]
    assert result["名称"].tolist() == ["科创50ETF华夏", "创业板ETF易方达"]
    assert result["_market_watch_source"].tolist() == [
        "akshare_em_etf_spot",
        "akshare_em_etf_spot",
    ]


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


def test_filter_by_codes_matches_sina_prefixed_source_codes() -> None:
    frame = pd.DataFrame(
        [
            {"代码": "sz300857", "名称": "协创数据"},
            {"代码": "sh000001", "名称": "上证指数"},
        ]
    )

    result = _filter_by_codes(frame, ["000001", "300857"])

    assert result["代码"].tolist() == ["sh000001", "sz300857"]
    assert result["名称"].tolist() == ["上证指数", "协创数据"]


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


class FallbackIntradayProvider:
    def __init__(self) -> None:
        self.stock_calls: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []
        self.minute_calls: list[dict[str, object]] = []

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
        raise RuntimeError("eastmoney stock minute offline")

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
        raise RuntimeError("eastmoney index minute offline")

    def stock_zh_a_minute(
        self,
        *,
        symbol: str,
        period: str,
        adjust: str,
    ) -> pd.DataFrame:
        self.minute_calls.append(
            {"symbol": symbol, "period": period, "adjust": adjust}
        )
        return pd.DataFrame(
            [
                {
                    "day": "2026-07-02 15:00:00",
                    "open": 293.0,
                    "high": 294.0,
                    "low": 292.0,
                    "close": 293.5,
                    "volume": 100,
                    "amount": 29350,
                },
                {
                    "day": "2026-07-03 09:31:00",
                    "open": 294.5,
                    "high": 296.0,
                    "low": 294.0,
                    "close": 295.2,
                    "volume": 1234,
                    "amount": 5678900,
                },
            ]
        )


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


def test_fetch_stock_intraday_falls_back_to_sina_minute_data() -> None:
    provider = FallbackIntradayProvider()

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
    assert provider.minute_calls == [
        {"symbol": "sz300857", "period": "1", "adjust": ""}
    ]
    assert result.to_dict(orient="records") == [
        {
            "时间": pd.Timestamp("2026-07-03 09:31:00"),
            "开盘": 294.5,
            "最高": 296.0,
            "最低": 294.0,
            "收盘": 295.2,
            "成交量": 1234,
            "成交额": 5678900,
            "_market_watch_source": "akshare_sina_minute_1m",
        }
    ]


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


def test_fetch_index_intraday_falls_back_to_sina_minute_data() -> None:
    provider = FallbackIntradayProvider()

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
    assert provider.minute_calls == [
        {"symbol": "sz399006", "period": "1", "adjust": ""}
    ]
    assert result["时间"].tolist() == [pd.Timestamp("2026-07-03 09:31:00")]
    assert result.iloc[0]["收盘"] == 295.2
    assert result.iloc[0]["_market_watch_source"] == "akshare_sina_minute_1m"


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


def test_fetch_etf_intraday_calls_akshare_with_one_minute_parameters() -> None:
    provider = EtfProvider()

    result = fetch_etf_intraday(
        "159915",
        "2026-07-03 09:30:00",
        "2026-07-03 15:00:00",
        provider=provider,
    )

    assert provider.intraday_calls == [
        {
            "symbol": "159915",
            "period": "1",
            "adjust": "",
            "start_date": "2026-07-03 09:30:00",
            "end_date": "2026-07-03 15:00:00",
        }
    ]
    assert result.iloc[0]["收盘"] == 4.037
    assert result.iloc[0]["_market_watch_source"] == "akshare_em_etf_intraday_1m"


def test_tencent_prefix_stock_chuangye() -> None:
    assert _tencent_prefix("300857", "stock") == "sz"


def test_tencent_prefix_stock_hushi() -> None:
    assert _tencent_prefix("600000", "stock") == "sh"


def test_tencent_prefix_index_shanghai_series() -> None:
    assert _tencent_prefix("000001", "index") == "sh"
    assert _tencent_prefix("000300", "index") == "sh"
    assert _tencent_prefix("000688", "index") == "sh"


def test_tencent_prefix_index_shenzhen_series() -> None:
    assert _tencent_prefix("399006", "index") == "sz"
    assert _tencent_prefix("399001", "index") == "sz"


def test_tencent_prefix_etf_hushi() -> None:
    assert _tencent_prefix("512480", "etf") == "sh"
    assert _tencent_prefix("588000", "etf") == "sh"


def test_tencent_prefix_etf_shenshi() -> None:
    assert _tencent_prefix("159915", "etf") == "sz"
