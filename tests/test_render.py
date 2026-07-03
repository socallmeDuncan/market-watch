from __future__ import annotations

import re

from market_watch.render import (
    build_json_payload,
    build_today_json_payload,
    render_markdown,
    render_today_markdown,
)


TIMESTAMP = "2026-07-03 10:42:30"


def stock_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "timestamp": TIMESTAMP,
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
        "volume_ratio": 1.43,
        "turnover_rate": 8.1,
        "pe_dynamic": 42.6,
        "pb_ratio": 5.7,
        "total_market_value": 123456789000,
        "circulating_market_value": 98765432100,
        "speed": 0.22,
        "five_min_change": 0.8,
        "sixty_day_change_pct": 18.5,
        "year_to_date_change_pct": 32.1,
        "source": "akshare_em",
    }
    record.update(overrides)
    return record


def index_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "timestamp": TIMESTAMP,
        "trade_date": "2026-07-03",
        "asset_type": "index",
        "code": "399006",
        "name": "创业板指",
        "role": "context",
        "price": 2310.2,
        "change_pct": 0.4,
        "change_amount": 9.2,
        "open": 2298,
        "high": 2320,
        "low": 2285,
        "prev_close": 2301,
        "volume": 123456789,
        "amount": 220000000000,
        "amplitude": 1.52,
        "volume_ratio": None,
        "turnover_rate": None,
        "pe_dynamic": None,
        "pb_ratio": None,
        "total_market_value": None,
        "circulating_market_value": None,
        "speed": None,
        "five_min_change": None,
        "sixty_day_change_pct": None,
        "year_to_date_change_pct": None,
        "source": "akshare_em",
    }
    record.update(overrides)
    return record


def etf_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "timestamp": TIMESTAMP,
        "trade_date": "2026-07-03",
        "asset_type": "etf",
        "code": "159915",
        "name": "创业板ETF易方达",
        "role": "context",
        "price": 4.037,
        "change_pct": 0.02,
        "change_amount": 0.001,
        "open": 4.02,
        "high": 4.05,
        "low": 4,
        "prev_close": 4.036,
        "volume": 1400000000,
        "amount": 5595214000,
        "amplitude": 1.23,
        "volume_ratio": 1.2,
        "turnover_rate": 8.5,
        "pe_dynamic": None,
        "pb_ratio": None,
        "total_market_value": 123456789,
        "circulating_market_value": 120000000,
        "speed": None,
        "five_min_change": None,
        "sixty_day_change_pct": None,
        "year_to_date_change_pct": None,
        "source": "akshare_em_etf_spot",
    }
    record.update(overrides)
    return record


def history_summary() -> dict[str, object]:
    return {
        "windows_minutes": [15],
        "items": [
            {
                "code": "300857",
                "name": "协创数据",
                "asset_type": "stock",
                "window_minutes": 15,
                "sample_count": 2,
                "first_price": 296,
                "last_price": 295.2,
                "window_high": 296,
                "window_low": 295.2,
                "price_change_pct": -0.2703,
            }
        ],
    }


def error_item() -> dict[str, object]:
    return {
        "level": "warning",
        "stage": "normalize_stock",
        "code": "TARGET_MISSING",
        "message": "Configured target not found in source data: stock 300475",
        "target": {"asset_type": "stock", "code": "300475"},
        "timestamp": TIMESTAMP,
    }


def table_header_after(markdown: str, section_title: str) -> list[str]:
    section = markdown.split(section_title, maxsplit=1)[1]
    header_line = next(line for line in section.splitlines() if line.startswith("|"))
    return [cell.strip() for cell in header_line.strip("|").split("|")]


def test_build_json_payload_groups_stock_and_index_records() -> None:
    payload = build_json_payload(
        TIMESTAMP,
        [stock_record(), index_record(), etf_record()],
        history_summary(),
        [error_item()],
    )

    assert payload == {
        "timestamp": TIMESTAMP,
        "current": {
            "stocks": [stock_record()],
            "indices": [index_record()],
            "etfs": [etf_record()],
        },
        "history_summary": history_summary(),
        "errors": [error_item()],
    }


def test_render_markdown_contains_tables_and_no_trading_advice_words() -> None:
    markdown = render_markdown(
        TIMESTAMP,
        [stock_record(), index_record(), etf_record()],
        history_summary(),
        [],
    )

    assert "# 盘中行情数据快照" in markdown
    assert "时间：2026-07-03 10:42:30" in markdown
    assert "## 当前个股行情" in markdown
    assert "## 当前指数行情" in markdown
    assert "## 当前 ETF 行情" in markdown
    assert "协创数据" in markdown
    assert "创业板指" in markdown
    assert "创业板ETF易方达" in markdown
    assert "## 最近 15 分钟客观统计" in markdown
    assert "15m" in markdown
    assert "## 给 ChatGPT 的分析请求" in markdown
    assert "不要假设脚本内置任何交易标准。" in markdown

    forbidden_words = ["买入", "卖出", "持仓", "止损", "止盈", "加仓", "减仓", "观望"]
    assert all(word not in markdown for word in forbidden_words)


def test_render_markdown_uses_exact_current_and_summary_headers() -> None:
    markdown = render_markdown(
        TIMESTAMP,
        [stock_record(), index_record(), etf_record()],
        history_summary(),
        [],
    )

    stock_headers = table_header_after(markdown, "## 当前个股行情")
    index_headers = table_header_after(markdown, "## 当前指数行情")
    etf_headers = table_header_after(markdown, "## 当前 ETF 行情")
    summary_headers = table_header_after(markdown, "## 最近 15 分钟客观统计")

    assert stock_headers == [
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "今开",
        "最高",
        "最低",
        "昨收",
        "成交量",
        "成交额",
        "振幅",
        "量比",
        "换手率",
        "市盈率-动态",
        "市净率",
        "总市值",
        "流通市值",
        "涨速",
        "5分钟涨跌",
        "60日涨跌幅",
        "年初至今涨跌幅",
        "来源",
    ]
    assert ["代码", "名称", "最新价", "成交额"] == [
        index_headers[0],
        index_headers[1],
        index_headers[2],
        index_headers[7],
    ]
    assert index_headers[-1] == "来源"
    assert etf_headers == [
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "今开",
        "最高",
        "最低",
        "昨收",
        "成交量",
        "成交额",
        "振幅",
        "量比",
        "换手率",
        "总市值",
        "流通市值",
        "来源",
    ]
    assert summary_headers == [
        "标的",
        "窗口",
        "样本数",
        "起始价",
        "当前价",
        "区间最高",
        "区间最低",
        "区间涨跌幅",
    ]


def test_render_markdown_displays_missing_rendered_values_as_dash() -> None:
    markdown = render_markdown(
        TIMESTAMP,
        [stock_record(five_min_change=None), index_record(open="")],
        {"windows_minutes": [], "items": []},
        [],
    )

    assert re.search(r"\|\s+-\s+\|", markdown)
    assert "暂无足够历史数据。" in markdown


def test_render_markdown_uses_dynamic_history_window_title() -> None:
    markdown = render_markdown(
        TIMESTAMP,
        [stock_record()],
        {"windows_minutes": [5, 15], "items": []},
        [],
    )

    assert "## 最近 5 / 15 分钟客观统计" in markdown


def test_render_markdown_includes_errors() -> None:
    markdown = render_markdown(
        TIMESTAMP,
        [],
        {"windows_minutes": [], "items": []},
        [error_item()],
    )

    assert "未获取到数据。" in markdown
    assert "## 数据警告" in markdown
    assert "TARGET_MISSING" in markdown
    assert "Configured target not found in source data: stock 300475" in markdown


def intraday_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
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
    row.update(overrides)
    return row


def intraday_summary() -> dict[str, object]:
    return {
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


def test_build_today_json_payload_contains_full_intraday_rows() -> None:
    payload = build_today_json_payload(
        generated_at="2026-07-03 16:05:00",
        trade_date="2026-07-03",
        period="1m",
        time_range={
            "start": "2026-07-03 09:30:00",
            "end": "2026-07-03 15:00:00",
        },
        rows=[intraday_row()],
        summary=intraday_summary(),
        errors=[error_item()],
    )

    assert payload == {
        "generated_at": "2026-07-03 16:05:00",
        "trade_date": "2026-07-03",
        "period": "1m",
        "time_range": {
            "start": "2026-07-03 09:30:00",
            "end": "2026-07-03 15:00:00",
        },
        "rows": [intraday_row()],
        "summary": intraday_summary(),
        "errors": [error_item()],
    }


def test_render_today_markdown_contains_summary_rows_and_no_advice_words() -> None:
    markdown = render_today_markdown(
        generated_at="2026-07-03 16:05:00",
        trade_date="2026-07-03",
        period="1m",
        time_range={
            "start": "2026-07-03 09:30:00",
            "end": "2026-07-03 15:00:00",
        },
        rows=[intraday_row(), intraday_row(timestamp="2026-07-03 09:32:00", close=296)],
        summary=intraday_summary(),
        errors=[],
    )

    assert "# 当日分钟行情数据" in markdown
    assert "生成时间：2026-07-03 16:05:00" in markdown
    assert "交易日期：2026-07-03" in markdown
    assert "请求区间：2026-07-03 09:30:00 -> 2026-07-03 15:00:00" in markdown
    assert "## 当日客观统计" in markdown
    assert "收盘涨跌额" in markdown
    assert "0.8" in markdown
    assert "## 1m 分钟明细" in markdown
    assert "协创数据" in markdown
    assert "2026-07-03 09:32:00" in markdown
    assert "## 给 ChatGPT 的分析请求" in markdown

    forbidden_words = ["买入", "卖出", "持仓", "止损", "止盈", "加仓", "减仓", "观望"]
    assert all(word not in markdown for word in forbidden_words)


def test_render_today_markdown_includes_full_intraday_row_headers() -> None:
    markdown = render_today_markdown(
        generated_at="2026-07-03 16:05:00",
        trade_date="2026-07-03",
        period="1m",
        time_range={
            "start": "2026-07-03 09:30:00",
            "end": "2026-07-03 15:00:00",
        },
        rows=[intraday_row()],
        summary=intraday_summary(),
        errors=[],
    )

    row_headers = table_header_after(markdown, "## 1m 分钟明细")

    assert row_headers == [
        "时间",
        "交易日期",
        "资产类型",
        "代码",
        "名称",
        "角色",
        "周期",
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量",
        "成交额",
        "均价",
        "来源",
    ]


def test_render_today_markdown_includes_errors_and_empty_messages() -> None:
    markdown = render_today_markdown(
        generated_at="2026-07-03 16:05:00",
        trade_date="2026-07-03",
        period="1m",
        time_range={
            "start": "2026-07-03 09:30:00",
            "end": "2026-07-03 15:00:00",
        },
        rows=[],
        summary={"items": []},
        errors=[{**error_item(), "code": "INTRADAY_NO_ROWS", "stage": "backfill"}],
    )

    assert "暂无分钟明细数据。" in markdown
    assert "暂无当日统计数据。" in markdown
    assert "## 数据警告" in markdown
    assert "INTRADAY_NO_ROWS" in markdown
