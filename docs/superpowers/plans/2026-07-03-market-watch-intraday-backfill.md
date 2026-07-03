# Market Watch Intraday Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a data-only `--backfill-today` command that fetches today's one-minute A-share intraday bars for configured stocks and indices, stores them separately from real-time snapshots, and renders `outputs/today.md` plus `outputs/today.json`.

**Architecture:** Keep the existing snapshot collector untouched and add a parallel intraday path: fetch target-level minute bars, normalize them into a separate OHLCV schema, replace a daily intraday CSV, summarize objective facts, and render standalone today outputs. Use CSV-first storage and mocked/provider-injected tests; do not add SQLite, trading calendars, dashboards, or trading rules.

**Tech Stack:** Python 3.9+, AKShare, pandas, PyYAML, tabulate, pytest, standard-library `argparse`, `csv`, `datetime`, `json`, `math`, `os`, `pathlib`, `tempfile`, `time`, and `zoneinfo`.

---

## Source Spec

Implement from `docs/superpowers/specs/2026-07-03-market-watch-intraday-backfill-design.md`.

Current workspace note: the repository is git-initialized but may not yet have a baseline commit. The commit checkpoints below assume execution after the current base has been committed. If `git rev-parse HEAD` fails during execution, skip the commit command for that task and record the skipped checkpoint in the execution notes.

## File Structure

Create or modify these files only:

- `config.yaml`: add optional intraday output paths under `storage`.
- `README.md`: document the backfill command and output files.
- `watch.py`: add CLI routing and the backfill orchestration pipeline.
- `market_watch/config.py`: add storage defaults and validation for intraday output paths.
- `market_watch/fetchers.py`: add AKShare one-minute stock and index wrappers.
- `market_watch/intraday.py`: create intraday schema, time-range, normalization, and objective daily summary helpers.
- `market_watch/storage.py`: add intraday CSV path and atomic replacement writer.
- `market_watch/render.py`: add today Markdown and JSON renderers.
- `tests/test_config.py`: add config default and validation coverage.
- `tests/test_fetchers.py`: add provider-injected intraday fetch wrapper coverage.
- `tests/test_intraday.py`: create tests for time range, normalization, and summary.
- `tests/test_storage.py`: add intraday CSV replacement coverage.
- `tests/test_render.py`: add today Markdown and JSON rendering coverage.
- `tests/test_watch.py`: add CLI and end-to-end backfill pipeline coverage.

Do not add trading thresholds, buy/sell advice, strategy labels, exchange-calendar logic, SQLite, APIs, or notification delivery.

---

### Task 1: Add Intraday Storage Configuration

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py`
- Modify: `market_watch/config.py`
- Modify: `config.yaml`

- [ ] **Step 1: Write failing config default tests**

Append these tests to `tests/test_config.py`:

```python
def test_load_config_applies_intraday_storage_defaults(
    tmp_path: Path, sample_config_dict: dict
) -> None:
    sample_config_dict["storage"].pop("intraday_dir", None)
    sample_config_dict["storage"].pop("today_markdown", None)
    sample_config_dict["storage"].pop("today_json", None)
    path = write_yaml(tmp_path / "config.yaml", sample_config_dict)

    config = load_config(path)

    assert config["storage"]["intraday_dir"] == "data/intraday"
    assert config["storage"]["today_markdown"] == "outputs/today.md"
    assert config["storage"]["today_json"] == "outputs/today.json"


def test_validate_config_rejects_empty_intraday_storage_path(
    sample_config_dict: dict,
) -> None:
    sample_config_dict["storage"]["intraday_dir"] = ""

    with pytest.raises(ConfigError, match="intraday_dir"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_empty_today_markdown_path(
    sample_config_dict: dict,
) -> None:
    sample_config_dict["storage"]["today_markdown"] = " "

    with pytest.raises(ConfigError, match="today_markdown"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_empty_today_json_path(
    sample_config_dict: dict,
) -> None:
    sample_config_dict["storage"]["today_json"] = ""

    with pytest.raises(ConfigError, match="today_json"):
        validate_config(sample_config_dict)
```

- [ ] **Step 2: Run config tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected: the new default test fails with `KeyError: 'intraday_dir'` or the validation tests fail because the new fields are not checked yet.

- [ ] **Step 3: Add config defaults and validation**

In `market_watch/config.py`, update `DEFAULT_CONFIG["storage"]` to:

```python
    "storage": {
        "snapshot_dir": "data/snapshots",
        "latest_markdown": "outputs/latest.md",
        "latest_json": "outputs/latest.json",
        "intraday_dir": "data/intraday",
        "today_markdown": "outputs/today.md",
        "today_json": "outputs/today.json",
    },
```

In `validate_config`, extend the storage validation block to:

```python
    storage = _require_mapping(config, "storage")
    _require_non_empty_string(storage, "snapshot_dir")
    _require_non_empty_string(storage, "latest_markdown")
    _require_non_empty_string(storage, "latest_json")
    _require_non_empty_string(storage, "intraday_dir")
    _require_non_empty_string(storage, "today_markdown")
    _require_non_empty_string(storage, "today_json")
```

- [ ] **Step 4: Add intraday paths to the shared config fixture**

Update the `storage` mapping in `tests/conftest.py` to:

```python
        "storage": {
            "snapshot_dir": "data/snapshots",
            "latest_markdown": "outputs/latest.md",
            "latest_json": "outputs/latest.json",
            "intraday_dir": "data/intraday",
            "today_markdown": "outputs/today.md",
            "today_json": "outputs/today.json",
        },
```

- [ ] **Step 5: Add intraday paths to the default config file**

Update `config.yaml` storage section to:

```yaml
storage:
  snapshot_dir: "data/snapshots"
  latest_markdown: "outputs/latest.md"
  latest_json: "outputs/latest.json"
  intraday_dir: "data/intraday"
  today_markdown: "outputs/today.md"
  today_json: "outputs/today.json"
```

- [ ] **Step 6: Run config tests and confirm pass**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected: all config tests pass.

- [ ] **Step 7: Commit checkpoint**

Run:

```bash
git add config.yaml market_watch/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: add intraday output config"
```

If there is no baseline `HEAD`, skip the commit command and note: `Task 1 checkpoint skipped because repository has no initial commit`.

---

### Task 2: Add Intraday Fetchers and Normalization

**Files:**
- Modify: `tests/test_fetchers.py`
- Create: `tests/test_intraday.py`
- Modify: `market_watch/fetchers.py`
- Create: `market_watch/intraday.py`

- [ ] **Step 1: Write failing fetcher tests**

Append these tests to `tests/test_fetchers.py`:

```python
from market_watch.fetchers import fetch_index_intraday, fetch_stock_intraday


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
```

- [ ] **Step 2: Write failing intraday normalization tests**

Create `tests/test_intraday.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from market_watch.fetchers import SourceDataError
from market_watch.intraday import (
    INTRADAY_FIELDS,
    build_intraday_time_range,
    normalize_intraday_frame,
    summarize_intraday,
)


def target(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "code": "300857",
        "name": "协创数据",
        "role": "primary",
    }
    item.update(overrides)
    return item


def minute_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "时间": "2026-07-03 09:31:00",
                "开盘": "294.5",
                "收盘": "295.2",
                "最高": "296.0",
                "最低": "294.0",
                "成交量": "1,234",
                "成交额": "5678900",
                "均价": "295.1",
            },
            {
                "时间": "2026-07-03 09:32:00",
                "开盘": 295.2,
                "收盘": 296.0,
                "最高": 296.5,
                "最低": 295.0,
                "成交量": 2345,
                "成交额": 6789000,
                "均价": 295.8,
            },
        ]
    )


def test_build_intraday_time_range_uses_regular_a_share_session() -> None:
    assert build_intraday_time_range("2026-07-03") == (
        "2026-07-03 09:30:00",
        "2026-07-03 15:00:00",
    )


def test_normalize_intraday_frame_maps_minute_rows_to_schema() -> None:
    rows = normalize_intraday_frame(
        minute_frame(),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    assert list(rows[0].keys()) == INTRADAY_FIELDS
    assert rows[0] == {
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
    assert rows[1]["close"] == 296
    assert rows[1]["volume"] == 2345


def test_normalize_intraday_frame_raises_when_required_column_missing() -> None:
    frame = minute_frame().drop(columns=["成交额"])

    with pytest.raises(SourceDataError, match="Source frame is missing required column: 成交额"):
        normalize_intraday_frame(
            frame,
            target(),
            asset_type="stock",
            trade_date="2026-07-03",
        )


def test_normalize_intraday_frame_keeps_missing_average_price_as_none() -> None:
    frame = minute_frame().drop(columns=["均价"])

    rows = normalize_intraday_frame(
        frame,
        target(),
        asset_type="index",
        trade_date="2026-07-03",
    )

    assert rows[0]["asset_type"] == "index"
    assert rows[0]["average_price"] is None


def test_summarize_intraday_computes_objective_facts_only() -> None:
    rows = normalize_intraday_frame(
        minute_frame(),
        target(),
        asset_type="stock",
        trade_date="2026-07-03",
    )

    summary = summarize_intraday(rows)

    assert summary == {
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
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_fetchers.py tests/test_intraday.py -v
```

Expected: failures for missing `fetch_stock_intraday`, `fetch_index_intraday`, and `market_watch.intraday`.

- [ ] **Step 4: Add intraday fetch wrappers**

Add these functions to `market_watch/fetchers.py` below `fetch_indices`:

```python
def fetch_stock_intraday(
    code: str,
    *,
    start: str,
    end: str,
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
    *,
    start: str,
    end: str,
    provider: Any | None = None,
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
    return source.index_zh_a_hist_min_em(
        symbol=str(code),
        period="1",
        start_date=start,
        end_date=end,
    )
```

- [ ] **Step 5: Create intraday helper module**

Create `market_watch/intraday.py`:

```python
"""Intraday minute-bar normalization and objective summaries."""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any

import pandas as pd

from market_watch.fetchers import SourceDataError


INTRADAY_FIELDS = [
    "timestamp",
    "trade_date",
    "asset_type",
    "code",
    "name",
    "role",
    "period",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "average_price",
    "source",
]

REQUIRED_INTRADAY_COLUMNS = ["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
OPTIONAL_INTRADAY_COLUMNS = ["均价"]
SOURCE_NAME = "akshare_em_intraday_1m"


def build_intraday_time_range(trade_date: str) -> tuple[str, str]:
    return f"{trade_date} 09:30:00", f"{trade_date} 15:00:00"


def normalize_intraday_frame(
    frame: pd.DataFrame,
    target: dict[str, Any],
    *,
    asset_type: str,
    trade_date: str,
) -> list[dict[str, Any]]:
    for column in REQUIRED_INTRADAY_COLUMNS:
        if column not in frame.columns:
            raise SourceDataError(f"Source frame is missing required column: {column}")

    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        timestamp = _format_timestamp(source_row.get("时间"))
        if timestamp is None:
            continue
        row = {
            "timestamp": timestamp,
            "trade_date": trade_date,
            "asset_type": asset_type,
            "code": str(target["code"]),
            "name": str(target["name"]),
            "role": str(target["role"]),
            "period": "1m",
            "open": _format_number(_parse_number(source_row.get("开盘"))),
            "high": _format_number(_parse_number(source_row.get("最高"))),
            "low": _format_number(_parse_number(source_row.get("最低"))),
            "close": _format_number(_parse_number(source_row.get("收盘"))),
            "volume": _format_number(_parse_number(source_row.get("成交量"))),
            "amount": _format_number(_parse_number(source_row.get("成交额"))),
            "average_price": _format_number(_parse_number(source_row.get("均价"))),
            "source": SOURCE_NAME,
        }
        if row["close"] is not None:
            rows.append(row)
    return rows


def summarize_intraday(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: "OrderedDict[tuple[str, str], list[dict[str, Any]]]" = OrderedDict()
    for row in rows:
        key = (str(row.get("asset_type", "")), str(row.get("code", "")))
        grouped.setdefault(key, []).append(row)

    items: list[dict[str, Any]] = []
    for group_rows in grouped.values():
        samples = sorted(group_rows, key=lambda item: str(item.get("timestamp", "")))
        closes = [_parse_number(item.get("close")) for item in samples]
        highs = [_parse_number(item.get("high")) for item in samples]
        lows = [_parse_number(item.get("low")) for item in samples]
        volumes = [_parse_number(item.get("volume")) for item in samples]
        amounts = [_parse_number(item.get("amount")) for item in samples]
        closes = [value for value in closes if value is not None]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        volumes = [value for value in volumes if value is not None]
        amounts = [value for value in amounts if value is not None]
        if not samples or not closes:
            continue

        first = samples[0]
        last = samples[-1]
        first_close = closes[0]
        last_close = closes[-1]
        close_change = last_close - first_close
        close_change_pct = (
            close_change / first_close * 100 if first_close not in (None, 0) else None
        )
        items.append(
            {
                "asset_type": last["asset_type"],
                "code": last["code"],
                "name": last["name"],
                "role": last["role"],
                "period": last["period"],
                "first_timestamp": first["timestamp"],
                "last_timestamp": last["timestamp"],
                "first_close": _format_number(first_close),
                "last_close": _format_number(last_close),
                "day_high": _format_number(max(highs) if highs else None),
                "day_low": _format_number(min(lows) if lows else None),
                "close_change": _format_number(close_change),
                "close_change_pct": _format_number(close_change_pct),
                "total_volume": _format_number(sum(volumes) if volumes else None),
                "total_amount": _format_number(sum(amounts) if amounts else None),
                "row_count": len(samples),
            }
        )

    return {"items": items}


def _format_timestamp(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        timestamp = pd.to_datetime(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(timestamp):
        return None
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _parse_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _format_number(value: float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(value, 4)
    if rounded == 0:
        return 0
    if rounded.is_integer():
        return int(rounded)
    return rounded
```

- [ ] **Step 6: Run focused tests and confirm pass**

Run:

```bash
python3 -m pytest tests/test_fetchers.py tests/test_intraday.py -v
```

Expected: all tests in both files pass.

- [ ] **Step 7: Commit checkpoint**

Run:

```bash
git add market_watch/fetchers.py market_watch/intraday.py tests/test_fetchers.py tests/test_intraday.py
git commit -m "feat: add intraday fetch and normalize helpers"
```

If there is no baseline `HEAD`, skip the commit command and record the skipped checkpoint.

---

### Task 3: Add Intraday CSV Replacement Storage

**Files:**
- Modify: `tests/test_storage.py`
- Modify: `market_watch/storage.py`

- [ ] **Step 1: Write failing storage tests**

Append these imports to the existing import block in `tests/test_storage.py`:

```python
from market_watch.intraday import INTRADAY_FIELDS
```

Add these names to the `from market_watch.storage import (...)` block:

```python
    intraday_path,
    read_intraday_rows,
    write_intraday_rows,
```

Append these tests to `tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run storage tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_storage.py -v
```

Expected: import failure for missing `intraday_path`, `write_intraday_rows`, or `read_intraday_rows`.

- [ ] **Step 3: Add intraday storage helpers**

In `market_watch/storage.py`, add this import near the existing `SNAPSHOT_FIELDS` import:

```python
from market_watch.intraday import INTRADAY_FIELDS
```

Add these functions below `read_snapshots_for_trade_date`:

```python
def intraday_path(
    intraday_dir: str | Path,
    trade_date: str,
    period: str = "1m",
) -> Path:
    return Path(intraday_dir) / f"{trade_date}-{period}.csv"


def write_intraday_rows(
    intraday_dir: str | Path,
    trade_date: str,
    records: Iterable[dict[str, Any]],
    period: str = "1m",
) -> Path:
    destination = intraday_path(intraday_dir, trade_date, period)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".tmp",
            newline="",
            encoding="utf-8",
        ) as temp_file:
            temp_name = temp_file.name
            writer = csv.DictWriter(
                temp_file,
                fieldnames=INTRADAY_FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(records)
        os.replace(temp_name, destination)
    except Exception:
        if temp_name is not None:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()
        raise

    return destination


def read_intraday_rows(
    intraday_dir: str | Path,
    trade_date: str,
    period: str = "1m",
) -> list[dict[str, str]]:
    path = intraday_path(intraday_dir, trade_date, period)
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
```

- [ ] **Step 4: Run storage tests and confirm pass**

Run:

```bash
python3 -m pytest tests/test_storage.py -v
```

Expected: all storage tests pass.

- [ ] **Step 5: Commit checkpoint**

Run:

```bash
git add market_watch/storage.py tests/test_storage.py
git commit -m "feat: add intraday csv replacement storage"
```

If there is no baseline `HEAD`, skip the commit command and record the skipped checkpoint.

---

### Task 4: Render Today JSON and Markdown

**Files:**
- Modify: `tests/test_render.py`
- Modify: `market_watch/render.py`

- [ ] **Step 1: Write failing render tests**

Update the import at the top of `tests/test_render.py` to include the new functions:

```python
from market_watch.render import (
    build_json_payload,
    build_today_json_payload,
    render_markdown,
    render_today_markdown,
)
```

Append these helper functions and tests to `tests/test_render.py`:

```python
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
    assert "## 1m 分钟明细" in markdown
    assert "协创数据" in markdown
    assert "2026-07-03 09:32:00" in markdown
    assert "## 给 ChatGPT 的分析请求" in markdown

    forbidden_words = ["买入", "卖出", "持仓", "止损", "止盈", "加仓", "减仓", "观望"]
    assert all(word not in markdown for word in forbidden_words)


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
```

- [ ] **Step 2: Run render tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: import failure for missing `build_today_json_payload` or `render_today_markdown`.

- [ ] **Step 3: Add render constants**

In `market_watch/render.py`, add these constants below `ERROR_COLUMNS`:

```python
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
    ("close_change_pct", "收盘涨跌幅"),
    ("total_volume", "成交量"),
    ("total_amount", "成交额"),
]

INTRADAY_ROW_COLUMNS = [
    ("timestamp", "时间"),
    ("code", "代码"),
    ("name", "名称"),
    ("open", "开盘"),
    ("high", "最高"),
    ("low", "最低"),
    ("close", "收盘"),
    ("volume", "成交量"),
    ("amount", "成交额"),
    ("average_price", "均价"),
]
```

- [ ] **Step 4: Add today JSON and Markdown functions**

Add these functions to `market_watch/render.py` below `render_markdown`:

```python
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
```

- [ ] **Step 5: Run render tests and confirm pass**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: all render tests pass.

- [ ] **Step 6: Commit checkpoint**

Run:

```bash
git add market_watch/render.py tests/test_render.py
git commit -m "feat: render intraday today outputs"
```

If there is no baseline `HEAD`, skip the commit command and record the skipped checkpoint.

---

### Task 5: Add Backfill Pipeline and CLI

**Files:**
- Modify: `tests/test_watch.py`
- Modify: `watch.py`

- [ ] **Step 1: Write failing CLI dispatch test**

Append this test to `tests/test_watch.py`:

```python
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
```

- [ ] **Step 2: Write failing end-to-end backfill tests**

Append these helpers and tests to `tests/test_watch.py`:

```python
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
```

- [ ] **Step 3: Run watch tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_watch.py -v
```

Expected: failures for missing `run_backfill_today`, missing `--backfill-today`, or missing intraday imports in `watch.py`.

- [ ] **Step 4: Add imports to watch.py**

Update the import section in `watch.py`:

```python
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
```

- [ ] **Step 5: Add intraday collection helpers**

Add these functions to `watch.py` below `collect_records`:

```python
def collect_intraday_records(
    config: dict,
    timestamp: str,
    trade_date: str,
    start: str,
    end: str,
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    errors: list[dict] = []
    runtime = config["runtime"]
    retry_count = runtime["retry_count"]
    slow_threshold_seconds = runtime["request_timeout_seconds"]

    for target in config["targets"].get("stocks", []):
        frame, fetch_errors = _fetch_intraday_with_retry(
            lambda target=target: fetch_stock_intraday(
                target["code"],
                start=start,
                end=end,
            ),
            stage="fetch_stock_intraday",
            asset_type="stock",
            target=target,
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        errors.extend(fetch_errors)
        if frame is not None:
            rows, row_errors = _normalize_intraday_target(
                frame,
                target,
                asset_type="stock",
                trade_date=trade_date,
                timestamp=timestamp,
            )
            records.extend(rows)
            errors.extend(row_errors)

    for target in config["targets"].get("indices", []):
        frame, fetch_errors = _fetch_intraday_with_retry(
            lambda target=target: fetch_index_intraday(
                target["code"],
                start=start,
                end=end,
            ),
            stage="fetch_index_intraday",
            asset_type="index",
            target=target,
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
        errors.extend(fetch_errors)
        if frame is not None:
            rows, row_errors = _normalize_intraday_target(
                frame,
                target,
                asset_type="index",
                trade_date=trade_date,
                timestamp=timestamp,
            )
            records.extend(rows)
            errors.extend(row_errors)

    return records, errors


def _normalize_intraday_target(
    frame: Any,
    target: dict,
    *,
    asset_type: str,
    trade_date: str,
    timestamp: str,
) -> tuple[list[dict], list[dict]]:
    try:
        rows = normalize_intraday_frame(
            frame,
            target,
            asset_type=asset_type,
            trade_date=trade_date,
        )
    except SourceDataError as exc:
        return [], [
            make_error(
                level="error",
                stage="normalize_intraday",
                code="INTRADAY_SOURCE_FIELD_MISSING",
                message=str(exc),
                target={"asset_type": asset_type, "code": target["code"]},
                timestamp=timestamp,
            )
        ]

    if not rows:
        return [], [
            make_error(
                level="warning",
                stage="normalize_intraday",
                code="INTRADAY_NO_ROWS",
                message=f"No intraday rows returned for {asset_type} {target['code']}",
                target={"asset_type": asset_type, "code": target["code"]},
                timestamp=timestamp,
            )
        ]

    return rows, []


def _fetch_intraday_with_retry(
    operation: Callable[[], Any],
    *,
    stage: str,
    asset_type: str,
    target: dict,
    timestamp: str,
    retry_count: int,
    slow_threshold_seconds: int,
) -> tuple[Any | None, list[dict]]:
    errors: list[dict] = []
    attempts = retry_count + 1

    for attempt in range(attempts):
        start_time = time.monotonic()
        try:
            result = operation()
        except SourceDataError as exc:
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="INTRADAY_SOURCE_FIELD_MISSING",
                    message=str(exc),
                    target={"asset_type": asset_type, "code": target["code"]},
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
                    target={"asset_type": asset_type, "code": target["code"]},
                    timestamp=timestamp,
                )
            ]

        elapsed = time.monotonic() - start_time
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
                    target={"asset_type": asset_type, "code": target["code"]},
                    timestamp=timestamp,
                )
            )
        return result, errors

    return None, errors
```

- [ ] **Step 6: Add run_backfill_today**

Add this function to `watch.py` below `run_once`:

```python
def run_backfill_today(config_path: str = "config.yaml") -> int:
    config = load_config(config_path)
    runtime = config["runtime"]
    storage = config["storage"]
    timestamp, trade_date = current_market_timestamp(runtime["market_timezone"])
    start, end = build_intraday_time_range(trade_date)
    time_range = {"start": start, "end": end}

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
```

- [ ] **Step 7: Add CLI argument and routing**

In `build_parser`, add:

```python
    parser.add_argument(
        "--backfill-today",
        action="store_true",
        help="Fetch today's one-minute intraday bars and write today outputs.",
    )
```

In `main`, route backfill before loop:

```python
        if args.backfill_today:
            return run_backfill_today(args.config)
        if args.loop:
            return run_loop(args.config, interval_override=args.interval)
        return run_once(args.config)
```

- [ ] **Step 8: Run watch tests and confirm pass**

Run:

```bash
python3 -m pytest tests/test_watch.py -v
```

Expected: all watch tests pass.

- [ ] **Step 9: Commit checkpoint**

Run:

```bash
git add watch.py tests/test_watch.py
git commit -m "feat: add intraday backfill cli"
```

If there is no baseline `HEAD`, skip the commit command and record the skipped checkpoint.

---

### Task 6: Update User Docs and Run Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-03-market-watch-intraday-backfill.md` during checkbox tracking only

- [ ] **Step 1: Update README with backfill usage**

Add this section to `README.md` after the loop instructions:

````markdown
## Backfill Today's Minute Data

```bash
python3 watch.py --backfill-today
```

This command fetches today's available one-minute bars for configured stocks and
indices. It is useful after market close or when the real-time loop was not
running earlier in the day. The data is stored separately from real-time
snapshots because minute bars are OHLCV records, not real-time quote snapshots.
````

Extend the output list in `README.md` to include:

```markdown
- `data/intraday/YYYY-MM-DD-1m.csv`: one-minute intraday bars for today's backfill.
- `outputs/today.md`: copy-paste friendly full-day minute data.
- `outputs/today.json`: structured full-day minute rows, summaries, and errors.
```

- [ ] **Step 2: Run the complete test suite**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Run compile verification**

Run:

```bash
python3 -m compileall watch.py market_watch tests
```

Expected: command exits 0 with no syntax errors.

- [ ] **Step 4: Scan implementation and outputs for advice language**

Run:

```bash
rg -n "买入|卖出|持仓|止损|止盈|加仓|减仓|观望|buy|sell|hold|stop-loss" watch.py market_watch tests README.md
```

Expected: either no matches, or matches only in explicit negative-boundary text such as "does not provide buy/sell rules" or tests that assert forbidden words are absent.

- [ ] **Step 5: Run a local mocked-free smoke command**

Run:

```bash
python3 watch.py --backfill-today
```

Expected: command writes `outputs/today.md`, `outputs/today.json`, and `data/intraday/<today>-1m.csv`. If the network source fails, the command still exits successfully when errors are rendered, and `outputs/today.json` contains `INTRADAY_SOURCE_FETCH_FAILED` entries.

- [ ] **Step 6: Check generated JSON shape**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("outputs/today.json").read_text(encoding="utf-8"))
print(sorted(payload.keys()))
print(payload["period"])
print(type(payload["rows"]).__name__)
print(type(payload["summary"]["items"]).__name__)
PY
```

Expected output includes:

```text
['errors', 'generated_at', 'period', 'rows', 'summary', 'time_range', 'trade_date']
1m
list
list
```

- [ ] **Step 7: Commit checkpoint**

Run:

```bash
git add README.md docs/superpowers/plans/2026-07-03-market-watch-intraday-backfill.md
git commit -m "docs: document intraday backfill"
```

If there is no baseline `HEAD`, skip the commit command and record the skipped checkpoint.

---

## Final Review Checklist

- [ ] `--backfill-today` does not call `append_snapshots` and does not write to `data/snapshots/YYYY-MM-DD.csv`.
- [ ] `--once` and `--loop` tests still pass without changing their output schema.
- [ ] `data/intraday/YYYY-MM-DD-1m.csv` is replaced on each backfill run rather than appended.
- [ ] `outputs/today.json` contains all normalized intraday rows.
- [ ] `outputs/today.md` contains full minute rows and objective summary.
- [ ] Error rows name failed target codes when individual stock or index fetches fail.
- [ ] Empty source data creates today outputs and a CSV header file.
- [ ] Rendered user-facing text remains data-only and contains no advice language.
