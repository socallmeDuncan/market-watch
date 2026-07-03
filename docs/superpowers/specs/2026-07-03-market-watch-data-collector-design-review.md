# Market Watch Data Collector Design Review

Review date: 2026-07-03

Reviewed document: `2026-07-03-market-watch-data-collector-design.md`

## Overall Verdict

这份 spec 的方向是对的，可以作为实现入口。它最值得保留的设计选择是：把脚本边界收窄为“采集、归一化、保存、客观摘要”，并明确排除买卖建议、策略标签和内置交易阈值。这比早期把状态判断写进脚本的方案更稳，也更容易测试和长期维护。

建议在开始编码前做一次小修订。当前最大风险不是架构太复杂，而是几个实现契约还不够硬：AKShare 字段映射、交易时间语义、CSV/最新输出写入一致性、窗口统计在缺样本时的行为、以及错误对象结构。如果这些不先写清，第一版代码很可能会在盘中运行时才暴露歧义。

## Strengths

- 边界清楚：Purpose 和 Out of Scope 明确拒绝自动交易、买卖建议、策略标签和阈值，能降低工具“越界解释”的风险。
- 存储路线合理：每日 CSV 作为历史事实源，后续迁移 SQLite，适合轻量 MVP。
- 模块拆分自然：`fetchers`、`normalize`、`storage`、`summary`、`render` 的职责边界基本成立。
- 测试方向正确：把 AKShare fetch 包起来，用 fixture 测归一化、存储、摘要和渲染，是这类脚本最关键的稳定性保障。
- 相比根目录早期思路文档，新 spec 已经有意识移除了“右侧确认、弱势、买点”等策略状态，这是一个重要改进。

## Findings

### P1: AKShare 字段契约需要在 spec 中显式固化

相关位置：原 spec 第 97-108 行、第 195-215 行、第 263-276 行。

spec 现在列出了稳定 schema，但没有写清 AKShare 中文字段到内部字段的逐项映射，也没有区分股票和指数返回字段的差异。尤其是 `speed`、`five_min_change`、`turnover_rate` 这类字段，不同接口、版本或品类不一定都有。指数接口通常没有换手率、涨速、5 分钟涨跌等股票字段。

建议补一个 `Source Field Mapping` 小节，至少包含：

- `stock_zh_a_spot_em()` 字段到 normalized schema 的映射。
- `stock_zh_index_spot_em(symbol=...)` 字段到 normalized schema 的映射。
- 缺失字段的统一行为：CSV 空值、JSON `null`、Markdown 显示为空还是 `-`。
- 字段单位：`change_pct`、`amplitude`、`turnover_rate` 是百分数数值还是小数比例，`volume` 和 `amount` 是否保留 AKShare 原单位。
- 一份来自真实 AKShare 返回结果的 fixture，作为 normalize 测试输入。

外部核对：AKShare 官方文档确认 `stock_zh_index_spot_em` 接口的 `symbol` 取值包括 `沪深重要指数`，返回列包括 `代码`、`名称`、`最新价`、`涨跌额`、`涨跌幅`、`成交量`、`成交额`、`振幅`、`最高`、`最低`、`今开`、`昨收`、`量比`。AKShare 源码/文档片段也显示 `stock_zh_a_spot_em()` 返回字段以东财实时行情列为准。字段契约最好在本项目里 pin 住，而不是依赖记忆。

### P1: 时间模型和交易日语义还不够明确

相关位置：原 spec 第 52-54 行、第 115-122 行、第 230-248 行、第 310-311 行。

spec 说每天写 `YYYY-MM-DD.csv`，并按最近 15、30、60 分钟计算摘要，但没有定义：

- `timestamp` 使用本机时区还是 Asia/Shanghai。
- `trade_date` 如何计算，尤其是本机在美国时区运行时。
- A 股午休 11:30-13:00 是否跨窗口统计。
- 09:30 刚启动时样本不足的输出语义。
- AKShare 返回的源时间戳和本地采样时间哪个作为事实时间。
- 节假日、周末、临时休市如何处理。

建议明确：所有市场时间统一使用 `Asia/Shanghai`；`timestamp` 记录采集完成时间；`trade_date` 按中国交易日计算；窗口按时间范围过滤，而不是假设 60 秒等于一个样本；样本不足时照常输出 `sample_count` 和实际 `first_timestamp`，不要填充或推断。

### P1: CSV 和 latest 输出需要写入一致性规则

相关位置：原 spec 第 52-56 行、第 115-122 行、第 306-312 行。

长时间循环写 CSV 和覆盖 `outputs/latest.*` 时，spec 还没有说明原子写入、重复样本、部分写入失败、进程中断时的行为。第一版虽然轻量，但盘中运行最怕半个 JSON、CSV header 重复、或者重启后同一分钟重复写入不可区分。

建议补充：

- CSV 首次创建写 header，后续 append 不重复 header。
- `outputs/latest.md` 和 `outputs/latest.json` 使用临时文件加 rename 的原子覆盖。
- CSV 行增加可选 `run_id` 或至少定义唯一键：`timestamp + asset_type + code + source`。
- 同一分钟重复采样是否允许；如果允许，使用精确秒级时间区分。
- CSV append 成功但 latest 写失败时如何记录和恢复。

### P1: 错误处理语义存在“整批失败”和“单标的缺失”的边界模糊

相关位置：原 spec 第 306-308 行、第 289-301 行。

spec 同时说 AKShare 失败时跳过该 sample，单个 target 缺失时写 warning。但实际 pipeline 里会有几种不同失败：

- 股票接口失败，指数接口成功。
- 指数接口失败，股票接口成功。
- 接口成功但目标代码不在返回数据中。
- normalize 某个字段失败。
- CSV 写入失败。
- latest JSON 或 Markdown 渲染失败。

建议定义 `errors` 数组对象结构，而不是只说字符串。例如：

```json
{
  "level": "warning",
  "stage": "fetch_indices",
  "code": "SOURCE_TIMEOUT",
  "message": "stock_zh_index_spot_em timed out",
  "target": null,
  "timestamp": "2026-07-03 10:42:30"
}
```

同时明确 partial success 的输出规则：只要有任一资产成功，就写入本次成功记录和 warnings；只有所有 fetch 都失败时才跳过 CSV append，但仍可更新 latest JSON 显示错误，或保留上一份 latest 并打印错误。二者需要择一写清。

### P2: Fetch 循环缺少超时、重试和调度定义

相关位置：原 spec 第 21 行、第 45-58 行、第 306 行。

默认 60 秒循环是合理的，但需要说明调度方式：

- 每次循环间隔是从“上次开始”算，还是从“上次结束”算。
- fetch 超过 60 秒时是否跳过下一轮。
- AKShare 请求 timeout 默认值是多少。
- 是否有一次轻量 retry。
- 连续失败多少次后只记录错误但继续睡眠。

建议 MVP 简化为：单线程串行执行；每轮开始记录 `sample_started_at`；请求 timeout 10-15 秒；失败不阻塞下一轮；下一轮按固定 sleep 计算，不并发重入。

### P2: `market_hours_only` 需要具体交易时段和时区

相关位置：原 spec 第 174 行、第 310-311 行。

这项配置很好，但现在太抽象。建议明确默认只在中国 A 股连续竞价时间采样：09:30-11:30、13:00-15:00，时区 `Asia/Shanghai`。是否包含 09:15-09:25 集合竞价、11:30/15:00 边界点、以及节假日日历，最好也明确第一版行为。

MVP 可以先不引入复杂交易日历，只做工作日加固定时段；但 spec 应说明这是近似规则，并允许手动 `market_hours_only: false`。

### P2: JSON 输出结构需要比示例更完整

相关位置：原 spec 第 285-301 行、第 327-337 行。

JSON 示例里 `current.stocks`、`current.indices` 和 `history_summary.items` 都是空数组，没有展示单条 current record 和 summary item 的最终字段。实现时容易出现 Markdown 用一套字段、JSON 用另一套字段。

建议在 JSON Output 里补两段完整示例：

- 一条 normalized current stock record。
- 一条 index record，展示股票没有的字段如何为 `null`。
- 一条 `history_summary.items` 记录。
- 一条 `errors` 记录。

### P2: 配置验证规则还需要落到可测试条件

相关位置：原 spec 第 146-189 行、第 318 行。

`config.py` 被要求验证配置，但 spec 没有列验证规则。建议至少写清：

- `targets.stocks` 和 `targets.indices` 必须是列表。
- `code`、`name`、`role` 必填。
- `role` 只能是 `primary`、`compare`、`context`。
- 同一 `asset_type + code` 不允许重复。
- `interval_seconds > 0`。
- `history_windows_minutes` 是正整数列表。
- `snapshot_dir`、`latest_markdown`、`latest_json` 不能为空。
- `source.provider` 第一版只允许 `akshare`。

这些规则都能转成低成本单元测试。

### P3: “B-first storage design” 术语不够自解释

相关位置：原 spec 第 42 行。

`B-first storage design` 对读者不够明确。建议改成更直接的表达，例如 “CSV-first storage design”。如果 `B-first` 是内部上下文里的术语，建议在首次出现时解释。

### P3: Acceptance Criteria 可以更贴近可验证命令

相关位置：原 spec 第 327-337 行。

现在验收标准方向没问题，但还不够命令化。建议补充：

- `python watch.py --once` 能完成一次采集、写 CSV、写 latest。
- `python watch.py --loop --interval 60` 能循环运行，并可 `Ctrl+C` 干净退出。
- 测试命令，例如 `pytest`，通过 config、normalize、storage、summary、render 的 fixture 测试。
- 没有网络时，fixture 测试仍可通过。

## Recommended Spec Edits Before Implementation

1. 增加 `Source Field Mapping` 小节，固化 AKShare 字段、单位、缺失字段策略。
2. 增加 `Time Model` 小节，定义 `timestamp`、`trade_date`、时区、市场时段、窗口过滤规则。
3. 增加 `Persistence Contract` 小节，定义 CSV header、append、latest 原子写、重复样本和部分失败。
4. 扩展 `Error Handling`，给出结构化 `errors` 对象和 partial success 策略。
5. 扩展 `JSON Output`，展示完整 current、history summary 和 error item。
6. 把 `Config validation` 规则列成可测试清单。
7. 把 Acceptance Criteria 改成更容易执行的验收命令和结果。

## Suggested MVP Slice

为了避免第一版一下子做成长循环工具，可以把实现切成两步：

1. `--once`：加载 config，fetch，normalize，写当天 CSV，写 latest Markdown/JSON，全部 fixture 测试通过。
2. `--loop`：在 `--once` pipeline 稳定后加循环、market-hours gate、错误持续记录和 Ctrl+C 退出。

这样既不牺牲最终目标，也能更快得到一个可验证的最小闭环。

## References Checked

- AKShare 官方文档，指数实时行情 `stock_zh_index_spot_em`: https://akshare.akfamily.xyz/data/index/index.html
- AKShare GitHub / Context7 文档片段，A 股实时行情 `stock_zh_a_spot_em`: https://github.com/akfamily/akshare
