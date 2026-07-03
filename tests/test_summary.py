from __future__ import annotations

from market_watch.summary import TIMESTAMP_FORMAT, summarize_history


def make_row(
    timestamp: str,
    code: str = "300857",
    price: object = "295.2",
    *,
    name: str = "Target A",
    asset_type: str = "stock",
    amount: object = "1850000",
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "asset_type": asset_type,
        "code": code,
        "name": name,
        "price": price,
        "amount": amount,
    }


def test_timestamp_format_matches_storage_rows() -> None:
    assert TIMESTAMP_FORMAT == "%Y-%m-%d %H:%M:%S"


def test_summarize_history_filters_15_and_30_minute_windows() -> None:
    rows = [
        make_row("2026-07-03 10:00:00", price="290", amount="1200000"),
        make_row("2026-07-03 10:10:00", price="292", amount="1300000"),
        make_row("2026-07-03 10:20:00", price="296", amount="1400000"),
        make_row("2026-07-03 10:30:00", price="295.2", amount="1850000"),
    ]

    summary = summarize_history(
        rows,
        windows_minutes=[15, 30],
        latest_timestamp="2026-07-03 10:30:00",
    )

    assert summary == {
        "windows_minutes": [15, 30],
        "items": [
            {
                "code": "300857",
                "name": "Target A",
                "asset_type": "stock",
                "window_minutes": 15,
                "sample_count": 2,
                "first_timestamp": "2026-07-03 10:20:00",
                "last_timestamp": "2026-07-03 10:30:00",
                "first_price": 296,
                "last_price": 295.2,
                "price_change": -0.8,
                "price_change_pct": -0.2703,
                "window_high": 296,
                "window_low": 295.2,
                "latest_amount": 1850000,
            },
            {
                "code": "300857",
                "name": "Target A",
                "asset_type": "stock",
                "window_minutes": 30,
                "sample_count": 4,
                "first_timestamp": "2026-07-03 10:00:00",
                "last_timestamp": "2026-07-03 10:30:00",
                "first_price": 290,
                "last_price": 295.2,
                "price_change": 5.2,
                "price_change_pct": 1.7931,
                "window_high": 296,
                "window_low": 290,
                "latest_amount": 1850000,
            },
        ],
    }


def test_summarize_history_includes_each_code_and_window_with_samples() -> None:
    rows = [
        make_row("2026-07-03 10:00:00", code="AAA", price="10", name="First"),
        make_row("2026-07-03 10:20:00", code="BBB", price="20", name="Second"),
        make_row("2026-07-03 10:30:00", code="AAA", price="11", name="First"),
        make_row("2026-07-03 10:30:00", code="BBB", price="22", name="Second"),
    ]

    summary = summarize_history(
        rows,
        windows_minutes=[15, 30],
        latest_timestamp="2026-07-03 10:30:00",
    )

    assert [
        (item["code"], item["window_minutes"], item["sample_count"])
        for item in summary["items"]
    ] == [
        ("AAA", 15, 1),
        ("AAA", 30, 2),
        ("BBB", 15, 2),
        ("BBB", 30, 2),
    ]


def test_summarize_history_handles_empty_rows() -> None:
    assert summarize_history(
        [],
        windows_minutes=[15, 30],
        latest_timestamp="2026-07-03 10:30:00",
    ) == {"windows_minutes": [15, 30], "items": []}


def test_summarize_history_ignores_invalid_timestamp_and_price_rows() -> None:
    rows = [
        make_row("not-a-time", price="290"),
        make_row("2026-07-03 10:20:00", price=""),
        make_row("2026-07-03 10:30:00", price="295.2"),
    ]

    summary = summarize_history(
        rows,
        windows_minutes=[15],
        latest_timestamp="2026-07-03 10:30:00",
    )

    assert summary["items"][0]["sample_count"] == 1
    assert summary["items"][0]["first_price"] == 295.2
    assert summary["items"][0]["last_price"] == 295.2


def test_summarize_history_parses_comma_amount() -> None:
    rows = [
        make_row("2026-07-03 10:30:00", price="295.2", amount="1,850,000"),
    ]

    summary = summarize_history(
        rows,
        windows_minutes=[15],
        latest_timestamp="2026-07-03 10:30:00",
    )

    assert summary["items"][0]["latest_amount"] == 1850000


def test_summarize_history_uses_none_pct_when_first_price_is_zero() -> None:
    rows = [
        make_row("2026-07-03 10:20:00", price="0"),
        make_row("2026-07-03 10:30:00", price="10"),
    ]

    summary = summarize_history(
        rows,
        windows_minutes=[15],
        latest_timestamp="2026-07-03 10:30:00",
    )

    assert summary["items"][0]["price_change"] == 10
    assert summary["items"][0]["price_change_pct"] is None
