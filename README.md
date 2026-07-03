# Market Watch v1

一个自用的 A 股行情数据采集脚本。它只负责抓数据、保存数据、渲染 Markdown/JSON，方便后续把结果交给 ChatGPT 做事实分析。

## 1. 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## 2. 配置标的

编辑 `config.yaml`：

- `targets.stocks`：要跟踪的个股。
- `targets.indices`：要跟踪的指数。
- `runtime.interval_seconds`：盘中循环刷新间隔，默认 `60` 秒。
- `runtime.market_hours_only`：默认 `true`，循环模式只在交易时段采样。
- `storage`：输出文件位置。

## 3. 盘中每 60 秒采样

```bash
python3 watch.py --loop
```

用途：

- 交易时段内每 60 秒抓一次当前行情。
- 持续写入当天快照 CSV，保留较长时间的盘中走势记录。
- 同步刷新最新 Markdown 和 JSON，方便随时交给 ChatGPT。

如果想临时覆盖刷新间隔：

```bash
python3 watch.py --loop --interval 30
```

## 4. 单次抓取

```bash
python3 watch.py --once
```

用途：

- 立即抓一次当前行情。
- 不受 `market_hours_only` 限制，适合测试配置和输出格式。

## 5. 非交易时段补抓今天分钟线

```bash
python3 watch.py --backfill-today
```

用途：

- 抓取今天可获得的 1 分钟 OHLCV 数据。
- 适合盘后复盘，或当天没有启动 `--loop` 时补一份分钟级数据。
- 输出和 60 秒实时快照分开保存，不会把分钟线伪装成实时快照。
- 单个标的抓取失败时，会继续抓其他标的，并把错误写入输出文件。

## 6. 输出文件

盘中实时快照：

- `data/snapshots/YYYY-MM-DD.csv`
- `outputs/latest.md`
- `outputs/latest.json`

当日分钟线补抓：

- `data/intraday/YYYY-MM-DD-1m.csv`
- `outputs/today.md`
- `outputs/today.json`

推荐用法：

- 盘中看 `outputs/latest.md` 或 `outputs/latest.json`。
- 盘后看 `outputs/today.md` 或 `outputs/today.json`。
- 需要原始长期记录时，看 `data/snapshots/` 和 `data/intraday/`。

## 7. 数据边界

本项目只采集和整理行情数据，不内置交易规则，不输出交易决策，也不生成策略标签。Markdown 末尾给 ChatGPT 的请求也限定为基于表格事实进行描述。
