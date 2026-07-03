"""AKShare fetch wrappers."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
import requests


class SourceDataError(RuntimeError):
    """Raised when source data does not have the expected shape."""


def fetch_stocks(
    codes: Iterable[str],
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_stocks_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = _with_source(akshare_module.stock_zh_a_spot_em(), "akshare_em")
        return _filter_by_codes(frame, codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(akshare_module.stock_zh_a_spot(), "akshare_sina_spot")
            return _filter_by_codes(frame, codes)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney stock fetch failed: {primary_exc}; "
                f"Sina stock fetch failed: {fallback_exc}"
            ) from fallback_exc


def fetch_indices(
    codes: Iterable[str],
    symbol: str,
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_indices_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    requested_codes = [str(code) for code in codes]
    try:
        frame = _with_source(akshare_module.stock_zh_index_spot_em(symbol=symbol), "akshare_em")
        filtered = _filter_by_codes(frame, requested_codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(
                akshare_module.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
            )
            return _filter_by_codes(frame, requested_codes)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney index fetch failed: {primary_exc}; "
                f"Sina index fetch failed: {fallback_exc}"
            ) from fallback_exc

    missing_codes = _missing_codes(filtered, requested_codes)
    if not missing_codes:
        return filtered

    try:
        fallback_frame = _with_source(
            akshare_module.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
        )
        fallback_filtered = _filter_by_codes(fallback_frame, missing_codes)
    except Exception:
        return filtered

    return _filter_by_codes(
        pd.concat([filtered, fallback_filtered], ignore_index=True),
        requested_codes,
    )


def fetch_etfs(
    codes: Iterable[str],
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_etfs_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    frame = _with_source(akshare_module.fund_etf_spot_em(), "akshare_em_etf_spot")
    return _filter_by_codes(frame, codes)



def fetch_stock_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="stock")
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = akshare_module.stock_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            adjust="",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = akshare_module.stock_zh_a_minute(
                symbol=_stock_sina_symbol(code),
                period="1",
                adjust="",
            )
            return _convert_sina_minute_frame(frame, start=start, end=end)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney stock minute fetch failed: {primary_exc}; "
                f"Sina stock minute fetch failed: {fallback_exc}"
            ) from fallback_exc


def fetch_index_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="index")
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = akshare_module.index_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = akshare_module.stock_zh_a_minute(
                symbol=_index_sina_symbol(code),
                period="1",
                adjust="",
            )
            return _convert_sina_minute_frame(frame, start=start, end=end)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney index minute fetch failed: {primary_exc}; "
                f"Sina index minute fetch failed: {fallback_exc}"
            ) from fallback_exc


def fetch_etf_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="etf")
    akshare_module = provider if provider is not None else _import_akshare()
    frame = akshare_module.fund_etf_hist_min_em(
        symbol=str(code),
        period="1",
        adjust="",
        start_date=start,
        end_date=end,
    )
    return _with_source(frame, "akshare_em_etf_intraday_1m")


def _filter_by_codes(frame: pd.DataFrame, codes: Iterable[str]) -> pd.DataFrame:
    if "代码" not in frame.columns:
        raise SourceDataError("Source frame is missing required column: 代码")

    wanted_codes = [str(code) for code in codes]
    working = frame.copy()
    source_codes = working["代码"].map(_source_code_to_str)

    chunks: list[pd.DataFrame] = []
    for wanted_code in wanted_codes:
        comparable = source_codes.map(lambda source_code: source_code.zfill(len(wanted_code)))
        matches = working[comparable == wanted_code]
        if not matches.empty:
            chunks.append(matches)

    if not chunks:
        return working.iloc[0:0].copy()
    return pd.concat(chunks, ignore_index=True).copy()


def _missing_codes(frame: pd.DataFrame, requested_codes: list[str]) -> list[str]:
    if frame.empty or "代码" not in frame.columns:
        return requested_codes
    present = {_source_code_to_str(value) for value in frame["代码"]}
    return [code for code in requested_codes if code not in present]


def _with_source(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    working = frame.copy()
    working["_market_watch_source"] = source_name
    return working


def _convert_sina_minute_frame(
    frame: pd.DataFrame, *, start: str, end: str
) -> pd.DataFrame:
    required_columns = ["day", "open", "high", "low", "close", "volume", "amount"]
    for column in required_columns:
        if column not in frame.columns:
            raise SourceDataError(f"Sina minute frame is missing column: {column}")

    working = frame[required_columns].copy()
    working["day"] = pd.to_datetime(working["day"], errors="coerce")
    start_time = pd.to_datetime(start)
    end_time = pd.to_datetime(end)
    working = working[
        working["day"].notna()
        & (working["day"] >= start_time)
        & (working["day"] <= end_time)
    ].copy()
    working.rename(
        columns={
            "day": "时间",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
        },
        inplace=True,
    )
    working["_market_watch_source"] = "akshare_sina_minute_1m"
    return working


def _stock_sina_symbol(code: str) -> str:
    normalized = str(code).strip().lower()
    if normalized.startswith(("sh", "sz", "bj")):
        return normalized
    if normalized.startswith("6"):
        return f"sh{normalized}"
    if normalized.startswith(("4", "8")):
        return f"bj{normalized}"
    return f"sz{normalized}"


def _index_sina_symbol(code: str) -> str:
    normalized = str(code).strip().lower()
    if normalized.startswith(("sh", "sz")):
        return normalized
    if normalized.startswith(("399", "159")):
        return f"sz{normalized}"
    return f"sh{normalized}"


def _source_code_to_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, str):
        source_code = value.strip()
        if (
            len(source_code) > 2
            and source_code[:2].lower() in {"sh", "sz", "bj"}
            and source_code[2:].isdigit()
        ):
            return source_code[2:]
        return source_code
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _import_akshare() -> Any:
    import akshare

    return akshare


def _tencent_prefix(code: str, asset_type: str) -> str:
    """Return the Tencent exchange prefix ("sh" or "sz") for a given code.

    asset_type ∈ {"stock", "index", "etf"}. See spec section 7.1:
      index: 399开头->sz, 其余(000/000300/000688等)->sh
      stock/etf: 5/6/9开头->sh, 其余(0/1/3开头)->sz
    """
    normalized = str(code).strip()
    if asset_type == "index":
        if normalized.startswith("399"):
            return "sz"
        return "sh"
    # stock and etf share the same prefix rule
    if normalized.startswith(("5", "6", "9")):
        return "sh"
    return "sz"


TENCENT_QT_URL = "https://qt.gtimg.cn/q="
TENCENT_QT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://gu.qq.com/",
}

# 腾讯 qt 字段索引 → 中文列名。单位坑：成交额[37]是万，市值[44][45]是亿。
# 见 spec 第 2 节字段索引表。
_TENCENT_QT_FIELD_INDEX = {
    1: "名称",
    2: "代码",
    3: "最新价",
    4: "昨收",
    5: "今开",
    6: "成交量",
    31: "涨跌额",
    32: "涨跌幅",
    33: "最高",
    34: "最低",
    37: "成交额",
    38: "换手率",
    39: "市盈率-动态",
    43: "振幅",
    44: "流通市值",
    45: "总市值",
}


def _to_number(value: Any) -> int | float | None:
    """Parse a Tencent field string to number; return None for empty/invalid."""
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "--"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _tencent_qt_session() -> Any:
    session = requests.Session()
    session.trust_env = False
    return session


def _parse_tencent_qt_response(text: str) -> dict[str, Any]:
    """Parse a single v_code="..."; response into a {col: value} dict.

    Returns empty dict if response is malformed or too short.
    """
    if "=" not in text:
        return {}
    payload = text.split("=", 1)[1].strip().rstrip(";").strip('"')
    parts = payload.split("~")
    # 真实腾讯响应约 88 字段。截断/异常响应通常远少于 50，用此阈值过滤垃圾。
    if len(parts) < 50:
        return {}
    row: dict[str, Any] = {}
    for index, col in _TENCENT_QT_FIELD_INDEX.items():
        if index >= len(parts):
            continue
        raw = parts[index]
        if col in {"名称", "代码"}:
            row[col] = raw
            continue
        row[col] = _to_number(raw)
    # 单位转换：万 -> 元，亿 -> 元
    if row.get("成交额") is not None:
        row["成交额"] = row["成交额"] * 10000
    if row.get("流通市值") is not None:
        row["流通市值"] = row["流通市值"] * 1e8
    if row.get("总市值") is not None:
        row["总市值"] = row["总市值"] * 1e8
    return row


def _tencent_realtime_multi(codes: list[str], *, asset_type: str) -> pd.DataFrame:
    """Query Tencent qt for multiple codes, return 中文列名 DataFrame."""
    session = _tencent_qt_session()
    rows: list[dict[str, Any]] = []
    for code in codes:
        prefix = _tencent_prefix(code, asset_type)
        response = session.get(
            f"{TENCENT_QT_URL}{prefix}{code}",
            headers=TENCENT_QT_HEADERS,
            timeout=15,
        )
        row = _parse_tencent_qt_response(response.text)
        if not row or row.get("最新价") is None:
            raise SourceDataError(f"Tencent returned empty/invalid quote for {code}")
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame = _with_source(frame, "tencent_qt")
    return frame


def _fetch_stocks_tencent(codes: Iterable[str]) -> pd.DataFrame:
    """Fetch realtime stock quotes from Tencent, fallback to Sina on failure."""
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="stock")
    except Exception as primary_exc:
        try:
            return _sina_stocks_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent stock fetch failed: {primary_exc}; "
                f"Sina stock fetch failed: {fallback_exc}"
            ) from fallback_exc


def _sina_stocks_fallback(codes: list[str]) -> pd.DataFrame:
    """Fallback: use akshare Sina spot, filter to requested codes."""
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.stock_zh_a_spot(), "sina_spot")
    return _filter_by_codes(frame, codes)


def _fetch_indices_tencent(codes: Iterable[str]) -> pd.DataFrame:
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="index")
    except Exception as primary_exc:
        try:
            return _sina_indices_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent index fetch failed: {primary_exc}; "
                f"Sina index fetch failed: {fallback_exc}"
            ) from fallback_exc


def _fetch_etfs_tencent(codes: Iterable[str]) -> pd.DataFrame:
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="etf")
    except Exception as primary_exc:
        try:
            return _sina_etfs_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent etf fetch failed: {primary_exc}; "
                f"Sina etf fetch failed: {fallback_exc}"
            ) from fallback_exc


def _sina_indices_fallback(codes: list[str]) -> pd.DataFrame:
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.stock_zh_index_spot_sina(), "sina_spot")
    return _filter_by_codes(frame, codes)


def _sina_etfs_fallback(codes: list[str]) -> pd.DataFrame:
    """ETF 兜底：akshare 无纯新浪 ETF spot 接口，沿用东财 fund_etf_spot_em。

    注意 source 标记为 akshare_em_etf_spot（反映真实来源），不写 sina_spot，
    避免数据来源造假（spec 6.3 硬约束）。
    """
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.fund_etf_spot_em(), "akshare_em_etf_spot")
    return _filter_by_codes(frame, codes)


TENCENT_MKLINE_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"

# 腾讯 mkline 返回 8 元素: [时间, 开, 收, 高, 低, 量, {}, 额]
# 契约要求: [时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额]
# 注意腾讯是"开收高低"，契约是"开高低收"，需重排。
_TENCENT_MKLINE_INDEX = {
    "时间": 0,
    "开盘": 1,
    "收盘": 2,
    "最高": 3,
    "最低": 4,
    "成交量": 5,
    "成交额": 7,  # 索引6是空{}，跳过
}


def _fetch_intraday_tencent(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    try:
        return _tencent_mkline(code, start, end, asset_type=asset_type)
    except Exception as primary_exc:
        try:
            return _sina_intraday_fallback(code, start, end, asset_type=asset_type)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent intraday fetch failed: {primary_exc}; "
                f"Sina intraday fetch failed: {fallback_exc}"
            ) from fallback_exc


def _tencent_mkline(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    prefix = _tencent_prefix(code, asset_type)
    session = _tencent_qt_session()
    response = session.get(
        TENCENT_MKLINE_URL,
        params={"param": f"{prefix}{code},m1,,320"},
        headers=TENCENT_QT_HEADERS,
        timeout=15,
    )
    payload = response.json()
    node = payload.get("data", {}).get(f"{prefix}{code}", {})
    klines = node.get("m1", [])
    if not klines:
        raise SourceDataError(f"Tencent mkline returned no data for {code}")

    rows: list[dict[str, Any]] = []
    for kline in klines:
        if len(kline) < 8:
            continue
        time_str = str(kline[_TENCENT_MKLINE_INDEX["时间"]])
        parsed_time = pd.to_datetime(time_str, format="%Y%m%d%H%M", errors="coerce")
        row = {
            "时间": parsed_time,
            "开盘": _to_number(kline[_TENCENT_MKLINE_INDEX["开盘"]]),
            "最高": _to_number(kline[_TENCENT_MKLINE_INDEX["最高"]]),
            "最低": _to_number(kline[_TENCENT_MKLINE_INDEX["最低"]]),
            "收盘": _to_number(kline[_TENCENT_MKLINE_INDEX["收盘"]]),
            "成交量": _to_number(kline[_TENCENT_MKLINE_INDEX["成交量"]]),
            "成交额": _to_number(kline[_TENCENT_MKLINE_INDEX["成交额"]]),
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    start_time = pd.to_datetime(start)
    end_time = pd.to_datetime(end)
    frame = frame[
        frame["时间"].notna()
        & (frame["时间"] >= start_time)
        & (frame["时间"] <= end_time)
    ].copy()
    frame = _with_source(frame, "tencent_mkline_1m")
    return frame


def _sina_intraday_fallback(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    """Fallback to akshare Sina minute data."""
    akshare_module = _import_akshare()
    if asset_type == "index":
        sina_symbol = _index_sina_symbol(code)
    else:
        sina_symbol = _stock_sina_symbol(code)
    frame = akshare_module.stock_zh_a_minute(
        symbol=sina_symbol,
        period="1",
        adjust="",
    )
    return _convert_sina_minute_frame(frame, start=start, end=end)
