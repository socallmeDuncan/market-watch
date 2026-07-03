from __future__ import annotations

import csv
import json
from pathlib import Path

from market_watch.intraday import INTRADAY_FIELDS
from market_watch.normalize import SNAPSHOT_FIELDS
from market_watch.storage import (
    append_snapshots,
    atomic_write_json,
    atomic_write_text,
    intraday_path,
    read_intraday_rows,
    read_snapshots_for_trade_date,
    snapshot_path,
    write_intraday_rows,
)


def make_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {field: "" for field in SNAPSHOT_FIELDS}
    record.update(
        {
            "timestamp": "2026-07-03 10:42:30",
            "trade_date": "2026-07-03",
            "asset_type": "stock",
            "code": "300857",
            "name": "协创数据",
            "role": "primary",
            "price": 295.2,
            "change_pct": 0.55,
            "source": "akshare_em",
        }
    )
    record.update(overrides)
    return record


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.reader(file))


def test_snapshot_path_uses_trade_date(tmp_path: Path) -> None:
    assert snapshot_path(tmp_path / "snapshots", "2026-07-03") == (
        tmp_path / "snapshots" / "2026-07-03.csv"
    )


def test_append_snapshots_writes_single_header(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"

    path = append_snapshots(
        snapshot_dir,
        "2026-07-03",
        [make_record(code="300857")],
    )
    second_path = append_snapshots(
        snapshot_dir,
        "2026-07-03",
        [make_record(code="300475", name="香农芯创", price=None)],
    )

    rows = read_csv_rows(path)
    assert second_path == path
    assert rows[0] == SNAPSHOT_FIELDS
    assert [row[SNAPSHOT_FIELDS.index("code")] for row in rows[1:]] == [
        "300857",
        "300475",
    ]
    assert rows.count(SNAPSHOT_FIELDS) == 1
    assert rows[2][SNAPSHOT_FIELDS.index("price")] == ""


def test_append_snapshots_writes_header_when_existing_file_is_empty(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    path = snapshot_path(snapshot_dir, "2026-07-03")
    path.parent.mkdir(parents=True)
    path.touch()

    append_snapshots(snapshot_dir, "2026-07-03", [make_record(code="300857")])

    rows = read_csv_rows(path)
    assert rows[0] == SNAPSHOT_FIELDS
    assert len(rows) == 2
    assert read_snapshots_for_trade_date(snapshot_dir, "2026-07-03")[0]["code"] == (
        "300857"
    )


def test_append_snapshots_preserves_snapshot_fields_column_order(tmp_path: Path) -> None:
    path = append_snapshots(
        tmp_path / "snapshots",
        "2026-07-03",
        [make_record()],
    )

    assert read_csv_rows(path)[0] == SNAPSHOT_FIELDS


def test_read_snapshots_for_trade_date_returns_dict_rows(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    append_snapshots(
        snapshot_dir,
        "2026-07-03",
        [
            make_record(code="300857", price=295.2, turnover_rate=None),
            make_record(code="300475", name="香农芯创", price=252),
        ],
    )

    rows = read_snapshots_for_trade_date(snapshot_dir, "2026-07-03")

    assert rows == [
        {
            **{field: "" for field in SNAPSHOT_FIELDS},
            "timestamp": "2026-07-03 10:42:30",
            "trade_date": "2026-07-03",
            "asset_type": "stock",
            "code": "300857",
            "name": "协创数据",
            "role": "primary",
            "price": "295.2",
            "change_pct": "0.55",
            "source": "akshare_em",
        },
        {
            **{field: "" for field in SNAPSHOT_FIELDS},
            "timestamp": "2026-07-03 10:42:30",
            "trade_date": "2026-07-03",
            "asset_type": "stock",
            "code": "300475",
            "name": "香农芯创",
            "role": "primary",
            "price": "252",
            "change_pct": "0.55",
            "source": "akshare_em",
        },
    ]


def test_read_missing_trade_date_returns_empty_list(tmp_path: Path) -> None:
    assert read_snapshots_for_trade_date(tmp_path / "snapshots", "2026-07-03") == []


def test_atomic_write_text(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "report.txt"

    result = atomic_write_text(path, "first")
    second_result = atomic_write_text(path, "second")

    assert result == path
    assert second_result == path
    assert path.read_text(encoding="utf-8") == "second"
    assert list(path.parent.glob("*.tmp")) == []


def test_atomic_write_json(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"
    payload = {"name": "协创数据", "items": [1, 2]}

    result = atomic_write_json(path, payload)

    assert result == path
    assert path.read_text(encoding="utf-8") == (
        '{\n  "name": "协创数据",\n  "items": [\n    1,\n    2\n  ]\n}\n'
    )
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert list(path.parent.glob("*.tmp")) == []


def make_intraday_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in INTRADAY_FIELDS}
    row.update(
        {
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
            "average_price": None,
            "source": "akshare_em_intraday_1m",
        }
    )
    row.update(overrides)
    return row


def test_intraday_path_uses_trade_date_and_period(tmp_path: Path) -> None:
    assert intraday_path(tmp_path / "intraday", "2026-07-03", "1m") == (
        tmp_path / "intraday" / "2026-07-03-1m.csv"
    )


def test_write_intraday_rows_replaces_existing_file_without_duplicates(
    tmp_path: Path,
) -> None:
    intraday_dir = tmp_path / "intraday"

    path = write_intraday_rows(
        intraday_dir,
        "2026-07-03",
        [make_intraday_row(code="300857")],
    )
    second_path = write_intraday_rows(
        intraday_dir,
        "2026-07-03",
        [make_intraday_row(code="300475", name="香农芯创", close=None)],
    )

    rows = read_csv_rows(path)
    assert second_path == path
    assert rows[0] == INTRADAY_FIELDS
    assert len(rows) == 2
    assert rows[1][INTRADAY_FIELDS.index("code")] == "300475"
    assert rows[1][INTRADAY_FIELDS.index("close")] == ""
    assert read_intraday_rows(intraday_dir, "2026-07-03")[0]["code"] == "300475"


def test_write_intraday_rows_writes_header_for_empty_rows(tmp_path: Path) -> None:
    path = write_intraday_rows(tmp_path / "intraday", "2026-07-03", [])

    assert read_csv_rows(path) == [INTRADAY_FIELDS]
    assert read_intraday_rows(tmp_path / "intraday", "2026-07-03") == []
