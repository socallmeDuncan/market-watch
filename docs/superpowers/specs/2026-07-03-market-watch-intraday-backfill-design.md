# Market Watch Intraday Backfill Design

## Purpose

Add a small after-hours backfill feature that can fetch today's full intraday
minute data for the configured stocks and indices, then render Markdown and JSON
outputs for ChatGPT analysis.

This feature remains data-only. It does not produce trading decisions, strategy
labels, buy/sell suggestions, thresholds, or standards for judging a move.

## Background

The existing collector samples real-time quote snapshots during market hours.
Those snapshots are useful when the process has been running all day, because
they preserve the 60-second state seen by the script.

Outside market hours, two cases are different:

- If the collector ran during the day, today's `data/snapshots/YYYY-MM-DD.csv`
  already contains the saved 60-second snapshots.
- If the collector did not run, the script cannot recreate real-time snapshot
  fields such as speed, five-minute change, or turnover-rate state at each
  sample. It can, however, fetch recent one-minute intraday bars from AKShare.

Therefore the backfill feature should fetch one-minute bars as a separate data
type instead of filling the snapshot CSV with synthetic snapshot rows.

## Recommended Approach

Use a separate "intraday backfill" mode:

```bash
python3 watch.py --backfill-today
```

The command uses the configured targets, computes today's trade date in
`Asia/Shanghai`, fetches one-minute bars for the regular A-share session, writes
a separate intraday CSV, and renders separate latest-today outputs:

```text
data/intraday/YYYY-MM-DD-1m.csv
outputs/today.md
outputs/today.json
```

This keeps the current 60-second real-time collector simple while adding a
clean path for after-hours daily review.

## Alternatives Considered

### A. Reuse Existing Snapshot CSV Only

This is simplest but only works when the process was already running during the
day. It cannot recover missed intraday data after the fact, so it does not solve
the user's after-hours use case.

### B. Separate One-Minute Intraday Backfill

This is the recommended first version. It is still small, fits the current
module boundaries, and can be upgraded later. The trade-off is that minute bars
are not identical to real-time quote snapshots, so the schema and output should
make that difference explicit.

### C. Full Historical Persistence Layer

This would introduce SQLite, trading calendars, deduplication policies, and
query APIs now. It may become useful later, but it is more than this personal
tool needs for the next step.

## Scope

### In Scope

- Add a CLI mode: `python3 watch.py --backfill-today`.
- Fetch one-minute intraday bars for configured stocks.
- Fetch one-minute intraday bars for configured indices.
- Store backfilled rows in `data/intraday/YYYY-MM-DD-1m.csv`.
- Render `outputs/today.md` and `outputs/today.json`.
- Include objective daily and per-target summaries in the output.
- Include the full minute rows in JSON.
- Include the full minute rows in Markdown for direct ChatGPT review.
- Continue fetching other targets if one target fails.
- Surface source and storage errors in the rendered outputs.

### Out of Scope

- Trading decisions, trading labels, or strategy rules.
- Automatic previous-trading-day fallback on weekends or holidays.
- A full exchange calendar.
- SQLite migration.
- Dashboard, notifications, or APIs.
- Reconstructing real-time-only fields from minute bars.
- Merging backfilled rows into `data/snapshots/YYYY-MM-DD.csv`.

## Source Data

Use AKShare's Eastmoney one-minute intraday interfaces:

- Stocks: `ak.stock_zh_a_hist_min_em(symbol=code, period="1", adjust="",
  start_date=start, end_date=end)`.
- Indices: `ak.index_zh_a_hist_min_em(symbol=code, period="1",
  start_date=start, end_date=end)`.

Official AKShare notes that stock one-minute data is recent-only and not
adjusted. The source output fields include:

```text
时间
开盘
收盘
最高
最低
成交量
成交额
均价
```

The first version should rely only on these shared fields so stock and index
backfill can share one normalizer.

References:

- https://akshare.akfamily.xyz/data/stock/stock.html
- https://akshare.akfamily.xyz/data/index/index.html

## Time Range

Default time range for `--backfill-today`:

```text
YYYY-MM-DD 09:30:00 -> YYYY-MM-DD 15:00:00
```

The date is calculated in `runtime.market_timezone`, which defaults to
`Asia/Shanghai`.

If the command runs during the lunch break or before close, it may request the
full day; the source will return currently available rows. The renderer should
report the actual first and last bar timestamps returned.

If today's date is not a trading day, the command should write outputs with no
rows and a clear data warning. It should not silently switch to the previous
trading day in the first version.

## Intraday Row Schema

Each CSV row represents one target at one one-minute bar timestamp.

```text
timestamp
trade_date
asset_type
code
name
role
period
open
high
low
close
volume
amount
average_price
source
```

Field notes:

- `timestamp`: source bar time, formatted as `YYYY-MM-DD HH:MM:SS`.
- `trade_date`: `YYYY-MM-DD` in the configured market timezone.
- `asset_type`: `stock` or `index`.
- `period`: initially `1m`.
- `volume`: source unit is "hands" for the AKShare interfaces above.
- `amount`: source unit is yuan.
- `average_price`: mapped from `均价` when present; otherwise `null` in JSON
  and empty in CSV.
- `source`: initially `akshare_em_intraday_1m`.

This schema is intentionally separate from the real-time snapshot schema. It has
OHLCV fields, but it does not have snapshot fields such as `speed`,
`five_min_change`, `turnover_rate`, or `change_pct`.

## Output Shape

### `outputs/today.json`

JSON should include the complete normalized intraday rows:

```json
{
  "generated_at": "2026-07-03 16:05:00",
  "trade_date": "2026-07-03",
  "period": "1m",
  "time_range": {
    "start": "2026-07-03 09:30:00",
    "end": "2026-07-03 15:00:00"
  },
  "rows": [],
  "summary": {
    "items": []
  },
  "errors": []
}
```

### `outputs/today.md`

Markdown should be copy-paste friendly:

- Title and generated time.
- Requested date and actual returned time span.
- Per-target objective summary table.
- Full minute rows grouped by target or sorted by timestamp and target.
- Data warnings, if any.
- A final ChatGPT request asking for fact-based description only.

The Markdown output may be long. That is acceptable for the first version
because the configured target list is small, and the full-day row count is
roughly 241 rows per target.

## Objective Summary

The summary should compute facts only:

- First bar timestamp.
- Last bar timestamp.
- First close.
- Last close.
- Day high.
- Day low.
- Close change amount.
- Close change percentage.
- Total volume.
- Total amount.
- Row count.

The summary must not classify the move or make recommendations.

## Configuration

Add optional storage defaults:

```yaml
storage:
  intraday_dir: "data/intraday"
  today_markdown: "outputs/today.md"
  today_json: "outputs/today.json"
```

No strategy fields should be added. No separate `intraday` config section is
needed in the first version because the feature is intentionally fixed to
today's one-minute bars.

## Module Changes

### `watch.py`

- Add `--backfill-today`.
- Route this mode to a new backfill pipeline.
- Keep `--once` and `--loop` behavior unchanged.
- Do not apply `market_hours_only` to `--backfill-today`.

### `market_watch/fetchers.py`

- Add wrappers for stock and index one-minute intraday fetches.
- Keep provider injection support for tests.
- Convert target-level failures into structured errors while allowing other
  targets to continue.

### `market_watch/intraday.py`

Add a focused module for intraday-specific work:

- Build start and end datetime strings.
- Normalize stock and index minute bar frames.
- Build objective per-target summaries.
- Render the JSON payload inputs.

This keeps `normalize.py` focused on current snapshot normalization and avoids
overloading one module with two schemas.

### `market_watch/storage.py`

- Add an intraday CSV path helper.
- Add an atomic write function for complete intraday CSV replacement.
- Do not append rows on each backfill run, because repeated backfills should not
  duplicate the same one-minute bars.

### `market_watch/render.py`

- Add Markdown and JSON builders for today's intraday data.
- Keep the current `latest.md` and `latest.json` renderers unchanged.

### `market_watch/config.py`

- Add defaults and validation for `storage.intraday_dir`,
  `storage.today_markdown`, and `storage.today_json`.
- Preserve backwards compatibility with existing `config.yaml` files that omit
  these fields.

## Error Handling

Use structured errors similar to the existing collector:

- `INTRADAY_SOURCE_FETCH_FAILED`
- `INTRADAY_SOURCE_FIELD_MISSING`
- `INTRADAY_NO_ROWS`
- `INTRADAY_STORAGE_WRITE_FAILED`
- `INTRADAY_SLOW_FETCH`

If one target fails, the command should still write outputs for successful
targets and include the failed target in `errors`.

If all targets fail or return no rows, the command should still write
`outputs/today.md` and `outputs/today.json` with empty `rows`, empty summary,
and clear errors.

## Testing

Use test-driven development with source calls mocked or provider-injected. Tests
should not call AKShare live endpoints.

Required coverage:

- CLI routes `--backfill-today` without changing `--once` or `--loop`.
- Today date and time range use `runtime.market_timezone`.
- Stock intraday frames normalize to the intraday schema.
- Index intraday frames normalize to the same schema.
- Missing required source fields produce structured errors.
- Backfill CSV replacement does not duplicate rows across repeated runs.
- JSON output includes full rows, summary, and errors.
- Markdown output contains objective summary and does not include trading advice
  language.
- Partial target failure still writes successful rows.

## Acceptance Criteria

- `python3 watch.py --backfill-today` creates or replaces
  `data/intraday/YYYY-MM-DD-1m.csv`.
- It writes `outputs/today.md` and `outputs/today.json`.
- Existing commands still pass:

```bash
python3 watch.py --once
python3 watch.py --loop --interval 60
```

- The implementation keeps the real-time snapshot storage separate from
  intraday backfill storage.
- The rendered outputs contain objective facts only.
- The full test suite passes.

## Future Upgrade Path

If this feature becomes central to daily use, the next reasonable upgrades are:

- Add `--date YYYY-MM-DD` for manual replay of recent days supported by the
  source.
- Add `--last-trading-day` with an exchange calendar.
- Add compact Markdown output when the configured target list grows.
- Move both snapshot and intraday data into SQLite if CSV scanning becomes slow.
