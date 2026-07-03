from __future__ import annotations

import json

import pandas as pd
import yaml

import watch
from market_watch.fetchers import SourceDataError


TIMESTAMP = "2026-07-03 10:15:00"
TRADE_DATE = "2026-07-03"


def source_row(code: str, name: str, price: float) -> dict[str, object]:
    return {
        "代码": code,
        "名称": name,
        "最新价": price,
        "涨跌幅": 1.2,
        "涨跌额": 3.4,
        "今开": price - 1,
        "最高": price + 2,
        "最低": price - 3,
        "昨收": price - 2,
        "成交量": 12345,
        "成交额": 67890,
        "振幅": 2.5,
        "换手率": 1.1,
        "涨速": 0.2,
        "5分钟涨跌": 0.5,
    }


def test_run_once_writes_csv_markdown_and_json(tmp_path, capsys, monkeypatch) -> None:
    config = {
        "targets": {
            "stocks": [{"code": "300857", "name": "协创数据", "role": "primary"}],
            "indices": [{"code": "399006", "name": "创业板指", "role": "context"}],
        },
        "runtime": {
            "market_timezone": "Asia/Shanghai",
            "history_windows_minutes": [15],
            "market_hours_only": True,
        },
        "storage": {
            "snapshot_dir": str(tmp_path / "snapshots"),
            "latest_markdown": str(tmp_path / "latest.md"),
            "latest_json": str(tmp_path / "latest.json"),
        },
        "source": {"index_symbol": "沪深重要指数"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: (TIMESTAMP, TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stocks",
        lambda codes: pd.DataFrame([source_row("300857", "协创数据", 295.2)]),
    )
    monkeypatch.setattr(
        watch,
        "fetch_indices",
        lambda codes, symbol: pd.DataFrame([source_row("399006", "创业板指", 2310.2)]),
    )

    result = watch.run_once(str(config_path))

    snapshot_path = tmp_path / "snapshots" / f"{TRADE_DATE}.csv"
    markdown_path = tmp_path / "latest.md"
    json_path = tmp_path / "latest.json"

    assert result == 0
    assert snapshot_path.exists()
    assert markdown_path.exists()
    assert json_path.exists()
    assert "协创数据" in markdown_path.read_text(encoding="utf-8")
    assert "# 盘中行情数据快照" in capsys.readouterr().out

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["current"]["stocks"][0]["code"] == "300857"
    assert payload["current"]["stocks"][0]["name"] == "协创数据"
    assert payload["current"]["indices"][0]["code"] == "399006"
    assert payload["current"]["indices"][0]["name"] == "创业板指"


def test_market_hours_gate_uses_shanghai_weekday_sessions() -> None:
    timezone_name = "Asia/Shanghai"

    assert watch.is_market_time("2026-07-03 09:30:00", timezone_name)
    assert watch.is_market_time("2026-07-03 11:30:00", timezone_name)
    assert watch.is_market_time("2026-07-03 13:00:00", timezone_name)
    assert watch.is_market_time("2026-07-03 15:00:00", timezone_name)
    assert not watch.is_market_time("2026-07-03 09:29:59", timezone_name)
    assert not watch.is_market_time("2026-07-03 11:30:01", timezone_name)
    assert not watch.is_market_time("2026-07-03 12:30:00", timezone_name)
    assert not watch.is_market_time("2026-07-03 15:00:01", timezone_name)
    assert not watch.is_market_time("2026-07-04 10:00:00", timezone_name)


def test_collect_records_keeps_index_records_when_stock_fetch_fails(
    sample_config_dict, monkeypatch
) -> None:
    def failing_stock_fetch(codes):
        raise RuntimeError("stock source offline")

    monkeypatch.setattr(watch, "fetch_stocks", failing_stock_fetch)
    monkeypatch.setattr(
        watch,
        "fetch_indices",
        lambda codes, symbol: pd.DataFrame(
            [
                source_row("399006", "创业板指", 2310.2),
                source_row("399001", "深证成指", 11000.1),
                source_row("000001", "上证指数", 3200.5),
            ]
        ),
    )

    records, errors = watch.collect_records(sample_config_dict, TIMESTAMP, TRADE_DATE)

    assert [record["asset_type"] for record in records] == ["index", "index", "index"]
    assert errors[0]["stage"] == "fetch_stocks"
    assert errors[0]["code"] == "SOURCE_FETCH_FAILED"


def test_collect_records_retries_stock_fetch_once(sample_config_dict, monkeypatch) -> None:
    sample_config_dict["targets"]["indices"] = []
    calls = {"stock": 0}

    def flaky_stock_fetch(codes):
        calls["stock"] += 1
        if calls["stock"] == 1:
            raise RuntimeError("transient source failure")
        return pd.DataFrame(
            [
                source_row("300857", "协创数据", 295.2),
                source_row("300475", "香农芯创", 42.7),
            ]
        )

    monkeypatch.setattr(watch, "fetch_stocks", flaky_stock_fetch)

    records, errors = watch.collect_records(sample_config_dict, TIMESTAMP, TRADE_DATE)

    assert calls["stock"] == 2
    assert [record["code"] for record in records] == ["300857", "300475"]
    assert errors == []


def test_collect_records_emits_slow_fetch_warning(
    sample_config_dict, monkeypatch
) -> None:
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["runtime"]["request_timeout_seconds"] = 15
    times = iter([100.0, 116.5])

    monkeypatch.setattr(watch.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(
        watch,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                source_row("300857", "协创数据", 295.2),
                source_row("300475", "香农芯创", 42.7),
            ]
        ),
    )

    records, errors = watch.collect_records(sample_config_dict, TIMESTAMP, TRADE_DATE)

    assert [record["code"] for record in records] == ["300857", "300475"]
    assert errors[0]["stage"] == "fetch_stocks"
    assert errors[0]["code"] == "SLOW_FETCH"
    assert errors[0]["level"] == "warning"


def test_collect_records_reports_source_data_error_as_field_missing(
    sample_config_dict, monkeypatch
) -> None:
    sample_config_dict["targets"]["indices"] = []

    def missing_field_fetch(codes):
        raise SourceDataError("Source frame is missing required column: 代码")

    monkeypatch.setattr(watch, "fetch_stocks", missing_field_fetch)

    records, errors = watch.collect_records(sample_config_dict, TIMESTAMP, TRADE_DATE)

    assert records == []
    assert errors[0]["stage"] == "fetch_stocks"
    assert errors[0]["code"] == "SOURCE_FIELD_MISSING"
    assert errors[0]["level"] == "error"


def test_main_once_with_config_calls_run_once(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    called = {}

    def fake_run_once(path: str) -> int:
        called["path"] = path
        return 7

    monkeypatch.setattr(watch, "run_once", fake_run_once)

    assert watch.main(["--once", "--config", str(config_path)]) == 7
    assert called == {"path": str(config_path)}


def test_main_default_with_config_calls_run_once(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    called = {}

    def fake_run_once(path: str) -> int:
        called["path"] = path
        return 0

    monkeypatch.setattr(watch, "run_once", fake_run_once)

    assert watch.main(["--config", str(config_path)]) == 0
    assert called == {"path": str(config_path)}


def test_main_loop_dispatches_to_run_loop_with_interval(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    called = {}

    def fake_run_loop(path: str, interval_override: int | None = None) -> int:
        called["path"] = path
        called["interval_override"] = interval_override
        return 0

    monkeypatch.setattr(watch, "run_loop", fake_run_loop)

    assert (
        watch.main(["--loop", "--interval", "7", "--config", str(config_path)]) == 0
    )
    assert called == {"path": str(config_path), "interval_override": 7}


def test_main_handles_missing_config_cleanly(tmp_path, capsys) -> None:
    result = watch.main(["--once", "--config", str(tmp_path / "missing.yaml")])
    output = capsys.readouterr().out

    assert result == 2
    assert "Config error:" in output
    assert "Traceback" not in output


def test_main_rejects_non_positive_loop_interval(
    monkeypatch, tmp_path, sample_config_dict, capsys
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8"
    )
    calls = {"run_loop": 0}

    def fake_run_loop(path: str, interval_override: int | None = None) -> int:
        calls["run_loop"] += 1
        return 0

    monkeypatch.setattr(watch, "run_loop", fake_run_loop)

    assert (
        watch.main(["--loop", "--interval", "0", "--config", str(config_path)]) == 2
    )
    assert (
        watch.main(["--loop", "--interval", "-1", "--config", str(config_path)]) == 2
    )

    output = capsys.readouterr().out
    assert "Interval error:" in output
    assert "--interval must be positive" in output
    assert "Traceback" not in output
    assert calls["run_loop"] == 0


def test_run_loop_market_hours_gate_skips_outside_market(
    monkeypatch, tmp_path, sample_config_dict, capsys
) -> None:
    config = sample_config_dict
    config["runtime"]["market_hours_only"] = True
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    calls = {"run_once": 0}

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-03 12:00:00", TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "run_once",
        lambda path: calls.__setitem__("run_once", calls["run_once"] + 1),
    )
    monkeypatch.setattr(
        watch.time,
        "sleep",
        lambda interval: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    assert watch.run_loop(str(config_path)) == 0
    assert calls["run_once"] == 0
    assert "Market Watch stopped." in capsys.readouterr().out


def test_run_loop_ignores_market_hours_gate_when_disabled(
    monkeypatch, tmp_path, sample_config_dict
) -> None:
    config = sample_config_dict
    config["runtime"]["market_hours_only"] = False
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    calls = {"run_once": 0}

    def fake_run_once(path: str) -> int:
        calls["run_once"] += 1
        return 0

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-03 12:00:00", TRADE_DATE),
    )
    monkeypatch.setattr(watch, "run_once", fake_run_once)
    monkeypatch.setattr(
        watch.time,
        "sleep",
        lambda interval: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    assert watch.run_loop(str(config_path)) == 0
    assert calls["run_once"] == 1


def test_run_once_samples_outside_market_hours(tmp_path, monkeypatch) -> None:
    config = {
        "targets": {
            "stocks": [{"code": "300857", "name": "协创数据", "role": "primary"}],
            "indices": [{"code": "399006", "name": "创业板指", "role": "context"}],
        },
        "runtime": {
            "market_timezone": "Asia/Shanghai",
            "history_windows_minutes": [15],
            "market_hours_only": True,
        },
        "storage": {
            "snapshot_dir": str(tmp_path / "snapshots"),
            "latest_markdown": str(tmp_path / "latest.md"),
            "latest_json": str(tmp_path / "latest.json"),
        },
        "source": {"index_symbol": "沪深重要指数"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-03 12:00:00", TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stocks",
        lambda codes: pd.DataFrame([source_row("300857", "协创数据", 295.2)]),
    )
    monkeypatch.setattr(
        watch,
        "fetch_indices",
        lambda codes, symbol: pd.DataFrame([source_row("399006", "创业板指", 2310.2)]),
    )

    assert watch.run_once(str(config_path)) == 0
    assert (tmp_path / "snapshots" / f"{TRADE_DATE}.csv").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.json").exists()


def test_run_once_records_storage_failure_in_latest_json(
    tmp_path, monkeypatch, sample_config_dict
) -> None:
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["storage"] = {
        "snapshot_dir": str(tmp_path / "snapshots"),
        "latest_markdown": str(tmp_path / "latest.md"),
        "latest_json": str(tmp_path / "latest.json"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8"
    )

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: (TIMESTAMP, TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                source_row("300857", "协创数据", 295.2),
                source_row("300475", "香农芯创", 42.7),
            ]
        ),
    )

    def failing_append(snapshot_dir, trade_date, records):
        raise OSError("disk full")

    monkeypatch.setattr(watch, "append_snapshots", failing_append)

    assert watch.run_once(str(config_path)) == 1

    payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert payload["errors"][0]["stage"] == "storage"
    assert payload["errors"][0]["code"] == "STORAGE_WRITE_FAILED"
    assert payload["errors"][0]["level"] == "error"


def test_run_once_records_non_os_storage_failure_in_latest_json(
    tmp_path, monkeypatch, sample_config_dict
) -> None:
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["storage"] = {
        "snapshot_dir": str(tmp_path / "snapshots"),
        "latest_markdown": str(tmp_path / "latest.md"),
        "latest_json": str(tmp_path / "latest.json"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8"
    )

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: (TIMESTAMP, TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                source_row("300857", "协创数据", 295.2),
                source_row("300475", "香农芯创", 42.7),
            ]
        ),
    )

    def failing_append(snapshot_dir, trade_date, records):
        raise ValueError("bad row")

    monkeypatch.setattr(watch, "append_snapshots", failing_append)

    assert watch.run_once(str(config_path)) == 1

    payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert payload["errors"][0]["stage"] == "storage"
    assert payload["errors"][0]["code"] == "STORAGE_WRITE_FAILED"
    assert payload["errors"][0]["message"] == "bad row"


def test_main_backfill_today_dispatches_to_run_backfill_today(
    monkeypatch, tmp_path
) -> None:
    config_path = tmp_path / "config.yaml"
    called = {}

    def fake_run_backfill_today(path: str) -> int:
        called["path"] = path
        return 0

    monkeypatch.setattr(watch, "run_backfill_today", fake_run_backfill_today)

    assert watch.main(["--backfill-today", "--config", str(config_path)]) == 0
    assert called == {"path": str(config_path)}


def minute_source_row(timestamp: str, close: float) -> dict[str, object]:
    return {
        "时间": timestamp,
        "开盘": close - 1,
        "收盘": close,
        "最高": close + 2,
        "最低": close - 3,
        "成交量": 12345,
        "成交额": 67890,
        "均价": close - 0.1,
    }


def test_run_backfill_today_writes_intraday_csv_markdown_and_json(
    tmp_path, capsys, monkeypatch
) -> None:
    config = {
        "targets": {
            "stocks": [{"code": "300857", "name": "协创数据", "role": "primary"}],
            "indices": [{"code": "399006", "name": "创业板指", "role": "context"}],
        },
        "runtime": {
            "market_timezone": "Asia/Shanghai",
            "history_windows_minutes": [15],
            "market_hours_only": True,
        },
        "storage": {
            "snapshot_dir": str(tmp_path / "snapshots"),
            "latest_markdown": str(tmp_path / "latest.md"),
            "latest_json": str(tmp_path / "latest.json"),
            "intraday_dir": str(tmp_path / "intraday"),
            "today_markdown": str(tmp_path / "today.md"),
            "today_json": str(tmp_path / "today.json"),
        },
        "source": {"index_symbol": "沪深重要指数"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-03 16:05:00", TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stock_intraday",
        lambda code, start, end: pd.DataFrame(
            [
                minute_source_row("2026-07-03 09:31:00", 295.2),
                minute_source_row("2026-07-03 09:32:00", 296.0),
            ]
        ),
    )
    monkeypatch.setattr(
        watch,
        "fetch_index_intraday",
        lambda code, start, end: pd.DataFrame(
            [minute_source_row("2026-07-03 09:31:00", 2310.2)]
        ),
    )

    result = watch.run_backfill_today(str(config_path))

    assert result == 0
    assert (tmp_path / "intraday" / f"{TRADE_DATE}-1m.csv").exists()
    assert (tmp_path / "today.md").exists()
    assert (tmp_path / "today.json").exists()
    assert "# 当日分钟行情数据" in capsys.readouterr().out

    payload = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))
    assert payload["trade_date"] == TRADE_DATE
    assert payload["time_range"] == {
        "start": "2026-07-03 09:30:00",
        "end": "2026-07-03 15:00:00",
    }
    assert [row["code"] for row in payload["rows"]] == ["300857", "300857", "399006"]
    assert payload["summary"]["items"][0]["row_count"] == 2


def test_run_backfill_today_keeps_successful_target_when_one_target_fails(
    tmp_path, monkeypatch
) -> None:
    config = {
        "targets": {
            "stocks": [{"code": "300857", "name": "协创数据", "role": "primary"}],
            "indices": [{"code": "399006", "name": "创业板指", "role": "context"}],
        },
        "runtime": {"market_timezone": "Asia/Shanghai"},
        "storage": {
            "snapshot_dir": str(tmp_path / "snapshots"),
            "latest_markdown": str(tmp_path / "latest.md"),
            "latest_json": str(tmp_path / "latest.json"),
            "intraday_dir": str(tmp_path / "intraday"),
            "today_markdown": str(tmp_path / "today.md"),
            "today_json": str(tmp_path / "today.json"),
        },
        "source": {"index_symbol": "沪深重要指数"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-03 16:05:00", TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stock_intraday",
        lambda code, start, end: pd.DataFrame(
            [minute_source_row("2026-07-03 09:31:00", 295.2)]
        ),
    )

    def failing_index_fetch(code: str, start: str, end: str) -> pd.DataFrame:
        raise RuntimeError("index source offline")

    monkeypatch.setattr(watch, "fetch_index_intraday", failing_index_fetch)

    result = watch.run_backfill_today(str(config_path))
    payload = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))

    assert result == 0
    assert [row["code"] for row in payload["rows"]] == ["300857"]
    assert payload["errors"][0]["code"] == "INTRADAY_SOURCE_FETCH_FAILED"
    assert payload["errors"][0]["target"] == {"asset_type": "index", "code": "399006"}


def test_run_backfill_today_writes_outputs_when_all_targets_empty(
    tmp_path, monkeypatch
) -> None:
    config = {
        "targets": {
            "stocks": [{"code": "300857", "name": "协创数据", "role": "primary"}],
            "indices": [],
        },
        "runtime": {"market_timezone": "Asia/Shanghai"},
        "storage": {
            "snapshot_dir": str(tmp_path / "snapshots"),
            "latest_markdown": str(tmp_path / "latest.md"),
            "latest_json": str(tmp_path / "latest.json"),
            "intraday_dir": str(tmp_path / "intraday"),
            "today_markdown": str(tmp_path / "today.md"),
            "today_json": str(tmp_path / "today.json"),
        },
        "source": {"index_symbol": "沪深重要指数"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: ("2026-07-04 16:05:00", "2026-07-04"),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stock_intraday",
        lambda code, start, end: pd.DataFrame(
            columns=["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "均价"]
        ),
    )

    result = watch.run_backfill_today(str(config_path))
    payload = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))

    assert result == 0
    assert payload["rows"] == []
    assert payload["summary"] == {"items": []}
    assert payload["errors"][0]["code"] == "INTRADAY_NO_ROWS"
    assert (tmp_path / "intraday" / "2026-07-04-1m.csv").exists()


def test_collect_intraday_records_emits_slow_fetch_warning(
    sample_config_dict, monkeypatch
) -> None:
    sample_config_dict["targets"]["stocks"] = [sample_config_dict["targets"]["stocks"][0]]
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["runtime"]["request_timeout_seconds"] = 15
    times = iter([100.0, 116.5])

    monkeypatch.setattr(watch.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(
        watch,
        "fetch_stock_intraday",
        lambda code, start, end: pd.DataFrame(
            [minute_source_row("2026-07-03 09:31:00", 295.2)]
        ),
    )

    records, errors = watch.collect_intraday_records(
        sample_config_dict,
        timestamp=TIMESTAMP,
        trade_date=TRADE_DATE,
        start="2026-07-03 09:30:00",
        end="2026-07-03 15:00:00",
    )

    assert [record["code"] for record in records] == ["300857"]
    assert errors[0]["stage"] == "fetch_stock_intraday"
    assert errors[0]["code"] == "INTRADAY_SLOW_FETCH"
    assert errors[0]["level"] == "warning"


def test_run_backfill_today_records_storage_failure_in_today_json(
    tmp_path, monkeypatch, sample_config_dict
) -> None:
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["storage"] = {
        "snapshot_dir": str(tmp_path / "snapshots"),
        "latest_markdown": str(tmp_path / "latest.md"),
        "latest_json": str(tmp_path / "latest.json"),
        "intraday_dir": str(tmp_path / "intraday"),
        "today_markdown": str(tmp_path / "today.md"),
        "today_json": str(tmp_path / "today.json"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8"
    )

    monkeypatch.setattr(
        watch,
        "current_market_timestamp",
        lambda timezone_name: (TIMESTAMP, TRADE_DATE),
    )
    monkeypatch.setattr(
        watch,
        "fetch_stock_intraday",
        lambda code, start, end: pd.DataFrame(
            [minute_source_row("2026-07-03 09:31:00", 295.2)]
        ),
    )

    def failing_write(intraday_dir, trade_date, records, period="1m"):
        raise OSError("disk full")

    monkeypatch.setattr(watch, "write_intraday_rows", failing_write)

    assert watch.run_backfill_today(str(config_path)) == 1

    payload = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))
    assert payload["errors"][-1]["code"] == "INTRADAY_STORAGE_WRITE_FAILED"
    assert payload["errors"][-1]["message"] == "disk full"
