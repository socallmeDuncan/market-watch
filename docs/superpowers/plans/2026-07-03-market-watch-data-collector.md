# Market Watch Data Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python command-line market data collector that fetches configured A-share stocks and indices, normalizes records, stores daily CSV history, and renders latest Markdown/JSON data snapshots without trading advice.

**Architecture:** Implement a CSV-first pipeline with clear module boundaries: config validation, AKShare fetching, normalization, storage, objective summary, rendering, and CLI orchestration. Build `--once` first as the testable core, then wrap the same pipeline in `--loop` with market-hours gating and clean shutdown.

**Tech Stack:** Python 3.11+, AKShare, pandas, PyYAML, tabulate, pytest, standard-library `csv`, `json`, `datetime`, `zoneinfo`, `argparse`, and `pathlib`.

---

## Source Spec

Implement from `docs/superpowers/specs/2026-07-03-market-watch-data-collector-design.md`.

Current workspace note: this directory is not currently a git repository. Commit steps below are included for execution in a git-enabled workspace. If `.git` is absent, skip the commit command and record the skipped checkpoint in the execution notes.

## File Structure

Create and maintain these files:

- `requirements.txt`: runtime and test dependencies.
- `README.md`: install, run, and safety boundary instructions.
- `config.yaml`: default collector configuration.
- `watch.py`: CLI entry point for `--once` and `--loop`.
- `market_watch/__init__.py`: package marker.
- `market_watch/config.py`: YAML loading, defaults, and validation.
- `market_watch/fetchers.py`: AKShare fetch wrappers and target filtering.
- `market_watch/normalize.py`: source field mapping, parsing, normalized rows, and structured errors.
- `market_watch/storage.py`: daily CSV append, history reads, atomic file writes.
- `market_watch/summary.py`: fact-only recent-window statistics.
- `market_watch/render.py`: Markdown and JSON payload rendering.
- `tests/conftest.py`: shared pytest fixtures and temporary config helpers.
- `tests/test_config.py`: config validation tests.
- `tests/test_normalize.py`: field mapping and missing-value tests.
- `tests/test_storage.py`: CSV append, header, history, and atomic write tests.
- `tests/test_summary.py`: recent-window objective summary tests.
- `tests/test_render.py`: Markdown and JSON rendering tests.
- `tests/test_fetchers.py`: AKShare wrapper tests using monkeypatched providers.
- `tests/test_watch.py`: `--once`, loop scheduling, and market-hours gate tests.

Do not add strategy thresholds, buy/sell advice, status labels, or trading-rule logic.

---

### Task 1: Scaffold Project Files

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `config.yaml`
- Create: `watch.py`
- Create: `market_watch/__init__.py`
- Create: `market_watch/config.py`
- Create: `market_watch/fetchers.py`
- Create: `market_watch/normalize.py`
- Create: `market_watch/storage.py`
- Create: `market_watch/summary.py`
- Create: `market_watch/render.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create dependency file**

Write `requirements.txt`:

```text
akshare
pandas
pyyaml
tabulate
pytest
```

- [ ] **Step 2: Create default configuration**

Write `config.yaml`:

```yaml
targets:
  stocks:
    - code: "300857"
      name: "协创数据"
      role: "primary"
    - code: "300475"
      name: "香农芯创"
      role: "compare"
  indices:
    - code: "399006"
      name: "创业板指"
      role: "context"
    - code: "399001"
      name: "深证成指"
      role: "context"
    - code: "000001"
      name: "上证指数"
      role: "context"

runtime:
  interval_seconds: 60
  market_hours_only: true
  market_timezone: "Asia/Shanghai"
  history_windows_minutes: [15, 30, 60]
  request_timeout_seconds: 15
  retry_count: 1

storage:
  snapshot_dir: "data/snapshots"
  latest_markdown: "outputs/latest.md"
  latest_json: "outputs/latest.json"

source:
  provider: "akshare"
  stock_source: "eastmoney"
  index_symbol: "沪深重要指数"
```

- [ ] **Step 3: Create README**

Write `README.md`:

```markdown
# Market Watch

Lightweight A-share intraday data collector.

The tool collects configured stock and index quotes, stores daily CSV snapshots,
and writes latest Markdown/JSON outputs for analysis. It does not make trading
decisions, produce strategy labels, place orders, or encode buy/sell rules.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Once

```bash
python watch.py --once
```

`--once` always attempts one sample, even outside the market-hours gate. Use it
for manual checks, smoke tests, and debugging.

## Run In Loop

```bash
python watch.py --loop --interval 60
```

`--loop` respects `runtime.market_hours_only` and skips scheduled samples outside
the configured A-share trading sessions.

## Outputs

- `data/snapshots/YYYY-MM-DD.csv`: normalized historical records.
- `outputs/latest.md`: latest copy-paste friendly market data snapshot.
- `outputs/latest.json`: structured current records, history summaries, and errors.

## Boundary

This project only collects, stores, and summarizes objective market data. It
does not provide buy, sell, hold, add, reduce, stop-loss, confirmation,
breakdown, or other strategy decisions.
```

- [ ] **Step 4: Create package and skeleton modules**

Write these files with the exact content shown:

`market_watch/__init__.py`

```python
"""Market Watch data collector package."""
```

`market_watch/config.py`

```python
"""Configuration loading and validation."""
```

`market_watch/fetchers.py`

```python
"""AKShare fetch wrappers."""
```

`market_watch/normalize.py`

```python
"""Normalize AKShare rows into the project schema."""
```

`market_watch/storage.py`

```python
"""CSV storage and atomic output helpers."""
```

`market_watch/summary.py`

```python
"""Objective history summaries."""
```

`market_watch/render.py`

```python
"""Markdown and JSON rendering."""
```

`watch.py`

```python
"""Command-line entry point for Market Watch."""


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create shared pytest helper file**

Write `tests/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_config_dict() -> dict:
    return {
        "targets": {
            "stocks": [
                {"code": "300857", "name": "协创数据", "role": "primary"},
                {"code": "300475", "name": "香农芯创", "role": "compare"},
            ],
            "indices": [
                {"code": "399006", "name": "创业板指", "role": "context"},
                {"code": "399001", "name": "深证成指", "role": "context"},
            ],
        },
        "runtime": {
            "interval_seconds": 60,
            "market_hours_only": True,
            "market_timezone": "Asia/Shanghai",
            "history_windows_minutes": [15, 30, 60],
            "request_timeout_seconds": 15,
            "retry_count": 1,
        },
        "storage": {
            "snapshot_dir": "data/snapshots",
            "latest_markdown": "outputs/latest.md",
            "latest_json": "outputs/latest.json",
        },
        "source": {
            "provider": "akshare",
            "stock_source": "eastmoney",
            "index_symbol": "沪深重要指数",
        },
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config_dict: dict) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8")
    return path
```

- [ ] **Step 6: Run scaffold sanity check**

Run:

```bash
python -m compileall watch.py market_watch
```

Expected: command exits 0 and reports compiled files.

- [ ] **Step 7: Commit scaffold checkpoint**

Run only if `.git` exists:

```bash
git add README.md requirements.txt config.yaml watch.py market_watch tests/conftest.py
git commit -m "chore: scaffold market watch collector"
```

Expected: commit succeeds.

---

### Task 2: Implement Config Loading And Validation

**Files:**
- Modify: `market_watch/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Write `tests/test_config.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from market_watch.config import ConfigError, load_config, validate_config


def write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_config_applies_defaults(tmp_path: Path, sample_config_dict: dict) -> None:
    del sample_config_dict["runtime"]["market_timezone"]
    del sample_config_dict["runtime"]["request_timeout_seconds"]
    path = write_yaml(tmp_path / "config.yaml", sample_config_dict)

    config = load_config(path)

    assert config["runtime"]["market_timezone"] == "Asia/Shanghai"
    assert config["runtime"]["request_timeout_seconds"] == 15
    assert config["runtime"]["retry_count"] == 1


def test_validate_config_rejects_duplicate_asset_code(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"].append(
        {"code": "300857", "name": "重复协创", "role": "compare"}
    )

    with pytest.raises(ConfigError, match="Duplicate target"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_invalid_role(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"][0]["role"] = "leader"

    with pytest.raises(ConfigError, match="Invalid role"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_missing_targets(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"] = []
    sample_config_dict["targets"]["indices"] = []

    with pytest.raises(ConfigError, match="At least one target"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_non_positive_interval(sample_config_dict: dict) -> None:
    sample_config_dict["runtime"]["interval_seconds"] = 0

    with pytest.raises(ConfigError, match="interval_seconds"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_missing_index_symbol(sample_config_dict: dict) -> None:
    sample_config_dict["source"]["index_symbol"] = ""

    with pytest.raises(ConfigError, match="index_symbol"):
        validate_config(sample_config_dict)


def test_load_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Config file not found"):
        load_config(tmp_path / "missing.yaml")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `ConfigError`, `load_config`, and `validate_config` are not defined.

- [ ] **Step 3: Implement config module**

Replace `market_watch/config.py` with:

```python
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


VALID_ROLES = {"primary", "compare", "context"}
DEFAULT_CONFIG: dict[str, Any] = {
    "targets": {"stocks": [], "indices": []},
    "runtime": {
        "interval_seconds": 60,
        "market_hours_only": True,
        "market_timezone": "Asia/Shanghai",
        "history_windows_minutes": [15, 30, 60],
        "request_timeout_seconds": 15,
        "retry_count": 1,
    },
    "storage": {
        "snapshot_dir": "data/snapshots",
        "latest_markdown": "outputs/latest.md",
        "latest_json": "outputs/latest.json",
    },
    "source": {
        "provider": "akshare",
        "stock_source": "eastmoney",
        "index_symbol": "沪深重要指数",
    },
}


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ConfigError("Config root must be a mapping")
    config = merge_defaults(loaded)
    validate_config(config)
    return config


def merge_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    for section, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(section), dict):
            merged[section].update(value)
        else:
            merged[section] = value
    return merged


def validate_config(config: dict[str, Any]) -> None:
    targets = _require_mapping(config, "targets")
    stocks = _require_list(targets, "stocks")
    indices = _require_list(targets, "indices")
    if not stocks and not indices:
        raise ConfigError("At least one target must be configured")

    seen: set[tuple[str, str]] = set()
    for asset_type, items in [("stock", stocks), ("index", indices)]:
        for item in items:
            if not isinstance(item, dict):
                raise ConfigError(f"{asset_type} target must be a mapping")
            code = _require_non_empty_string(item, "code")
            _require_non_empty_string(item, "name")
            role = _require_non_empty_string(item, "role")
            if role not in VALID_ROLES:
                raise ConfigError(f"Invalid role for {asset_type} {code}: {role}")
            key = (asset_type, code)
            if key in seen:
                raise ConfigError(f"Duplicate target: {asset_type} {code}")
            seen.add(key)

    runtime = _require_mapping(config, "runtime")
    _require_positive_int(runtime, "interval_seconds")
    _require_positive_int(runtime, "request_timeout_seconds")
    _require_non_negative_int(runtime, "retry_count")
    _require_non_empty_string(runtime, "market_timezone")
    windows = _require_list(runtime, "history_windows_minutes")
    if not windows or not all(isinstance(value, int) and value > 0 for value in windows):
        raise ConfigError("history_windows_minutes must be a non-empty list of positive integers")

    storage = _require_mapping(config, "storage")
    _require_non_empty_string(storage, "snapshot_dir")
    _require_non_empty_string(storage, "latest_markdown")
    _require_non_empty_string(storage, "latest_json")

    source = _require_mapping(config, "source")
    provider = _require_non_empty_string(source, "provider")
    if provider != "akshare":
        raise ConfigError("source.provider must be akshare")
    if indices:
        _require_non_empty_string(source, "index_symbol")


def _require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a mapping")
    return value


def _require_list(config: dict[str, Any], key: str) -> list[Any]:
    value = config.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"{key} must be a list")
    return value


def _require_non_empty_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value


def _require_positive_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _require_non_negative_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or value < 0:
        raise ConfigError(f"{key} must be a non-negative integer")
    return value
```

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit config checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/config.py tests/test_config.py
git commit -m "feat: validate collector config"
```

Expected: commit succeeds.

---

### Task 3: Implement Normalization And Structured Errors

**Files:**
- Modify: `market_watch/normalize.py`
- Create: `tests/test_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

Write `tests/test_normalize.py`:

```python
from __future__ import annotations

import math

import pandas as pd

from market_watch.normalize import (
    SNAPSHOT_FIELDS,
    make_error,
    normalize_index_frame,
    normalize_stock_frame,
)


def test_normalize_stock_frame_maps_akshare_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "300857",
                "名称": "协创数据",
                "最新价": 295.2,
                "涨跌幅": 0.55,
                "涨跌额": 1.61,
                "成交量": 1234567,
                "成交额": 1850000000,
                "振幅": 2.32,
                "最高": 298.8,
                "最低": 292.0,
                "今开": 298.0,
                "昨收": 293.59,
                "换手率": 8.1,
                "涨速": 0.22,
                "5分钟涨跌": 0.8,
            }
        ]
    )
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert list(records[0].keys()) == SNAPSHOT_FIELDS
    assert records[0]["asset_type"] == "stock"
    assert records[0]["code"] == "300857"
    assert records[0]["role"] == "primary"
    assert records[0]["price"] == 295.2
    assert records[0]["change_pct"] == 0.55
    assert records[0]["turnover_rate"] == 8.1
    assert records[0]["source"] == "akshare_em"


def test_normalize_index_frame_missing_stock_only_fields_are_none() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "399006",
                "名称": "创业板指",
                "最新价": 2310.2,
                "涨跌幅": 0.4,
                "涨跌额": 9.2,
                "成交量": 123456789,
                "成交额": 220000000000,
                "振幅": 1.52,
                "最高": 2320.0,
                "最低": 2285.0,
                "今开": 2298.0,
                "昨收": 2301.0,
            }
        ]
    )
    targets = [{"code": "399006", "name": "创业板指", "role": "context"}]

    records, errors = normalize_index_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors == []
    assert records[0]["asset_type"] == "index"
    assert records[0]["turnover_rate"] is None
    assert records[0]["speed"] is None
    assert records[0]["five_min_change"] is None


def test_normalize_reports_missing_target() -> None:
    frame = pd.DataFrame([{"代码": "300475", "名称": "香农芯创", "最新价": 252.3}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors[0]["level"] == "warning"
    assert errors[0]["stage"] == "normalize_stock"
    assert errors[0]["code"] == "TARGET_MISSING"
    assert errors[0]["target"] == {"asset_type": "stock", "code": "300857"}


def test_invalid_numeric_required_field_skips_record() -> None:
    frame = pd.DataFrame([{"代码": "300857", "名称": "协创数据", "最新价": "-"}])
    targets = [{"code": "300857", "name": "协创数据", "role": "primary"}]

    records, errors = normalize_stock_frame(
        frame,
        targets,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors[0]["level"] == "error"
    assert errors[0]["code"] == "INVALID_REQUIRED_FIELD"


def test_make_error_shape() -> None:
    error = make_error(
        level="warning",
        stage="fetch_indices",
        code="SOURCE_TIMEOUT",
        message="timed out",
        target=None,
        timestamp="2026-07-03 10:42:30",
    )

    assert error == {
        "level": "warning",
        "stage": "fetch_indices",
        "code": "SOURCE_TIMEOUT",
        "message": "timed out",
        "target": None,
        "timestamp": "2026-07-03 10:42:30",
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_normalize.py -v
```

Expected: FAIL because normalization functions are not defined.

- [ ] **Step 3: Implement normalize module**

Replace `market_watch/normalize.py` with:

```python
from __future__ import annotations

from typing import Any

import pandas as pd


SNAPSHOT_FIELDS = [
    "timestamp",
    "trade_date",
    "asset_type",
    "code",
    "name",
    "role",
    "price",
    "change_pct",
    "change_amount",
    "open",
    "high",
    "low",
    "prev_close",
    "volume",
    "amount",
    "amplitude",
    "turnover_rate",
    "speed",
    "five_min_change",
    "source",
]

COMMON_FIELD_MAP = {
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change_amount": "涨跌额",
    "open": "今开",
    "high": "最高",
    "low": "最低",
    "prev_close": "昨收",
    "volume": "成交量",
    "amount": "成交额",
    "amplitude": "振幅",
}

STOCK_ONLY_FIELD_MAP = {
    "turnover_rate": "换手率",
    "speed": "涨速",
    "five_min_change": "5分钟涨跌",
}

REQUIRED_NUMERIC_FIELDS = {"price"}


def make_error(
    *,
    level: str,
    stage: str,
    code: str,
    message: str,
    target: dict[str, Any] | None,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "level": level,
        "stage": stage,
        "code": code,
        "message": message,
        "target": target,
        "timestamp": timestamp,
    }


def normalize_stock_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _normalize_frame(
        frame,
        targets,
        asset_type="stock",
        timestamp=timestamp,
        trade_date=trade_date,
        stage="normalize_stock",
        optional_map=STOCK_ONLY_FIELD_MAP,
    )


def normalize_index_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    timestamp: str,
    trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _normalize_frame(
        frame,
        targets,
        asset_type="index",
        timestamp=timestamp,
        trade_date=trade_date,
        stage="normalize_index",
        optional_map={},
    )


def _normalize_frame(
    frame: pd.DataFrame,
    targets: list[dict[str, Any]],
    *,
    asset_type: str,
    timestamp: str,
    trade_date: str,
    stage: str,
    optional_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if "代码" not in frame.columns:
        return records, [
            make_error(
                level="error",
                stage=stage,
                code="SOURCE_FIELD_MISSING",
                message="Source frame is missing column: 代码",
                target=None,
                timestamp=timestamp,
            )
        ]

    working = frame.copy()
    working["代码"] = working["代码"].astype(str)

    for target in targets:
        code = str(target["code"])
        matches = working[working["代码"] == code]
        target_ref = {"asset_type": asset_type, "code": code}
        if matches.empty:
            errors.append(
                make_error(
                    level="warning",
                    stage=stage,
                    code="TARGET_MISSING",
                    message=f"Configured target not found in source data: {asset_type} {code}",
                    target=target_ref,
                    timestamp=timestamp,
                )
            )
            continue

        row = matches.iloc[0].to_dict()
        record, row_errors = _build_record(
            row,
            target,
            asset_type=asset_type,
            timestamp=timestamp,
            trade_date=trade_date,
            stage=stage,
        )
        errors.extend(row_errors)
        if record is not None:
            for field, source_field in optional_map.items():
                record[field] = _parse_optional_number(row.get(source_field))
            records.append(record)

    return records, errors


def _build_record(
    row: dict[str, Any],
    target: dict[str, Any],
    *,
    asset_type: str,
    timestamp: str,
    trade_date: str,
    stage: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    code = str(target["code"])
    record: dict[str, Any] = {
        "timestamp": timestamp,
        "trade_date": trade_date,
        "asset_type": asset_type,
        "code": code,
        "name": str(target["name"]),
        "role": str(target["role"]),
        "source": "akshare_em",
    }

    for field, source_field in COMMON_FIELD_MAP.items():
        value = _parse_optional_number(row.get(source_field))
        if field in REQUIRED_NUMERIC_FIELDS and value is None:
            errors.append(
                make_error(
                    level="error",
                    stage=stage,
                    code="INVALID_REQUIRED_FIELD",
                    message=f"Invalid required numeric field {source_field} for {asset_type} {code}",
                    target={"asset_type": asset_type, "code": code},
                    timestamp=timestamp,
                )
            )
            return None, errors
        record[field] = value

    record["turnover_rate"] = None
    record["speed"] = None
    record["five_min_change"] = None
    return {field: record.get(field) for field in SNAPSHOT_FIELDS}, errors


def _parse_optional_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped in {"-", "--"}:
            return None
        value = stripped.replace(",", "")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed.is_integer():
        return int(parsed)
    return parsed
```

- [ ] **Step 4: Run normalization tests**

Run:

```bash
pytest tests/test_normalize.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit normalization checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/normalize.py tests/test_normalize.py
git commit -m "feat: normalize akshare quote rows"
```

Expected: commit succeeds.

---

### Task 4: Implement CSV Storage And Atomic Writes

**Files:**
- Modify: `market_watch/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Write `tests/test_storage.py`:

```python
from __future__ import annotations

import csv
import json
from pathlib import Path

from market_watch.normalize import SNAPSHOT_FIELDS
from market_watch.storage import (
    append_snapshots,
    atomic_write_json,
    atomic_write_text,
    read_snapshots_for_trade_date,
    snapshot_path,
)


def sample_record(code: str = "300857", timestamp: str = "2026-07-03 10:42:30") -> dict:
    return {
        "timestamp": timestamp,
        "trade_date": "2026-07-03",
        "asset_type": "stock",
        "code": code,
        "name": "协创数据",
        "role": "primary",
        "price": 295.2,
        "change_pct": 0.55,
        "change_amount": 1.61,
        "open": 298.0,
        "high": 298.8,
        "low": 292.0,
        "prev_close": 293.59,
        "volume": 1234567,
        "amount": 1850000000,
        "amplitude": 2.32,
        "turnover_rate": 8.1,
        "speed": 0.22,
        "five_min_change": 0.8,
        "source": "akshare_em",
    }


def test_snapshot_path_uses_trade_date(tmp_path: Path) -> None:
    assert snapshot_path(tmp_path, "2026-07-03") == tmp_path / "2026-07-03.csv"


def test_append_snapshots_writes_single_header(tmp_path: Path) -> None:
    record = sample_record()

    append_snapshots(tmp_path, "2026-07-03", [record])
    append_snapshots(tmp_path, "2026-07-03", [sample_record(code="300475")])

    rows = (tmp_path / "2026-07-03.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].split(",") == SNAPSHOT_FIELDS
    assert len(rows) == 3


def test_read_snapshots_for_trade_date_returns_dict_rows(tmp_path: Path) -> None:
    append_snapshots(tmp_path, "2026-07-03", [sample_record()])

    rows = read_snapshots_for_trade_date(tmp_path, "2026-07-03")

    assert rows[0]["code"] == "300857"
    assert rows[0]["price"] == "295.2"


def test_read_missing_trade_date_returns_empty_list(tmp_path: Path) -> None:
    assert read_snapshots_for_trade_date(tmp_path, "2026-07-03") == []


def test_atomic_write_text(tmp_path: Path) -> None:
    path = tmp_path / "outputs" / "latest.md"

    atomic_write_text(path, "hello")

    assert path.read_text(encoding="utf-8") == "hello"
    assert not list(path.parent.glob("*.tmp"))


def test_atomic_write_json(tmp_path: Path) -> None:
    path = tmp_path / "outputs" / "latest.json"

    atomic_write_json(path, {"ok": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_storage.py -v
```

Expected: FAIL because storage functions are not defined.

- [ ] **Step 3: Implement storage module**

Replace `market_watch/storage.py` with:

```python
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from market_watch.normalize import SNAPSHOT_FIELDS


def snapshot_path(snapshot_dir: str | Path, trade_date: str) -> Path:
    return Path(snapshot_dir) / f"{trade_date}.csv"


def append_snapshots(
    snapshot_dir: str | Path,
    trade_date: str,
    records: list[dict[str, Any]],
) -> Path:
    path = snapshot_path(snapshot_dir, trade_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        if not file_exists:
            writer.writeheader()
        for record in records:
            writer.writerow({field: _csv_value(record.get(field)) for field in SNAPSHOT_FIELDS})
    return path


def read_snapshots_for_trade_date(snapshot_dir: str | Path, trade_date: str) -> list[dict[str, str]]:
    path = snapshot_path(snapshot_dir, trade_date)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_text(path: str | Path, content: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, output_path)


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    atomic_write_text(path, content + "\n")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value
```

- [ ] **Step 4: Run storage tests**

Run:

```bash
pytest tests/test_storage.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit storage checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/storage.py tests/test_storage.py
git commit -m "feat: persist daily snapshot csv files"
```

Expected: commit succeeds.

---

### Task 5: Implement Objective History Summary

**Files:**
- Modify: `market_watch/summary.py`
- Create: `tests/test_summary.py`

**MVP summary contract:** `summarize_history()` only emits items for asset/window
pairs that have at least one stored sample in the requested time range. Current
target absences are represented by structured `errors`, not by empty
`sample_count: 0` summary rows.

- [ ] **Step 1: Write failing summary tests**

Write `tests/test_summary.py`:

```python
from __future__ import annotations

from market_watch.summary import summarize_history


def row(code: str, timestamp: str, price: str, amount: str = "1000") -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "trade_date": "2026-07-03",
        "asset_type": "stock",
        "code": code,
        "name": "协创数据" if code == "300857" else "香农芯创",
        "role": "primary" if code == "300857" else "compare",
        "price": price,
        "change_pct": "0.5",
        "change_amount": "1.0",
        "open": "290",
        "high": price,
        "low": price,
        "prev_close": "289",
        "volume": "100",
        "amount": amount,
        "amplitude": "1.2",
        "turnover_rate": "8.1",
        "speed": "0.22",
        "five_min_change": "0.8",
        "source": "akshare_em",
    }


def test_summarize_history_filters_by_window() -> None:
    rows = [
        row("300857", "2026-07-03 10:00:00", "290"),
        row("300857", "2026-07-03 10:20:00", "292"),
        row("300857", "2026-07-03 10:30:00", "296"),
        row("300857", "2026-07-03 10:42:30", "295.2", "1850000000"),
    ]

    result = summarize_history(
        rows,
        windows_minutes=[15, 30],
        latest_timestamp="2026-07-03 10:42:30",
    )

    items = {(item["code"], item["window_minutes"]): item for item in result["items"]}
    assert items[("300857", 15)]["sample_count"] == 2
    assert items[("300857", 15)]["first_price"] == 296
    assert items[("300857", 15)]["last_price"] == 295.2
    assert items[("300857", 30)]["sample_count"] == 3
    assert items[("300857", 30)]["window_high"] == 296
    assert items[("300857", 30)]["window_low"] == 292
    assert items[("300857", 30)]["latest_amount"] == 1850000000


def test_summarize_history_includes_each_code_and_window() -> None:
    rows = [
        row("300857", "2026-07-03 10:30:00", "296"),
        row("300475", "2026-07-03 10:30:00", "252"),
    ]

    result = summarize_history(
        rows,
        windows_minutes=[60],
        latest_timestamp="2026-07-03 10:42:30",
    )

    assert [(item["code"], item["window_minutes"]) for item in result["items"]] == [
        ("300857", 60),
        ("300475", 60),
    ]


def test_summarize_history_handles_empty_rows() -> None:
    result = summarize_history([], windows_minutes=[15], latest_timestamp="2026-07-03 10:42:30")

    assert result == {"windows_minutes": [15], "items": []}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_summary.py -v
```

Expected: FAIL because `summarize_history` is not defined.

- [ ] **Step 3: Implement summary module**

Replace `market_watch/summary.py` with:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def summarize_history(
    rows: list[dict[str, Any]],
    *,
    windows_minutes: list[int],
    latest_timestamp: str,
) -> dict[str, Any]:
    latest_dt = datetime.strptime(latest_timestamp, TIMESTAMP_FORMAT)
    parsed_rows = [_parse_row(row) for row in rows]
    parsed_rows = [row for row in parsed_rows if row is not None]

    items: list[dict[str, Any]] = []
    keys = _ordered_asset_keys(parsed_rows)
    for key in keys:
        asset_rows = [row for row in parsed_rows if _asset_key(row) == key]
        for window in windows_minutes:
            start_dt = latest_dt - timedelta(minutes=window)
            window_rows = [row for row in asset_rows if row["_timestamp_dt"] >= start_dt]
            if window_rows:
                items.append(_summarize_window(window_rows, window))
    return {"windows_minutes": windows_minutes, "items": items}


def _parse_row(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        timestamp_dt = datetime.strptime(str(row["timestamp"]), TIMESTAMP_FORMAT)
    except (KeyError, TypeError, ValueError):
        return None
    parsed = dict(row)
    parsed["_timestamp_dt"] = timestamp_dt
    parsed["_price"] = _to_float(row.get("price"))
    parsed["_amount"] = _to_float(row.get("amount"))
    if parsed["_price"] is None:
        return None
    return parsed


def _ordered_asset_keys(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    keys: list[tuple[str, str]] = []
    for row in rows:
        key = _asset_key(row)
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _asset_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("asset_type", "")), str(row.get("code", "")))


def _summarize_window(rows: list[dict[str, Any]], window_minutes: int) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: row["_timestamp_dt"])
    first = rows[0]
    last = rows[-1]
    prices = [row["_price"] for row in rows if row["_price"] is not None]
    first_price = first["_price"]
    last_price = last["_price"]
    price_change = _round_number(last_price - first_price)
    price_change_pct = None
    if first_price:
        price_change_pct = _round_number((last_price - first_price) / first_price * 100)
    return {
        "code": str(last.get("code")),
        "name": str(last.get("name")),
        "asset_type": str(last.get("asset_type")),
        "window_minutes": window_minutes,
        "sample_count": len(rows),
        "first_timestamp": str(first.get("timestamp")),
        "last_timestamp": str(last.get("timestamp")),
        "first_price": _round_number(first_price),
        "last_price": _round_number(last_price),
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "window_high": _round_number(max(prices)),
        "window_low": _round_number(min(prices)),
        "latest_amount": _round_number(last["_amount"]) if last["_amount"] is not None else None,
    }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        value = stripped.replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_number(value: float | None) -> float | int | None:
    if value is None:
        return None
    rounded = round(value, 4)
    if float(rounded).is_integer():
        return int(rounded)
    return rounded
```

- [ ] **Step 4: Run summary tests**

Run:

```bash
pytest tests/test_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit summary checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/summary.py tests/test_summary.py
git commit -m "feat: summarize recent quote history"
```

Expected: commit succeeds.

---

### Task 6: Implement Markdown And JSON Rendering

**Files:**
- Modify: `market_watch/render.py`
- Create: `tests/test_render.py`

- [ ] **Step 1: Write failing render tests**

Write `tests/test_render.py`:

```python
from __future__ import annotations

from market_watch.render import build_json_payload, render_markdown


def stock_record() -> dict:
    return {
        "timestamp": "2026-07-03 10:42:30",
        "trade_date": "2026-07-03",
        "asset_type": "stock",
        "code": "300857",
        "name": "协创数据",
        "role": "primary",
        "price": 295.2,
        "change_pct": 0.55,
        "change_amount": 1.61,
        "open": 298.0,
        "high": 298.8,
        "low": 292.0,
        "prev_close": 293.59,
        "volume": 1234567,
        "amount": 1850000000,
        "amplitude": 2.32,
        "turnover_rate": 8.1,
        "speed": 0.22,
        "five_min_change": 0.8,
        "source": "akshare_em",
    }


def index_record() -> dict:
    record = stock_record()
    record.update(
        {
            "asset_type": "index",
            "code": "399006",
            "name": "创业板指",
            "role": "context",
            "turnover_rate": None,
            "speed": None,
            "five_min_change": None,
        }
    )
    return record


def summary_payload() -> dict:
    return {
        "windows_minutes": [15],
        "items": [
            {
                "code": "300857",
                "name": "协创数据",
                "asset_type": "stock",
                "window_minutes": 15,
                "sample_count": 2,
                "first_timestamp": "2026-07-03 10:30:00",
                "last_timestamp": "2026-07-03 10:42:30",
                "first_price": 296,
                "last_price": 295.2,
                "price_change": -0.8,
                "price_change_pct": -0.2703,
                "window_high": 296,
                "window_low": 295.2,
                "latest_amount": 1850000000,
            }
        ],
    }


def test_build_json_payload_groups_current_records() -> None:
    payload = build_json_payload(
        timestamp="2026-07-03 10:42:30",
        records=[stock_record(), index_record()],
        history_summary=summary_payload(),
        errors=[],
    )

    assert payload["timestamp"] == "2026-07-03 10:42:30"
    assert payload["current"]["stocks"][0]["code"] == "300857"
    assert payload["current"]["indices"][0]["code"] == "399006"
    assert payload["history_summary"]["items"][0]["sample_count"] == 2
    assert payload["errors"] == []


def test_render_markdown_contains_tables_and_no_trading_advice() -> None:
    markdown = render_markdown(
        timestamp="2026-07-03 10:42:30",
        records=[stock_record(), index_record()],
        history_summary=summary_payload(),
        errors=[],
    )

    assert "# 盘中行情数据快照" in markdown
    assert "协创数据" in markdown
    assert "创业板指" in markdown
    assert "最近 15 分钟客观统计" in markdown
    assert "不要假设脚本内置任何交易标准" in markdown
    forbidden = ["买入", "卖出", "加仓", "减仓", "止损", "右侧确认"]
    assert all(word not in markdown for word in forbidden)


def test_render_markdown_displays_missing_values_as_dash() -> None:
    record = index_record()
    record["amount"] = None

    markdown = render_markdown(
        timestamp="2026-07-03 10:42:30",
        records=[record],
        history_summary={"windows_minutes": [15], "items": []},
        errors=[],
    )

    assert "| 399006 | 创业板指 |" in markdown
    assert " - " in markdown or "| - |" in markdown


def test_render_markdown_uses_dynamic_history_window_title() -> None:
    markdown = render_markdown(
        timestamp="2026-07-03 10:42:30",
        records=[],
        history_summary={"windows_minutes": [5, 15], "items": []},
        errors=[],
    )

    assert "## 最近 5 / 15 分钟客观统计" in markdown


def test_render_markdown_includes_errors() -> None:
    markdown = render_markdown(
        timestamp="2026-07-03 10:42:30",
        records=[],
        history_summary={"windows_minutes": [15], "items": []},
        errors=[
            {
                "level": "warning",
                "stage": "fetch_indices",
                "code": "SOURCE_TIMEOUT",
                "message": "timed out",
                "target": None,
                "timestamp": "2026-07-03 10:42:30",
            }
        ],
    )

    assert "## 数据警告" in markdown
    assert "SOURCE_TIMEOUT" in markdown
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_render.py -v
```

Expected: FAIL because render functions are not defined.

- [ ] **Step 3: Implement render module**

Replace `market_watch/render.py` with:

```python
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
    ("amount", "成交额"),
    ("turnover_rate", "换手率"),
    ("speed", "涨速"),
    ("five_min_change", "5分钟涨跌"),
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


def build_json_payload(
    *,
    timestamp: str,
    records: list[dict[str, Any]],
    history_summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "current": {
            "stocks": [record for record in records if record.get("asset_type") == "stock"],
            "indices": [record for record in records if record.get("asset_type") == "index"],
        },
        "history_summary": history_summary,
        "errors": errors,
    }


def render_markdown(
    *,
    timestamp: str,
    records: list[dict[str, Any]],
    history_summary: dict[str, Any],
    errors: list[dict[str, Any]],
) -> str:
    stocks = [record for record in records if record.get("asset_type") == "stock"]
    indices = [record for record in records if record.get("asset_type") == "index"]
    lines: list[str] = [
        "# 盘中行情数据快照",
        "",
        f"时间：{timestamp}",
        "",
        "## 当前个股行情",
        "",
        _records_table(stocks, STOCK_COLUMNS),
        "",
        "## 当前指数行情",
        "",
        _records_table(indices, INDEX_COLUMNS),
        "",
        f"## 最近 {_window_title(history_summary.get('windows_minutes', []))} 分钟客观统计",
        "",
        _summary_table(history_summary.get("items", [])),
    ]
    if errors:
        lines.extend(["", "## 数据警告", ""])
        for error in errors:
            lines.append(f"- [{error.get('level')}] {error.get('stage')} {error.get('code')}: {error.get('message')}")
    lines.extend(
        [
            "",
            "## 给 ChatGPT 的分析请求",
            "",
            "请基于以上客观行情数据，描述当前标的和相关指数的走势变化、",
            "相对强弱、波动范围、成交活跃度变化，以及还缺少哪些数据。",
            "不要假设脚本内置任何交易标准。",
            "",
        ]
    )
    return "\n".join(lines)


def _window_title(windows_minutes: list[int]) -> str:
    if not windows_minutes:
        return "历史"
    return " / ".join(str(window) for window in windows_minutes)


def _records_table(records: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not records:
        return "未获取到数据。"
    rows = []
    for record in records:
        rows.append({label: _display(record.get(field)) for field, label in columns})
    return pd.DataFrame(rows).to_markdown(index=False)


def _summary_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无足够历史数据。"
    rows = []
    for item in items:
        row = {}
        for field, label in SUMMARY_COLUMNS:
            value = item.get(field)
            if field == "window_minutes" and value is not None:
                value = f"{value}m"
            row[label] = _display(value)
        rows.append(row)
    return pd.DataFrame(rows).to_markdown(index=False)


def _display(value: Any) -> Any:
    if value is None or value == "":
        return "-"
    return value
```

- [ ] **Step 4: Run render tests**

Run:

```bash
pytest tests/test_render.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit render checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/render.py tests/test_render.py
git commit -m "feat: render market data outputs"
```

Expected: commit succeeds.

---

### Task 7: Implement AKShare Fetch Wrappers

**Files:**
- Modify: `market_watch/fetchers.py`
- Create: `tests/test_fetchers.py`

- [ ] **Step 1: Write failing fetcher tests**

Write `tests/test_fetchers.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from market_watch.fetchers import SourceDataError, fetch_indices, fetch_stocks


def test_fetch_stocks_calls_provider_and_filters_codes() -> None:
    class FakeAK:
        @staticmethod
        def stock_zh_a_spot_em() -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"代码": "300857", "名称": "协创数据", "最新价": 295.2},
                    {"代码": "300475", "名称": "香农芯创", "最新价": 252.3},
                    {"代码": "000001", "名称": "平安银行", "最新价": 10.1},
                ]
            )

    frame = fetch_stocks(["300857", "300475"], provider=FakeAK)

    assert frame["代码"].tolist() == ["300857", "300475"]


def test_fetch_indices_calls_provider_and_filters_codes() -> None:
    class FakeAK:
        @staticmethod
        def stock_zh_index_spot_em(symbol: str) -> pd.DataFrame:
            assert symbol == "沪深重要指数"
            return pd.DataFrame(
                [
                    {"代码": "399006", "名称": "创业板指", "最新价": 2310.2},
                    {"代码": "399001", "名称": "深证成指", "最新价": 12000.0},
                    {"代码": "000300", "名称": "沪深300", "最新价": 4000.0},
                ]
            )

    frame = fetch_indices(["399006"], symbol="沪深重要指数", provider=FakeAK)

    assert frame["代码"].tolist() == ["399006"]


def test_fetch_stocks_rejects_source_frame_without_code_column() -> None:
    class FakeAK:
        @staticmethod
        def stock_zh_a_spot_em() -> pd.DataFrame:
            return pd.DataFrame([{"名称": "协创数据", "最新价": 295.2}])

    with pytest.raises(SourceDataError, match="代码"):
        fetch_stocks(["300857"], provider=FakeAK)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_fetchers.py -v
```

Expected: FAIL because fetcher functions are not defined.

- [ ] **Step 3: Implement fetcher module**

Replace `market_watch/fetchers.py` with:

```python
from __future__ import annotations

from typing import Any

import pandas as pd


class SourceDataError(RuntimeError):
    """Raised when the source response is missing required structure."""


def fetch_stocks(codes: list[str], *, provider: Any | None = None) -> pd.DataFrame:
    ak = provider or _load_akshare()
    frame = ak.stock_zh_a_spot_em()
    return _filter_by_codes(frame, codes)


def fetch_indices(codes: list[str], *, symbol: str, provider: Any | None = None) -> pd.DataFrame:
    ak = provider or _load_akshare()
    frame = ak.stock_zh_index_spot_em(symbol=symbol)
    return _filter_by_codes(frame, codes)


def _filter_by_codes(frame: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    if "代码" not in frame.columns:
        raise SourceDataError("Source frame is missing required column: 代码")
    working = frame.copy()
    working["代码"] = working["代码"].astype(str)
    wanted = [str(code) for code in codes]
    return working[working["代码"].isin(wanted)].copy()


def _load_akshare() -> Any:
    import akshare as ak

    return ak
```

- [ ] **Step 4: Run fetcher tests**

Run:

```bash
pytest tests/test_fetchers.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit fetcher checkpoint**

Run only if `.git` exists:

```bash
git add market_watch/fetchers.py tests/test_fetchers.py
git commit -m "feat: fetch configured akshare targets"
```

Expected: commit succeeds.

---

### Task 8: Implement `--once` Pipeline

**Files:**
- Modify: `watch.py`
- Create: `tests/test_watch.py`

- [ ] **Step 1: Write failing `--once` tests**

Write `tests/test_watch.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import watch


def write_runtime_config(tmp_path: Path, sample_config_dict: dict) -> Path:
    sample_config_dict["storage"] = {
        "snapshot_dir": str(tmp_path / "data" / "snapshots"),
        "latest_markdown": str(tmp_path / "outputs" / "latest.md"),
        "latest_json": str(tmp_path / "outputs" / "latest.json"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8")
    return path


def test_run_once_writes_csv_markdown_and_json(
    tmp_path: Path,
    sample_config_dict: dict,
    monkeypatch,
) -> None:
    config_path = write_runtime_config(tmp_path, sample_config_dict)

    monkeypatch.setattr(watch, "current_market_timestamp", lambda timezone_name: ("2026-07-03 10:42:30", "2026-07-03"))
    monkeypatch.setattr(
        watch.fetchers,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                {
                    "代码": "300857",
                    "名称": "协创数据",
                    "最新价": 295.2,
                    "涨跌幅": 0.55,
                    "涨跌额": 1.61,
                    "成交量": 1234567,
                    "成交额": 1850000000,
                    "振幅": 2.32,
                    "最高": 298.8,
                    "最低": 292.0,
                    "今开": 298.0,
                    "昨收": 293.59,
                    "换手率": 8.1,
                    "涨速": 0.22,
                    "5分钟涨跌": 0.8,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        watch.fetchers,
        "fetch_indices",
        lambda codes, symbol: pd.DataFrame(
            [
                {
                    "代码": "399006",
                    "名称": "创业板指",
                    "最新价": 2310.2,
                    "涨跌幅": 0.4,
                    "涨跌额": 9.2,
                    "成交量": 123456789,
                    "成交额": 220000000000,
                    "振幅": 1.52,
                    "最高": 2320.0,
                    "最低": 2285.0,
                    "今开": 2298.0,
                    "昨收": 2301.0,
                }
            ]
        ),
    )

    exit_code = watch.run_once(config_path)

    assert exit_code == 0
    csv_path = tmp_path / "data" / "snapshots" / "2026-07-03.csv"
    assert csv_path.exists()
    assert "300857" in csv_path.read_text(encoding="utf-8")
    assert (tmp_path / "outputs" / "latest.md").exists()
    payload = json.loads((tmp_path / "outputs" / "latest.json").read_text(encoding="utf-8"))
    assert payload["current"]["stocks"][0]["code"] == "300857"
    assert payload["current"]["indices"][0]["code"] == "399006"


def test_market_hours_gate_uses_shanghai_weekday_sessions() -> None:
    assert watch.is_market_time("2026-07-03 09:30:00", "Asia/Shanghai") is True
    assert watch.is_market_time("2026-07-03 11:31:00", "Asia/Shanghai") is False
    assert watch.is_market_time("2026-07-03 13:00:00", "Asia/Shanghai") is True
    assert watch.is_market_time("2026-07-04 10:00:00", "Asia/Shanghai") is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_watch.py -v
```

Expected: FAIL because `run_once`, `current_market_timestamp`, and `is_market_time` are not defined.

- [ ] **Step 3: Implement `watch.py` once pipeline**

Replace `watch.py` with:

```python
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_watch import fetchers
from market_watch.config import ConfigError, load_config
from market_watch.normalize import make_error, normalize_index_frame, normalize_stock_frame
from market_watch.render import build_json_payload, render_markdown
from market_watch.storage import (
    append_snapshots,
    atomic_write_json,
    atomic_write_text,
    read_snapshots_for_trade_date,
)
from market_watch.summary import summarize_history


def current_market_timestamp(timezone_name: str) -> tuple[str, str]:
    now = datetime.now(ZoneInfo(timezone_name))
    return now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d")


def is_market_time(timestamp: str, timezone_name: str) -> bool:
    dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(timezone_name))
    if dt.weekday() >= 5:
        return False
    morning = dt.replace(hour=9, minute=30, second=0) <= dt <= dt.replace(hour=11, minute=30, second=0)
    afternoon = dt.replace(hour=13, minute=0, second=0) <= dt <= dt.replace(hour=15, minute=0, second=0)
    return morning or afternoon


def run_once(config_path: str | Path = "config.yaml") -> int:
    config = load_config(config_path)
    timestamp, trade_date = current_market_timestamp(config["runtime"]["market_timezone"])
    records, errors = collect_records(config, timestamp=timestamp, trade_date=trade_date)

    snapshot_dir = config["storage"]["snapshot_dir"]
    if records:
        append_snapshots(snapshot_dir, trade_date, records)

    history_rows = read_snapshots_for_trade_date(snapshot_dir, trade_date)
    history_summary = summarize_history(
        history_rows,
        windows_minutes=config["runtime"]["history_windows_minutes"],
        latest_timestamp=timestamp,
    )
    markdown = render_markdown(
        timestamp=timestamp,
        records=records,
        history_summary=history_summary,
        errors=errors,
    )
    payload = build_json_payload(
        timestamp=timestamp,
        records=records,
        history_summary=history_summary,
        errors=errors,
    )
    atomic_write_text(config["storage"]["latest_markdown"], markdown)
    atomic_write_json(config["storage"]["latest_json"], payload)
    print(markdown)
    return 0 if records or errors else 1


def collect_records(config: dict[str, Any], *, timestamp: str, trade_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    stock_targets = config["targets"]["stocks"]
    index_targets = config["targets"]["indices"]

    if stock_targets:
        try:
            stock_frame = fetchers.fetch_stocks([target["code"] for target in stock_targets])
            stock_records, stock_errors = normalize_stock_frame(
                stock_frame,
                stock_targets,
                timestamp=timestamp,
                trade_date=trade_date,
            )
            records.extend(stock_records)
            errors.extend(stock_errors)
        except Exception as exc:
            errors.append(
                make_error(
                    level="error",
                    stage="fetch_stocks",
                    code="SOURCE_FETCH_FAILED",
                    message=str(exc),
                    target=None,
                    timestamp=timestamp,
                )
            )

    if index_targets:
        try:
            index_frame = fetchers.fetch_indices(
                [target["code"] for target in index_targets],
                symbol=config["source"]["index_symbol"],
            )
            index_records, index_errors = normalize_index_frame(
                index_frame,
                index_targets,
                timestamp=timestamp,
                trade_date=trade_date,
            )
            records.extend(index_records)
            errors.extend(index_errors)
        except Exception as exc:
            errors.append(
                make_error(
                    level="error",
                    stage="fetch_indices",
                    code="SOURCE_FETCH_FAILED",
                    message=str(exc),
                    target=None,
                    timestamp=timestamp,
                )
            )

    return records, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect configured A-share market data.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--once", action="store_true", help="Run one sample and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=None, help="Override interval seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.loop:
            return run_loop(args.config, interval_override=args.interval)
        return run_once(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2


def run_loop(config_path: str | Path = "config.yaml", *, interval_override: int | None = None) -> int:
    config = load_config(config_path)
    interval = interval_override or config["runtime"]["interval_seconds"]
    try:
        while True:
            timestamp, _trade_date = current_market_timestamp(config["runtime"]["market_timezone"])
            if not config["runtime"]["market_hours_only"] or is_market_time(timestamp, config["runtime"]["market_timezone"]):
                run_once(config_path)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Market Watch stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run `--once` tests**

Run:

```bash
pytest tests/test_watch.py -v
```

Expected: PASS.

- [ ] **Step 5: Run integrated fixture test suite**

Run:

```bash
pytest tests/test_config.py tests/test_normalize.py tests/test_storage.py tests/test_summary.py tests/test_render.py tests/test_fetchers.py tests/test_watch.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit `--once` checkpoint**

Run only if `.git` exists:

```bash
git add watch.py tests/test_watch.py
git commit -m "feat: run one market data collection sample"
```

Expected: commit succeeds.

---

### Task 9: Harden Retry, Storage Failure, And Loop Scheduling

**Files:**
- Modify: `watch.py`
- Modify: `tests/test_watch.py`

**MVP timeout/retry contract:** `retry_count` controls real retry attempts in
`collect_records()`. `request_timeout_seconds` is a slow-call warning threshold,
not a hard timeout, because the AKShare calls used here do not expose a reliable
per-call timeout API in this plan.

- [ ] **Step 1: Add retry, failure, and loop tests**

Append these tests to `tests/test_watch.py`:

```python

def test_collect_records_keeps_index_when_stock_fetch_fails(sample_config_dict: dict, monkeypatch) -> None:
    def fail_stocks(codes):
        raise RuntimeError("stock source down")

    monkeypatch.setattr(watch.fetchers, "fetch_stocks", fail_stocks)
    monkeypatch.setattr(
        watch.fetchers,
        "fetch_indices",
        lambda codes, symbol: pd.DataFrame(
            [
                {
                    "代码": "399006",
                    "名称": "创业板指",
                    "最新价": 2310.2,
                    "涨跌幅": 0.4,
                    "涨跌额": 9.2,
                    "成交量": 123456789,
                    "成交额": 220000000000,
                    "振幅": 1.52,
                    "最高": 2320.0,
                    "最低": 2285.0,
                    "今开": 2298.0,
                    "昨收": 2301.0,
                }
            ]
        ),
    )

    records, errors = watch.collect_records(
        sample_config_dict,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records[0]["asset_type"] == "index"
    assert errors[0]["stage"] == "fetch_stocks"
    assert errors[0]["code"] == "SOURCE_FETCH_FAILED"


def test_collect_records_retries_fetch_once(sample_config_dict: dict, monkeypatch) -> None:
    sample_config_dict["targets"]["indices"] = []
    calls = {"stocks": 0}

    def flaky_stocks(codes):
        calls["stocks"] += 1
        if calls["stocks"] == 1:
            raise RuntimeError("temporary failure")
        return pd.DataFrame(
            [
                {
                    "代码": "300857",
                    "名称": "协创数据",
                    "最新价": 295.2,
                    "涨跌幅": 0.55,
                    "涨跌额": 1.61,
                    "成交量": 1234567,
                    "成交额": 1850000000,
                    "振幅": 2.32,
                    "最高": 298.8,
                    "最低": 292.0,
                    "今开": 298.0,
                    "昨收": 293.59,
                    "换手率": 8.1,
                    "涨速": 0.22,
                    "5分钟涨跌": 0.8,
                }
            ]
        )

    monkeypatch.setattr(watch.fetchers, "fetch_stocks", flaky_stocks)

    records, errors = watch.collect_records(
        sample_config_dict,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert calls["stocks"] == 2
    assert records[0]["code"] == "300857"
    assert errors == []


def test_collect_records_emits_slow_fetch_warning(sample_config_dict: dict, monkeypatch) -> None:
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["runtime"]["request_timeout_seconds"] = 15
    monotonic_values = iter([0.0, 20.0])

    monkeypatch.setattr(watch.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(
        watch.fetchers,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                {
                    "代码": "300857",
                    "名称": "协创数据",
                    "最新价": 295.2,
                    "涨跌幅": 0.55,
                    "涨跌额": 1.61,
                    "成交量": 1234567,
                    "成交额": 1850000000,
                    "振幅": 2.32,
                    "最高": 298.8,
                    "最低": 292.0,
                    "今开": 298.0,
                    "昨收": 293.59,
                    "换手率": 8.1,
                    "涨速": 0.22,
                    "5分钟涨跌": 0.8,
                }
            ]
        ),
    )

    _records, errors = watch.collect_records(
        sample_config_dict,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert errors[0]["code"] == "SLOW_FETCH"
    assert errors[0]["level"] == "warning"


def test_collect_records_reports_source_field_missing(sample_config_dict: dict, monkeypatch) -> None:
    sample_config_dict["targets"]["indices"] = []

    def missing_code_column(codes):
        raise watch.fetchers.SourceDataError("Source frame is missing required column: 代码")

    monkeypatch.setattr(watch.fetchers, "fetch_stocks", missing_code_column)

    records, errors = watch.collect_records(
        sample_config_dict,
        timestamp="2026-07-03 10:42:30",
        trade_date="2026-07-03",
    )

    assert records == []
    assert errors[0]["code"] == "SOURCE_FIELD_MISSING"


def test_run_once_records_storage_failure_in_latest_json(
    tmp_path: Path,
    sample_config_dict: dict,
    monkeypatch,
) -> None:
    sample_config_dict["targets"]["indices"] = []
    config_path = write_runtime_config(tmp_path, sample_config_dict)

    monkeypatch.setattr(watch, "current_market_timestamp", lambda timezone_name: ("2026-07-03 10:42:30", "2026-07-03"))
    monkeypatch.setattr(
        watch.fetchers,
        "fetch_stocks",
        lambda codes: pd.DataFrame(
            [
                {
                    "代码": "300857",
                    "名称": "协创数据",
                    "最新价": 295.2,
                    "涨跌幅": 0.55,
                    "涨跌额": 1.61,
                    "成交量": 1234567,
                    "成交额": 1850000000,
                    "振幅": 2.32,
                    "最高": 298.8,
                    "最低": 292.0,
                    "今开": 298.0,
                    "昨收": 293.59,
                    "换手率": 8.1,
                    "涨速": 0.22,
                    "5分钟涨跌": 0.8,
                }
            ]
        ),
    )
    monkeypatch.setattr(watch.fetchers, "fetch_indices", lambda codes, symbol: pd.DataFrame())
    monkeypatch.setattr(watch, "append_snapshots", lambda snapshot_dir, trade_date, records: (_ for _ in ()).throw(OSError("disk full")))

    exit_code = watch.run_once(config_path)

    assert exit_code == 1
    payload = json.loads((tmp_path / "outputs" / "latest.json").read_text(encoding="utf-8"))
    assert any(error["code"] == "STORAGE_WRITE_FAILED" for error in payload["errors"])


def test_run_loop_skips_outside_market_hours(tmp_path: Path, sample_config_dict: dict, monkeypatch) -> None:
    config_path = write_runtime_config(tmp_path, sample_config_dict)
    calls = {"run_once": 0, "sleep": 0}

    monkeypatch.setattr(watch, "current_market_timestamp", lambda timezone_name: ("2026-07-03 12:00:00", "2026-07-03"))
    monkeypatch.setattr(watch, "run_once", lambda config_path: calls.__setitem__("run_once", calls["run_once"] + 1) or 0)

    def fake_sleep(interval):
        calls["sleep"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(watch.time, "sleep", fake_sleep)

    assert watch.run_loop(config_path, interval_override=1) == 0
    assert calls == {"run_once": 0, "sleep": 1}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_watch.py -v
```

Expected: FAIL because retry, slow-fetch warnings, source-field errors, and
storage-failure rendering are not implemented yet.

- [ ] **Step 3: Replace hardened watch helpers**

In `watch.py`, change `from typing import Any` to this import, replace
`run_once`, replace `collect_records`, add `_fetch_with_retry`, and replace
`run_loop` with the code below. Keep `current_market_timestamp()`,
`is_market_time()`, `build_parser()`, and `main()` from Task 8 unchanged.

```python
from typing import Any, Callable
```

```python
def run_once(config_path: str | Path = "config.yaml") -> int:
    config = load_config(config_path)
    timestamp, trade_date = current_market_timestamp(config["runtime"]["market_timezone"])
    records, errors = collect_records(config, timestamp=timestamp, trade_date=trade_date)

    snapshot_dir = config["storage"]["snapshot_dir"]
    storage_failed = False
    if records:
        try:
            append_snapshots(snapshot_dir, trade_date, records)
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

    history_rows = read_snapshots_for_trade_date(snapshot_dir, trade_date)
    history_summary = summarize_history(
        history_rows,
        windows_minutes=config["runtime"]["history_windows_minutes"],
        latest_timestamp=timestamp,
    )
    markdown = render_markdown(
        timestamp=timestamp,
        records=records,
        history_summary=history_summary,
        errors=errors,
    )
    payload = build_json_payload(
        timestamp=timestamp,
        records=records,
        history_summary=history_summary,
        errors=errors,
    )
    atomic_write_text(config["storage"]["latest_markdown"], markdown)
    atomic_write_json(config["storage"]["latest_json"], payload)
    print(markdown)
    if storage_failed:
        return 1
    return 0 if records or errors else 1


def collect_records(config: dict[str, Any], *, timestamp: str, trade_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    stock_targets = config["targets"]["stocks"]
    index_targets = config["targets"]["indices"]
    retry_count = config["runtime"]["retry_count"]
    slow_threshold = config["runtime"]["request_timeout_seconds"]

    if stock_targets:
        stock_frame, fetch_errors = _fetch_with_retry(
            lambda: fetchers.fetch_stocks([target["code"] for target in stock_targets]),
            stage="fetch_stocks",
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold,
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

    if index_targets:
        index_frame, fetch_errors = _fetch_with_retry(
            lambda: fetchers.fetch_indices(
                [target["code"] for target in index_targets],
                symbol=config["source"]["index_symbol"],
            ),
            stage="fetch_indices",
            timestamp=timestamp,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold,
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


def _fetch_with_retry(
    operation: Callable[[], Any],
    *,
    stage: str,
    timestamp: str,
    retry_count: int,
    slow_threshold_seconds: int,
) -> tuple[Any | None, list[dict[str, Any]]]:
    attempts = retry_count + 1
    errors: list[dict[str, Any]] = []
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        started_at = time.monotonic()
        try:
            result = operation()
        except fetchers.SourceDataError as exc:
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
            last_error = exc
            if attempt < attempts:
                continue
            return None, [
                make_error(
                    level="error",
                    stage=stage,
                    code="SOURCE_FETCH_FAILED",
                    message=str(last_error),
                    target=None,
                    timestamp=timestamp,
                )
            ]

        elapsed = time.monotonic() - started_at
        if elapsed > slow_threshold_seconds:
            errors.append(
                make_error(
                    level="warning",
                    stage=stage,
                    code="SLOW_FETCH",
                    message=f"{stage} took {elapsed:.2f}s, above {slow_threshold_seconds}s threshold",
                    target=None,
                    timestamp=timestamp,
                )
            )
        return result, errors
    return None, errors


def run_loop(config_path: str | Path = "config.yaml", *, interval_override: int | None = None) -> int:
    config = load_config(config_path)
    interval = interval_override or config["runtime"]["interval_seconds"]
    try:
        while True:
            timestamp, _trade_date = current_market_timestamp(config["runtime"]["market_timezone"])
            if config["runtime"]["market_hours_only"] and not is_market_time(timestamp, config["runtime"]["market_timezone"]):
                time.sleep(interval)
                continue
            run_once(config_path)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Market Watch stopped.")
        return 0
```

- [ ] **Step 4: Run hardened watch tests**

Run:

```bash
pytest tests/test_watch.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit loop checkpoint**

Run only if `.git` exists:

```bash
git add watch.py tests/test_watch.py
git commit -m "feat: add market-hours loop scheduling"
```

Expected: commit succeeds.

---

### Task 10: Final Verification And Documentation Check

**Files:**
- Modify: `README.md` if command output or paths differ from documented behavior.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
python -m compileall watch.py market_watch tests
```

Expected: command exits 0.

- [ ] **Step 3: Run offline fixture confidence check**

Run:

```bash
pytest tests/test_config.py tests/test_normalize.py tests/test_storage.py tests/test_summary.py tests/test_render.py tests/test_fetchers.py tests/test_watch.py -v
```

Expected: all tests pass without live network access.

- [ ] **Step 4: Run live `--once` smoke test during acceptable sampling time**

Run:

```bash
python watch.py --once
```

Expected:

- Command exits 0 when AKShare returns at least one configured target.
- `data/snapshots/YYYY-MM-DD.csv` exists for the current `Asia/Shanghai` date.
- `outputs/latest.md` exists and contains `盘中行情数据快照`.
- `outputs/latest.json` exists and contains `current`, `history_summary`, and `errors`.

- [ ] **Step 5: Confirm no strategy advice language in generated output or implementation**

Run:

```bash
rg -n "买入|卖出|加仓|减仓|止损|右侧确认|短线弱势|破位风险|假跌破|可以买|不宜|buy recommendation|sell recommendation|buy signal|sell signal|stop loss" outputs market_watch
```

Expected: no matches in generated outputs or implementation files. If the command reports missing paths for files that do not exist, rerun after Step 4 creates `outputs/`.

- [ ] **Step 6: Commit final checkpoint**

Run only if `.git` exists:

```bash
git add README.md requirements.txt config.yaml watch.py market_watch tests
git commit -m "test: verify market watch data collector"
```

Expected: commit succeeds or reports no changes to commit.

---

## Self-Review Checklist

- Spec coverage:
  - Config validation is covered by Task 2.
  - AKShare field mapping and missing values are covered by Task 3.
  - CSV append, headers, history reads, and atomic writes are covered by Task 4.
  - Objective 15/30/60 minute summaries are covered by Task 5.
  - Markdown, JSON output shape, missing value display, and dynamic window titles are covered by Task 6.
  - AKShare wrapper boundaries and missing `代码` source frames are covered by Task 7.
  - `--once`, retry, slow-call warnings, storage failure rendering, partial success, market-hours gate, and `Ctrl+C` loop behavior are covered by Tasks 8 and 9.
  - Final no-strategy-language verification is covered by Task 10.
- Type consistency:
  - Normalized records are dictionaries keyed by `SNAPSHOT_FIELDS`.
  - `errors` are dictionaries with `level`, `stage`, `code`, `message`, `target`, and `timestamp`.
  - Summary payloads use `{"windows_minutes": list[int], "items": list[dict]}`.
  - Render payloads group records into `current.stocks` and `current.indices`.
  - Fetch hardening uses `SourceDataError`, `_fetch_with_retry()`, `SOURCE_FIELD_MISSING`, `SOURCE_FETCH_FAILED`, `SLOW_FETCH`, and `STORAGE_WRITE_FAILED` consistently.
- Execution order:
  - The plan builds a verified `--once` pipeline before adding loop behavior.
  - Live AKShare access is only needed in the final smoke test; unit tests use fixtures and monkeypatching.
