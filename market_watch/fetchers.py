"""AKShare fetch wrappers."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


class SourceDataError(RuntimeError):
    """Raised when source data does not have the expected shape."""


def fetch_stocks(codes: Iterable[str], provider: Any | None = None) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    frame = source.stock_zh_a_spot_em()
    return _filter_by_codes(frame, codes)


def fetch_indices(
    codes: Iterable[str], symbol: str, provider: Any | None = None
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    frame = source.stock_zh_index_spot_em(symbol=symbol)
    return _filter_by_codes(frame, codes)


def fetch_stock_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    return source.stock_zh_a_hist_min_em(
        symbol=str(code),
        period="1",
        adjust="",
        start_date=start,
        end_date=end,
    )


def fetch_index_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    return source.index_zh_a_hist_min_em(
        symbol=str(code),
        period="1",
        start_date=start,
        end_date=end,
    )


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


def _source_code_to_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _import_akshare() -> Any:
    import akshare

    return akshare
