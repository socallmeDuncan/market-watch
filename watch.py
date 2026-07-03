"""Command-line entry point for Market Watch."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, time as clock_time
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from market_watch.config import ConfigError, load_config
from market_watch.fetchers import (
    SourceDataError,
    fetch_index_intraday,
    fetch_indices,
    fetch_stock_intraday,
    fetch_stocks,
)
from market_watch.intraday import (
    build_intraday_time_range,
    normalize_intraday_frame,
    summarize_intraday,
)
from market_watch.normalize import (
    make_error,
    normalize_index_frame,
    normalize_stock_frame,
)
from market_watch.render import (
    build_json_payload,
    build_today_json_payload,
    render_markdown,
    render_today_markdown,
)
from market_watch.storage import (
    append_snapshots,
    atomic_write_json,
    atomic_write_text,
    read_snapshots_for_trade_date,
    write_intraday_rows,
)
from market_watch.summary import TIMESTAMP_FORMAT, summarize_history


TRADE_DATE_FORMAT = "%Y-%m-%d"


def current_market_timestamp(timezone_name: str) -> tuple[str, str]:
    now = datetime.now(ZoneInfo(timezone_name))
    return now.strftime(TIMESTAMP_FORMAT), now.strftime(TRADE_DATE_FORMAT)


def is_market_time(timestamp: str, timezone_name: str) -> bool:
    local_timestamp = datetime.strptime(timestamp, TIMESTAMP_FORMAT).replace(
        tzinfo=ZoneInfo(timezone_name)
    )
    if local_timestamp.weekday() >= 5:
        return False

    current_time = local_timestamp.time()
    return (
        clock_time(9, 30) <= current_time <= clock_time(11, 30)
        or clock_time(13, 0) <= current_time <= clock_time(15, 0)
    )


def collect_records(
    config: dict,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    errors: list[dict] = []
    targets = config["targets"]
    runtime = config["runtime"]
    retry_count = runtime["retry_count"]
    slow_threshold_seconds = runtime["request_timeout_seconds"]

    stock_targets = targets.get("stocks", [])
    if stock_targets:
        stock_frame, fetch_errors = _fetch_with_retry(
            lambda: fetch_stocks([target["code"] for target in stock_targets]),
            stage="fetch_stocks",
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        errors.extend(fetch_errors)
        if stock_frame is not None:
            stock_records, stock_errors = normalize_stock_frame(
                stock_frame,
                stock_targets,
                timestamp=timestamp,
                trade_date=trade_date,
            )
            records.extend(stock_records)
            errors.extend(stock_errors)

    index_targets = targets.get("indices", [])
    if index_targets:
        index_frame, fetch_errors = _fetch_with_retry(
            lambda: fetch_indices(
                [target["code"] for target in index_targets],
                config["source"]["index_symbol"],
            ),
            stage="fetch_indices",
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        errors.extend(fetch_errors)
        if index_frame is not None:
            index_records, index_errors = normalize_index_frame(
                index_frame,
                index_targets,
                timestamp=timestamp,
                trade_date=trade_date,
            )
            records.extend(index_records)
            errors.extend(index_errors)

    return records, errors


def collect_intraday_records(
    config: dict,
    *,
    timestamp: str,
    trade_date: str,
    start: str,
    end: str,
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    errors: list[dict] = []
    targets = config["targets"]
    runtime = config["runtime"]
    retry_count = runtime["retry_count"]
    slow_threshold_seconds = runtime["request_timeout_seconds"]

    for target in targets.get("stocks", []):
        target_records, target_errors = _normalize_intraday_target(
            target,
            asset_type="stock",
            fetcher=fetch_stock_intraday,
            stage="fetch_stock_intraday",
            timestamp=timestamp,
            trade_date=trade_date,
            start=start,
            end=end,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        records.extend(target_records)
        errors.extend(target_errors)

    for target in targets.get("indices", []):
        target_records, target_errors = _normalize_intraday_target(
            target,
            asset_type="index",
            fetcher=fetch_index_intraday,
            stage="fetch_index_intraday",
            timestamp=timestamp,
            trade_date=trade_date,
            start=start,
            end=end,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        records.extend(target_records)
        errors.extend(target_errors)

    return records, errors


def _normalize_intraday_target(
    target: dict,
    *,
    asset_type: str,
    fetcher: Callable[[str, str, str], Any],
    stage: str,
    timestamp: str,
    trade_date: str,
    start: str,
    end: str,
    retry_count: int,
    slow_threshold_seconds: int,
) -> tuple[list[dict], list[dict]]:
    target_ref = {"asset_type": asset_type, "code": target["code"]}
    frame, errors = _fetch_intraday_with_retry(
        lambda: fetcher(target["code"], start, end),
        stage=stage,
        target=target_ref,
        timestamp=timestamp,
        retry_count=retry_count,
        slow_threshold_seconds=slow_threshold_seconds,
    )
    if frame is None:
        return [], errors

    try:
        records = normalize_intraday_frame(
            frame,
            target,
            asset_type=asset_type,
            trade_date=trade_date,
        )
    except SourceDataError as exc:
        errors.append(
            make_error(
                level="error",
                stage=stage,
                code="INTRADAY_SOURCE_FIELD_MISSING",
                message=str(exc),
                target=target_ref,
                timestamp=timestamp,
            )
        )
        return [], errors

    if not records:
        errors.append(
            make_error(
                level="warning",
                stage=stage,
                code="INTRADAY_NO_ROWS",
                message=f"No intraday rows returned for {asset_type} {target['code']}",
                target=target_ref,
                timestamp=timestamp,
            )
        )

    return records, errors


def _fetch_intraday_with_retry(
    operation: Callable[[], Any],
    *,
    stage: str,
    target: dict,
    timestamp: str,
    retry_count: int,
    slow_threshold_seconds: int,
) -> tuple[Any | None, list[dict]]:
    errors: list[dict] = []
    attempts = retry_count + 1

    for attempt in range(attempts):
        start = time.monotonic()
        try:
            result = operation()
        except SourceDataError as exc:
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="INTRADAY_SOURCE_FIELD_MISSING",
                    message=str(exc),
                    target=target,
                    timestamp=timestamp,
                )
            ]
        except Exception as exc:
            if attempt < attempts - 1:
                continue
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="INTRADAY_SOURCE_FETCH_FAILED",
                    message=str(exc),
                    target=target,
                    timestamp=timestamp,
                )
            ]

        elapsed = time.monotonic() - start
        if elapsed > slow_threshold_seconds:
            errors.append(
                make_error(
                    level="warning",
                    stage=stage,
                    code="INTRADAY_SLOW_FETCH",
                    message=(
                        f"{stage} completed in {elapsed:.2f}s, above "
                        f"{slow_threshold_seconds}s threshold"
                    ),
                    target=target,
                    timestamp=timestamp,
                )
            )
        return result, errors

    return None, errors


def _fetch_with_retry(
    operation: Callable[[], Any],
    *,
    stage: str,
    timestamp: str,
    retry_count: int,
    slow_threshold_seconds: int,
) -> tuple[Any | None, list[dict]]:
    errors: list[dict] = []
    attempts = retry_count + 1

    for attempt in range(attempts):
        start = time.monotonic()
        try:
            result = operation()
        except SourceDataError as exc:
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="SOURCE_FIELD_MISSING",
                    message=str(exc),
                    target=None,
                    timestamp=timestamp,
                )
            ]
        except Exception as exc:
            if attempt < attempts - 1:
                continue
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="SOURCE_FETCH_FAILED",
                    message=str(exc),
                    target=None,
                    timestamp=timestamp,
                )
            ]

        elapsed = time.monotonic() - start
        if elapsed > slow_threshold_seconds:
            errors.append(
                make_error(
                    level="warning",
                    stage=stage,
                    code="SLOW_FETCH",
                    message=(
                        f"{stage} completed in {elapsed:.2f}s, above "
                        f"{slow_threshold_seconds}s threshold"
                    ),
                    target=None,
                    timestamp=timestamp,
                )
            )
        return result, errors

    return None, errors


def run_once(config_path: str = "config.yaml") -> int:
    config = load_config(config_path)
    runtime = config["runtime"]
    storage = config["storage"]
    timestamp, trade_date = current_market_timestamp(runtime["market_timezone"])

    records, errors = collect_records(config, timestamp, trade_date)
    storage_failed = False
    if records:
        try:
            append_snapshots(storage["snapshot_dir"], trade_date, records)
        except Exception as exc:
            storage_failed = True
            errors.append(
                make_error(
                    level="error",
                    stage="storage",
                    code="STORAGE_WRITE_FAILED",
                    message=str(exc),
                    target=None,
                    timestamp=timestamp,
                )
            )

    history_rows = read_snapshots_for_trade_date(storage["snapshot_dir"], trade_date)
    history_summary = summarize_history(
        history_rows,
        windows_minutes=runtime["history_windows_minutes"],
        latest_timestamp=timestamp,
    )
    markdown = render_markdown(timestamp, records, history_summary, errors)
    payload = build_json_payload(timestamp, records, history_summary, errors)

    atomic_write_text(storage["latest_markdown"], markdown)
    atomic_write_json(storage["latest_json"], payload)
    print(markdown, end="")

    if storage_failed:
        return 1
    return 0 if records or errors else 1


def run_backfill_today(config_path: str = "config.yaml") -> int:
    config = load_config(config_path)
    runtime = config["runtime"]
    storage = config["storage"]
    timestamp, trade_date = current_market_timestamp(runtime["market_timezone"])
    start, end = build_intraday_time_range(trade_date)

    records, errors = collect_intraday_records(
        config,
        timestamp=timestamp,
        trade_date=trade_date,
        start=start,
        end=end,
    )
    summary = summarize_intraday(records)

    storage_failed = False
    try:
        write_intraday_rows(storage["intraday_dir"], trade_date, records)
    except Exception as exc:
        storage_failed = True
        errors.append(
            make_error(
                level="error",
                stage="storage",
                code="INTRADAY_STORAGE_WRITE_FAILED",
                message=str(exc),
                target=None,
                timestamp=timestamp,
            )
        )

    time_range = {"start": start, "end": end}
    markdown = render_today_markdown(
        generated_at=timestamp,
        trade_date=trade_date,
        period="1m",
        time_range=time_range,
        rows=records,
        summary=summary,
        errors=errors,
    )
    payload = build_today_json_payload(
        generated_at=timestamp,
        trade_date=trade_date,
        period="1m",
        time_range=time_range,
        rows=records,
        summary=summary,
        errors=errors,
    )

    atomic_write_text(storage["today_markdown"], markdown)
    atomic_write_json(storage["today_json"], payload)
    print(markdown, end="")

    if storage_failed:
        return 1
    return 0 if records or errors else 1


def run_loop(config_path: str, interval_override: int | None = None) -> int:
    try:
        while True:
            config = load_config(config_path)
            runtime = config["runtime"]
            interval = (
                interval_override
                if interval_override is not None
                else runtime["interval_seconds"]
            )
            if interval <= 0:
                raise ValueError("loop interval must be positive")
            timestamp, _trade_date = current_market_timestamp(runtime["market_timezone"])

            if not runtime["market_hours_only"] or is_market_time(
                timestamp, runtime["market_timezone"]
            ):
                run_once(config_path)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("Market Watch stopped.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and render market snapshots.")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    parser.add_argument("--once", action="store_true", help="Run one sample and exit.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument(
        "--backfill-today",
        action="store_true",
        help="Fetch and render today's intraday minute data.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override loop interval in seconds.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.interval is not None and args.interval <= 0:
            raise ValueError("--interval must be positive")
        if args.backfill_today:
            return run_backfill_today(args.config)
        if args.loop:
            return run_loop(args.config, interval_override=args.interval)
        return run_once(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    except ValueError as exc:
        print(f"Interval error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
