"""Markdown and JSON rendering."""

from __future__ import annotations

from typing import Any

import pandas as pd


STOCK_COLUMNS = [
    ("code", "代码"),
    ("name", "名称"),
    ("price", "最新价"),
    ("change_pct", "涨跌幅"),
    ("open", "今开"),
    ("high", "最高"),
    ("low", "最低"),
    ("prev_close", "昨收"),
    ("volume", "成交量"),
    ("amount", "成交额"),
    ("amplitude", "振幅"),
    ("volume_ratio", "量比"),
    ("turnover_rate", "换手率"),
    ("pe_dynamic", "市盈率-动态"),
    ("pb_ratio", "市净率"),
    ("total_market_value", "总市值"),
    ("circulating_market_value", "流通市值"),
    ("speed", "涨速"),
    ("five_min_change", "5分钟涨跌"),
    ("sixty_day_change_pct", "60日涨跌幅"),
    ("year_to_date_change_pct", "年初至今涨跌幅"),
    ("source", "来源"),
]

INDEX_COLUMNS = [
    ("code", "代码"),
    ("name", "名称"),
    ("price", "最新价"),
    ("change_pct", "涨跌幅"),
    ("open", "今开"),
    ("high", "最高"),
    ("low", "最低"),
    ("amount", "成交额"),
    ("source", "来源"),
]

ETF_COLUMNS = [
    ("code", "代码"),
    ("name", "名称"),
    ("price", "最新价"),
    ("change_pct", "涨跌幅"),
    ("open", "今开"),
    ("high", "最高"),
    ("low", "最低"),
    ("prev_close", "昨收"),
    ("volume", "成交量"),
    ("amount", "成交额"),
    ("amplitude", "振幅"),
    ("volume_ratio", "量比"),
    ("turnover_rate", "换手率"),
    ("total_market_value", "总市值"),
    ("circulating_market_value", "流通市值"),
    ("source", "来源"),
]

SUMMARY_COLUMNS = [
    ("name", "标的"),
    ("window_minutes", "窗口"),
    ("sample_count", "样本数"),
    ("first_price", "起始价"),
    ("last_price", "当前价"),
    ("window_high", "区间最高"),
    ("window_low", "区间最低"),
    ("price_change_pct", "区间涨跌幅"),
]

ERROR_COLUMNS = [
    ("level", "级别"),
    ("stage", "阶段"),
    ("code", "代码"),
    ("message", "说明"),
    ("target", "目标"),
    ("timestamp", "时间"),
]

INTRADAY_SUMMARY_COLUMNS = [
    ("name", "标的"),
    ("period", "周期"),
    ("row_count", "行数"),
    ("first_timestamp", "起始时间"),
    ("last_timestamp", "结束时间"),
    ("first_close", "起始收盘"),
    ("last_close", "最新收盘"),
    ("day_high", "最高"),
    ("day_low", "最低"),
    ("close_change", "收盘涨跌额"),
    ("close_change_pct", "收盘涨跌幅"),
    ("total_volume", "成交量"),
    ("total_amount", "成交额"),
]

INTRADAY_ROW_COLUMNS = [
    ("timestamp", "时间"),
    ("trade_date", "交易日期"),
    ("asset_type", "资产类型"),
    ("code", "代码"),
    ("name", "名称"),
    ("role", "角色"),
    ("period", "周期"),
    ("open", "开盘"),
    ("high", "最高"),
    ("low", "最低"),
    ("close", "收盘"),
    ("volume", "成交量"),
    ("amount", "成交额"),
    ("average_price", "均价"),
    ("source", "来源"),
]


def build_json_payload(
    timestamp: str,
    records: list[dict[str, Any]],
    history_summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "current": {
            "stocks": [
                record for record in records if record.get("asset_type") == "stock"
            ],
            "indices": [
                record for record in records if record.get("asset_type") == "index"
            ],
            "etfs": [
                record for record in records if record.get("asset_type") == "etf"
            ],
        },
        "history_summary": history_summary,
        "errors": errors,
    }


def render_markdown(
    timestamp: str,
    records: list[dict[str, Any]],
    history_summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> str:
    payload = build_json_payload(timestamp, records, history_summary, errors)
    history_title = _history_title(history_summary.get("windows_minutes", []))

    parts = [
        "# 盘中行情数据快照",
        "",
        f"时间：{timestamp}",
        "",
        "## 当前个股行情",
        "",
        _render_table(payload["current"]["stocks"], STOCK_COLUMNS, "未获取到数据。"),
        "",
        "## 当前指数行情",
        "",
        _render_table(payload["current"]["indices"], INDEX_COLUMNS, "未获取到数据。"),
        "",
        "## 当前 ETF 行情",
        "",
        _render_table(payload["current"]["etfs"], ETF_COLUMNS, "未获取到数据。"),
        "",
        history_title,
        "",
        _render_summary_table(history_summary),
    ]

    if errors:
        parts.extend(
            [
                "",
                "## 数据警告",
                "",
                _render_table(errors, ERROR_COLUMNS, "暂无数据警告。"),
            ]
        )

    parts.extend(
        [
            "",
            "## 给 ChatGPT 的分析请求",
            "",
            "请基于以上客观行情数据，描述当前标的和相关指数的走势变化、",
            "短周期价格变化和数据缺失情况。请只基于表格事实进行分析，",
            "不要假设脚本内置任何交易标准。",
        ]
    )

    return "\n".join(parts).rstrip() + "\n"


def build_today_json_payload(
    *,
    generated_at: str,
    trade_date: str,
    period: str,
    time_range: dict[str, str],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "trade_date": trade_date,
        "period": period,
        "time_range": time_range,
        "rows": rows,
        "summary": summary,
        "errors": errors,
    }


def render_today_markdown(
    *,
    generated_at: str,
    trade_date: str,
    period: str,
    time_range: dict[str, str],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> str:
    actual_range = _actual_intraday_range(rows)
    parts = [
        "# 当日分钟行情数据",
        "",
        f"生成时间：{generated_at}",
        "",
        f"交易日期：{trade_date}",
        "",
        f"请求区间：{time_range['start']} -> {time_range['end']}",
        "",
        f"实际返回区间：{actual_range}",
        "",
        "## 当日客观统计",
        "",
        _render_table(summary.get("items", []), INTRADAY_SUMMARY_COLUMNS, "暂无当日统计数据。"),
        "",
        f"## {period} 分钟明细",
        "",
        _render_table(rows, INTRADAY_ROW_COLUMNS, "暂无分钟明细数据。"),
    ]

    if errors:
        parts.extend(
            [
                "",
                "## 数据警告",
                "",
                _render_table(errors, ERROR_COLUMNS, "暂无数据警告。"),
            ]
        )

    parts.extend(
        [
            "",
            "## 给 ChatGPT 的分析请求",
            "",
            "请基于以上客观分钟行情数据，描述各标的当日价格、成交量、",
            "成交额和数据缺失情况。请只基于表格事实进行分析，",
            "不要假设脚本内置任何交易标准。",
        ]
    )

    return "\n".join(parts).rstrip() + "\n"


def _actual_intraday_range(rows: list[dict[str, Any]]) -> str:
    timestamps = [
        str(row.get("timestamp"))
        for row in rows
        if row.get("timestamp") not in (None, "")
    ]
    if not timestamps:
        return "-"
    timestamps = sorted(timestamps)
    return f"{timestamps[0]} -> {timestamps[-1]}"


def _history_title(windows_minutes: Any) -> str:
    if not windows_minutes:
        return "## 最近 历史 分钟客观统计"
    windows = " / ".join(str(window) for window in windows_minutes)
    return f"## 最近 {windows} 分钟客观统计"


def _render_summary_table(history_summary: dict[str, Any]) -> str:
    rows = []
    for item in history_summary.get("items", []):
        row = dict(item)
        window_minutes = row.get("window_minutes")
        row["window_minutes"] = (
            f"{window_minutes}m" if window_minutes not in (None, "") else window_minutes
        )
        rows.append(row)
    return _render_table(rows, SUMMARY_COLUMNS, "暂无足够历史数据。")


def _render_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    empty_message: str,
) -> str:
    if not rows:
        return empty_message

    table_rows = []
    for row in rows:
        table_rows.append(
            {label: _format_display_value(row.get(field)) for field, label in columns}
        )

    return pd.DataFrame(table_rows).to_markdown(index=False)


def _format_display_value(value: Any) -> Any:
    if value is None or value == "":
        return "-"
    if isinstance(value, dict):
        return ", ".join(f"{key}={_format_display_value(item)}" for key, item in value.items())
    return value
