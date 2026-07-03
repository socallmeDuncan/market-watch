# Market Watch Data Collector Design

## Purpose

Build a lightweight intraday market data collector for selected A-share stocks,
indices, and later sector proxies. The tool runs during trading hours, samples
market data every 60 seconds, stores long-term historical snapshots, and renders
Markdown and JSON outputs that can be given to ChatGPT for analysis.

The tool does not make trading decisions. It does not label right-side
confirmation, breakdowns, buy zones, sell conditions, or any other strategy
state. It only collects, normalizes, stores, and summarizes objective market
data.

## Scope

### In Scope

- Fetch selected A-share stock quotes through AKShare.
- Fetch selected index quotes through AKShare.
- Run in a loop with a default 60-second interval.
- Save multi-day historical snapshots as daily CSV files.
- Normalize source-specific fields into a stable internal schema.
- Render the latest snapshot as Markdown.
- Render the latest snapshot and recent-window statistics as JSON.
- Summarize objective statistics over recent 15, 30, and 60 minute windows.
- Handle source failures without terminating the long-running process.

### Out of Scope

- Automatic trading.
- Automatic order placement.
- Buy, sell, hold, add, reduce, or stop-loss recommendations.
- Strategy labels such as "right-side confirmation", "weakness", "breakdown",
  or "false breakdown".
- Built-in trading rules or thresholds.
- FastAPI, public HTTPS APIs, dashboards, databases, or notification delivery in
  the first implementation.

## Recommended Architecture

Use a CSV-first storage design: daily CSV files are the source of historical
records, while the schema stays stable enough to migrate to SQLite later.

The runtime flow is:

```text
load config
-> fetch raw AKShare data
-> filter configured stocks and indices
-> normalize into stable records
-> append records to the current trade-date CSV
-> read recent history windows
-> compute objective statistics
-> write outputs/latest.md
-> write outputs/latest.json
-> wait for the next 60-second interval
```

## Project Structure

```text
market-watch/
  README.md
  requirements.txt
  config.yaml
  watch.py
  market_watch/
    __init__.py
    config.py
    fetchers.py
    normalize.py
    storage.py
    summary.py
    render.py
  data/
    snapshots/
  outputs/
    latest.md
    latest.json
```

## Module Responsibilities

### `watch.py`

Command-line entry point. It loads configuration, starts single-run or loop mode,
coordinates the pipeline, handles errors, and exits cleanly on `Ctrl+C`.

### `market_watch/config.py`

Loads and validates `config.yaml`. It should provide defaults for interval,
storage paths, and history windows.

### `market_watch/fetchers.py`

Fetches raw data from AKShare. The first version should support:

- `ak.stock_zh_a_spot_em()` for A-share stock quotes.
- `ak.stock_zh_index_spot_em(symbol="沪深重要指数")` for major index quotes.

This module returns source-shaped data and does not normalize or summarize it.

### `market_watch/normalize.py`

Converts AKShare Chinese column names into a stable internal schema. Downstream
modules should depend on normalized fields only, so future AKShare field changes
can be isolated here.

### `market_watch/storage.py`

Appends normalized records to daily CSV files and reads recent history for the
configured windows.

Daily CSV path:

```text
data/snapshots/YYYY-MM-DD.csv
```

The first version intentionally keeps every 60-second sample, even when values
do not change, because repeated records show how long a price persisted.

### `market_watch/summary.py`

Computes objective statistics only. It must not encode trading rules or produce
strategy labels.

Examples:

- Current price.
- Latest change percentage.
- Window high and low.
- Price change from the start of the window to now.
- Amount change from the start of the window to now, when available.
- Number of samples in the window.
- First and last timestamps in the window.

### `market_watch/render.py`

Renders:

- `outputs/latest.md` for human reading and copy-paste into ChatGPT.
- `outputs/latest.json` for structured reuse, debugging, or future automation.

## Configuration

Initial `config.yaml`:

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
  loop: true
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

No strategy levels or trading thresholds should be included in the first
configuration.

## Config Validation

`market_watch/config.py` should validate configuration before the first fetch.
Invalid configuration should stop the process with a clear error message.

Required rules:

- `targets.stocks` and `targets.indices` must be lists. Empty lists are allowed
  only if the other target list is non-empty.
- Each target must include non-empty `code`, `name`, and `role` fields.
- `role` must be one of `primary`, `compare`, or `context`.
- The same `asset_type + code` pair must not appear more than once.
- `runtime.interval_seconds` must be a positive integer.
- `runtime.history_windows_minutes` must be a non-empty list of positive
  integers.
- `runtime.market_timezone` defaults to `Asia/Shanghai`.
- `runtime.request_timeout_seconds` must be a positive integer.
- `runtime.retry_count` must be a non-negative integer.
- `storage.snapshot_dir`, `storage.latest_markdown`, and `storage.latest_json`
  must be non-empty paths.
- `source.provider` must be `akshare` in the first implementation.
- `source.index_symbol` must be non-empty when indices are configured.

## Normalized Snapshot Schema

Each CSV row represents one asset at one sample time.

```text
timestamp
trade_date
asset_type
code
name
role
price
change_pct
change_amount
open
high
low
prev_close
volume
amount
amplitude
turnover_rate
speed
five_min_change
source
```

Field notes:

- `asset_type`: `stock`, `index`, and later `sector` if needed.
- `role`: `primary`, `compare`, or `context`.
- `source`: initially `akshare_em`.
- Missing source fields should be stored as empty values in CSV and `null` in
  JSON.

This schema can later be mapped directly into a SQLite table.

## Source Field Mapping

The first implementation should pin AKShare-to-normalized-field mappings in
`normalize.py` and cover them with fixture tests. Downstream modules should not
read AKShare Chinese column names directly.

### Stock Mapping

Source: `ak.stock_zh_a_spot_em()`.

| Normalized field | AKShare field | Unit contract |
|---|---|---|
| `code` | `代码` | string, keep leading zeroes |
| `name` | `名称` | string |
| `price` | `最新价` | numeric price |
| `change_pct` | `涨跌幅` | percentage points, e.g. `1.23` means `1.23%` |
| `change_amount` | `涨跌额` | numeric price delta |
| `volume` | `成交量` | source value, Eastmoney A-share docs describe stock volume as hands |
| `amount` | `成交额` | source value, Eastmoney A-share docs describe stock amount as yuan |
| `amplitude` | `振幅` | percentage points |
| `high` | `最高` | numeric price |
| `low` | `最低` | numeric price |
| `open` | `今开` | numeric price |
| `prev_close` | `昨收` | numeric price |
| `turnover_rate` | `换手率` | percentage points |
| `speed` | `涨速` | source numeric value |
| `five_min_change` | `5分钟涨跌` | percentage points |

The first version does not store stock-only valuation fields such as
`市盈率-动态`, `市净率`, `总市值`, or `流通市值`. They can be added later without
changing the collector boundary.

### Index Mapping

Source: `ak.stock_zh_index_spot_em(symbol="沪深重要指数")`, with the configured
symbol allowed to override the default.

| Normalized field | AKShare field | Unit contract |
|---|---|---|
| `code` | `代码` | string, keep leading zeroes |
| `name` | `名称` | string |
| `price` | `最新价` | numeric index value |
| `change_pct` | `涨跌幅` | percentage points |
| `change_amount` | `涨跌额` | numeric index delta |
| `volume` | `成交量` | source numeric value |
| `amount` | `成交额` | source numeric value |
| `amplitude` | `振幅` | percentage points |
| `high` | `最高` | numeric index value |
| `low` | `最低` | numeric index value |
| `open` | `今开` | numeric index value |
| `prev_close` | `昨收` | numeric index value |
| `turnover_rate` | none | missing |
| `speed` | none | missing |
| `five_min_change` | none | missing |

### Missing Values

If a source field is absent, blank, `NaN`, or cannot be parsed as the expected
numeric type:

- CSV stores an empty value.
- JSON stores `null`.
- Markdown displays `-`.
- A per-field warning is recorded only when the missing field is required for
  the configured asset type. Optional fields should stay silent.

### Fixture Requirement

Tests should include fixture rows shaped like real AKShare stock and index
responses. The fixtures should include at least one missing optional index field
and one stock row with all MVP fields present.

## Time Model

All market time calculations use `Asia/Shanghai`, independent of the machine's
local timezone.

- `timestamp` records when the local collector finished normalizing a sample,
  formatted in `Asia/Shanghai`.
- `trade_date` is derived from the `Asia/Shanghai` date of `timestamp`.
- AKShare source timestamps are not used as the first implementation's fact
  time unless a later source provides a reliable per-row timestamp field.
- History windows filter by timestamp range, not by assumed sample count. A
  30-minute window means records where `timestamp >= latest_timestamp - 30
  minutes`.
- At startup, or after missing samples, summaries use the available records
  only. They must output `sample_count`, `first_timestamp`, and `last_timestamp`
  instead of filling or inferring missing data.
- The default market-hours gate is an approximation for A-share continuous
  auction hours: 09:30-11:30 and 13:00-15:00, Monday through Friday, in
  `Asia/Shanghai`.
- The first implementation does not maintain a holiday calendar and does not
  sample 09:15-09:25 call auction data by default.
- Users can set `market_hours_only: false` to sample outside the default gate.

## History Summary

For each configured target and each configured window, compute a fact-only
summary:

```json
{
  "code": "300857",
  "name": "协创数据",
  "window_minutes": 30,
  "sample_count": 30,
  "first_timestamp": "2026-07-03 10:12:30",
  "last_timestamp": "2026-07-03 10:42:30",
  "first_price": 292.8,
  "last_price": 295.2,
  "price_change": 2.4,
  "price_change_pct": 0.82,
  "window_high": 298.8,
  "window_low": 289.6,
  "latest_amount": 1850000000
}
```

The summary may mention observed prices and changes, but it must not interpret
them as buy, sell, risk, confirmation, weakness, or reversal signals.

## Scheduling Contract

Loop mode is single-threaded and does not start overlapping fetches.

- Each round records `sample_started_at` and then runs fetch, normalize, store,
  summarize, and render serially.
- `request_timeout_seconds` applies to each AKShare fetch wrapper where the
  implementation can enforce it.
- If an AKShare API does not expose a timeout parameter, the MVP should avoid
  complex hard-kill workers. It should record elapsed time and emit a
  `SLOW_FETCH` warning if a call returns after the configured timeout.
- `retry_count: 1` means one retry after the initial failed attempt.
- If a round takes longer than `interval_seconds`, the next round starts after
  the current round finishes; the collector does not run catch-up rounds.
- Failures are recorded and the collector continues to the next scheduled
  round.

## Persistence Contract

CSV and latest-output writes should be predictable during long-running sessions.

- Daily CSV files are created under `data/snapshots/YYYY-MM-DD.csv`.
- CSV files write a header only when the file is first created.
- Later samples append rows without duplicating the header.
- Every normalized record includes a `timestamp`, `asset_type`, `code`, and
  `source`; together these define the first implementation's unique row
  identity.
- Multiple samples in the same minute are allowed. Exact second-level
  timestamps distinguish them.
- Repeated price values are allowed and should still be written, because they
  show duration.
- `outputs/latest.md` and `outputs/latest.json` should be written through a
  temporary file in the same directory and then atomically renamed into place.
- If CSV append succeeds but latest rendering fails, the CSV remains the durable
  record. The failure is printed and recorded in the next successful latest JSON
  if possible.
- If all fetches fail, no CSV rows are appended for that round. The collector
  should still attempt to update `outputs/latest.json` with structured errors
  and leave `outputs/latest.md` with either the previous successful content or a
  concise current error page.

## Markdown Output

`outputs/latest.md` should be optimized for direct copy-paste into ChatGPT:

```markdown
# 盘中行情数据快照

时间：2026-07-03 10:42:30

## 当前个股行情

| 代码 | 名称 | 最新价 | 涨跌幅 | 今开 | 最高 | 最低 | 昨收 | 成交额 | 换手率 | 涨速 | 5分钟涨跌 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## 当前指数行情

| 代码 | 名称 | 最新价 | 涨跌幅 | 今开 | 最高 | 最低 | 成交额 |
|---|---:|---:|---:|---:|---:|---:|---:|

## 最近 15 / 30 / 60 分钟客观统计

| 标的 | 窗口 | 样本数 | 起始价 | 当前价 | 区间最高 | 区间最低 | 区间涨跌幅 |
|---|---:|---:|---:|---:|---:|---:|---:|

## 给 ChatGPT 的分析请求

请基于以上客观行情数据，描述当前标的和相关指数的走势变化、
相对强弱、波动范围、成交活跃度变化，以及还缺少哪些数据。
不要假设脚本内置任何交易标准。
```

## JSON Output

`outputs/latest.json` should preserve structured data:

```json
{
  "timestamp": "2026-07-03 10:42:30",
  "current": {
    "stocks": [
      {
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
        "source": "akshare_em"
      }
    ],
    "indices": [
      {
        "timestamp": "2026-07-03 10:42:30",
        "trade_date": "2026-07-03",
        "asset_type": "index",
        "code": "399006",
        "name": "创业板指",
        "role": "context",
        "price": 2310.2,
        "change_pct": 0.4,
        "change_amount": 9.2,
        "open": 2298.0,
        "high": 2320.0,
        "low": 2285.0,
        "prev_close": 2301.0,
        "volume": 123456789,
        "amount": 220000000000,
        "amplitude": 1.52,
        "turnover_rate": null,
        "speed": null,
        "five_min_change": null,
        "source": "akshare_em"
      }
    ]
  },
  "history_summary": {
    "windows_minutes": [15, 30, 60],
    "items": [
      {
        "code": "300857",
        "name": "协创数据",
        "asset_type": "stock",
        "window_minutes": 30,
        "sample_count": 29,
        "first_timestamp": "2026-07-03 10:13:30",
        "last_timestamp": "2026-07-03 10:42:30",
        "first_price": 292.8,
        "last_price": 295.2,
        "price_change": 2.4,
        "price_change_pct": 0.82,
        "window_high": 298.8,
        "window_low": 289.6,
        "latest_amount": 1850000000
      }
    ]
  },
  "errors": [
    {
      "level": "warning",
      "stage": "fetch_indices",
      "code": "SOURCE_TIMEOUT",
      "message": "stock_zh_index_spot_em timed out",
      "target": null,
      "timestamp": "2026-07-03 10:42:30"
    }
  ]
}
```

## Error Handling

- Errors should use structured objects with these fields:
  `level`, `stage`, `code`, `message`, `target`, and `timestamp`.
- `level` should be `warning` for partial data or missing required fields and
  `error` for failed fetch, failed storage, or failed rendering. Missing
  optional fields should remain silent.
- If the stock fetch fails but index fetch succeeds, write successful index
  records and include a stock-fetch error.
- If the index fetch fails but stock fetch succeeds, write successful stock
  records and include an index-fetch error.
- If an interface succeeds but a configured target is absent, include a warning
  for that target and continue.
- If normalization fails for one record, skip that record, include an error for
  the target, and continue with other records.
- If CSV storage fails, do not claim the sample is durable. Still attempt to
  render latest JSON with the storage error.
- If latest Markdown or JSON rendering fails, keep the already-written CSV rows
  and print the render error.
- If output directories do not exist, create them.
- If `market_hours_only` is true, avoid writing repeated stale data outside
  regular A-share trading sessions.
- On `Ctrl+C`, print a short exit message and stop cleanly.

## Testing Strategy

Use focused tests around the stable parts of the system:

- Config loading and defaults.
- Normalization from sample AKShare-shaped rows.
- CSV append and recent-window loading.
- Objective summary calculations.
- Markdown and JSON rendering with missing values.

Fetching from AKShare should be wrapped so tests can use fixture data without
network access.

## Implementation Slices

Implement in two slices so the first useful loop is built on a verified single
sample pipeline:

1. `--once`: load config, fetch fixture or live data, normalize, append the
   current trade-date CSV, compute summaries from stored history, and write
   latest Markdown and JSON.
2. `--loop`: reuse the `--once` pipeline inside the scheduler, add
   market-hours gating, retry handling, structured loop errors, and clean
   `Ctrl+C` shutdown.

## Acceptance Criteria

- The tool runs on macOS with Python 3.11 or 3.12.
- `python watch.py --once` loads config, fetches configured targets, writes the
  current trade-date CSV, writes `outputs/latest.md`, and writes
  `outputs/latest.json`.
- `python watch.py --loop --interval 60` samples configured stocks and indices
  every 60 seconds during the configured market-hours gate.
- `Ctrl+C` exits loop mode cleanly without a traceback.
- Daily CSV files are written under `data/snapshots/`.
- Multi-day historical CSV files are preserved without overwriting prior days.
- CSV files contain one header and append subsequent rows without duplicate
  headers.
- Latest Markdown and JSON writes are atomic from the reader's perspective.
- Markdown includes current quote tables and recent-window objective statistics.
- JSON includes current records, history summaries, and errors.
- The implementation contains no buy/sell advice and no strategy labels.
- `pytest` passes fixture-based tests for config, normalize, storage, summary,
  and render modules.
- Fixture tests pass without network access.

## Future Evolution

### Add Sector Context

Add configured sector proxies, concept boards, or ETFs as additional `context`
targets once the initial stock and index pipeline is stable.

### Add SQLite

When CSV querying becomes inconvenient, import the same normalized schema into
SQLite. The existing daily CSV files can be migrated because they already use a
database-friendly flat schema.

### Add API or UI

After the collector is reliable, a FastAPI endpoint or local dashboard can read
from the same stored snapshots and latest JSON output.

## References

- AKShare official stock data documentation:
  `https://akshare.akfamily.xyz/data/stock/stock.html`
- AKShare official index data documentation:
  `https://akshare.akfamily.xyz/data/index/index.html`
