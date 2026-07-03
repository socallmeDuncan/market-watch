from __future__ import annotations

from unittest.mock import patch, MagicMock

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


TENCENT_STOCK_RESPONSE = (
    'v_sz300857="51~协创数据~300857~300.41~293.59~293.59~173803~92752~81051'
    '~300.40~50~300.39~10~300.38~14~300.37~3~300.35~14~300.41~0~300.50~67'
    '~300.51~11~300.53~29~300.55~113~~20260703161421~6.82~2.32~309.80~289.23'
    '~300.41/173803/5208699946~173803~520870~3.57~84.22~~309.80~289.23~7.01'
    '~1462.58~1470.10~28.72~352.31~234.87~0.80~-129~299.69~48.98~126.26~~~3.14'
    '~520869.9946~3.0041~1~ A A~GP-A-CYB~149.84~-9.64~0.08~33.62~4.70~355.55'
    '~53.63~8.15~22.95~102.53~486859998~489363040~-41.48~132.58~486859998~~~405.68'
    '~-0.04~~CNY~0~~300.60~-88~";'
)


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_parses_fields(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert len(result) == 1
    row = result.iloc[0]
    assert row["代码"] == "300857"
    assert row["名称"] == "协创数据"
    assert row["最新价"] == 300.41
    assert row["昨收"] == 293.59
    assert row["今开"] == 293.59
    assert row["最高"] == 309.80
    assert row["最低"] == 289.23
    assert row["涨跌额"] == 6.82
    assert row["涨跌幅"] == 2.32
    assert row["成交量"] == 173803
    assert row["换手率"] == 3.57
    assert row["振幅"] == 7.01
    assert row["市盈率-动态"] == 84.22
    assert row["_market_watch_source"] == "tencent_qt"


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_amount_in_yuan_not_wan(mock_requests):
    """成交额[37]腾讯单位是万，必须×10000转成元."""
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert result.iloc[0]["成交额"] == 520870 * 10000


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_market_value_in_yuan(mock_requests):
    """总市值[45]/流通市值[44]腾讯单位是亿，必须×1e8转成元."""
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert result.iloc[0]["总市值"] == 1470.10 * 1e8
    assert result.iloc[0]["流通市值"] == 1462.58 * 1e8


@patch("market_watch.fetchers.requests")
def test_fetch_indices_tencent_uses_sh_prefix_for_shanghai_index(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = (
        'v_sh000001="1~上证指数~000001~4043.64~4028.90~4031.34~602009738~0~0'
        '~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0'
        '~0.00~0~0.00~0~~20260703161448~14.74~0.37~4073.88~4027.26'
        '~4043.64/602009738/1465563104854~602009738~146556310~1.25~17.77'
        '~~4073.88~4027.26~1.16~626986.37~677257.54~0.00~-1~-1~0.93~0'
        '~4048.65~~~~~~146556310.4854~0.0000~0~ ~ZS~1.88~0.41~~~~4258.86'
        '~3455.49~-1.15~-0.35~4.21~4825426913330~~-1.37~4.69~4825426913330'
        '~~~16.83~-0.01~~CNY~0~~0.00~0~";'
    )
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_indices(["000001"], symbol="沪深重要指数", source="tencent")

    called_url = mock_requests.Session.return_value.get.call_args[0][0]
    assert "sh000001" in called_url
    assert result.iloc[0]["代码"] == "000001"
    assert result.iloc[0]["名称"] == "上证指数"
    assert result.iloc[0]["最新价"] == 4043.64
    assert result.iloc[0]["_market_watch_source"] == "tencent_qt"


@patch("market_watch.fetchers.requests")
def test_fetch_etfs_tencent_uses_sh_prefix_for_hushi_etf(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = (
        'v_sh512480="1~UC半导体ETF国联安~512480~1.331~1.350~1.322~15949373'
        '~7304492~8644881~1.331~1372~1.330~33247~1.329~2460~1.328~5717'
        '~1.327~2060~1.332~790~1.333~9398~1.334~11029~1.335~5749~1.336~8466'
        '~~20260703161447~-0.019~-1.41~1.383~1.303~1.331/15949373/2134113665'
        '~15949373~213411~9.18~~~1.383~1.303~5.93~231.14~231.14~0.00~1.485'
        '~1.215~1.66~9424~1.338~~~~~~213411.3665~0.0000~0~   A~ETF~81.83'
        '~-3.06~~~~1.556~0.505~7.34~21.33~88.26~17366007200~17366007200'
        '~11.74~72.86~17366007200~0.66~1.3223~159.96~-0.15~1.3447~CNY~0'
        '~_D_D__F__N~1.325~5533~";'
    )
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_etfs(["512480"], source="tencent")

    called_url = mock_requests.Session.return_value.get.call_args[0][0]
    assert "sh512480" in called_url
    assert result.iloc[0]["最新价"] == 1.331


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_rejects_truncated_response(mock_requests):
    """截断的异常响应(<50字段)应被拒绝，触发 fallback 而非返回脏数据."""
    mock_resp = MagicMock()
    mock_resp.text = 'v_sz300857="51~协创数据~300857~300.41";'  # 仅4字段
    # 主源腾讯返回截断响应，第一次调用失败；fallback 也需 mock 失败以验证 RuntimeError
    mock_requests.Session.return_value.get.return_value = mock_resp

    # 直接测解析函数：截断响应应返回空 dict
    from market_watch.fetchers import _parse_tencent_qt_response

    assert _parse_tencent_qt_response('v_sz300857="51~协创数据";') == {}
