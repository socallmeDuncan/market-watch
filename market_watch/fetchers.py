"""AKShare fetch wrappers."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


class SourceDataError(RuntimeError):
    """Raised when source data does not have the expected shape."""


def fetch_stocks(codes: Iterable[str], provider: Any | None = None) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    try:
        frame = _with_source(source.stock_zh_a_spot_em(), "akshare_em")
        return _filter_by_codes(frame, codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(source.stock_zh_a_spot(), "akshare_sina_spot")
            return _filter_by_codes(frame, codes)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney stock fetch failed: {primary_exc}; "
                f"Sina stock fetch failed: {fallback_exc}"
            ) from fallback_exc


def fetch_indices(
    codes: Iterable[str], symbol: str, provider: Any | None = None
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    requested_codes = [str(code) for code in codes]
    try:
        frame = _with_source(source.stock_zh_index_spot_em(symbol=symbol), "akshare_em")
        filtered = _filter_by_codes(frame, requested_codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(
                source.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
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
            source.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
        )
        fallback_filtered = _filter_by_codes(fallback_frame, missing_codes)
    except Exception:
        return filtered

    return _filter_by_codes(
        pd.concat([filtered, fallback_filtered], ignore_index=True),
        requested_codes,
    )


def fetch_etfs(codes: Iterable[str], provider: Any | None = None) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    frame = _with_source(source.fund_etf_spot_em(), "akshare_em_etf_spot")
    return _filter_by_codes(frame, codes)



def fetch_stock_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    try:
        frame = source.stock_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            adjust="",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = source.stock_zh_a_minute(
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
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    try:
        frame = source.index_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = source.stock_zh_a_minute(
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
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    frame = source.fund_etf_hist_min_em(
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
