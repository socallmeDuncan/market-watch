# Market Watch Data Collector Plan Review

Review date: 2026-07-03

Reviewed plan: `2026-07-03-market-watch-data-collector.md`

Related spec review: `../specs/2026-07-03-market-watch-data-collector-design-review.md`

## Overall Verdict

这份 implementation plan 已经接近可执行。它符合 `writing-plans` 的大方向：有文件结构、按任务拆分、先写失败测试、再实现、再验证，并且比原 design spec 更具体地补上了字段映射、结构化 errors、Asia/Shanghai 时间、atomic latest writes、partial success 测试。

但现在还不建议直接交给执行 agent。主要原因不是计划不够细，而是有几处计划内契约不一致：部分配置项被验证但从未生效、一个 render 测试按计划实现后仍会失败、Markdown 窗口标题写死、`runtime.loop` 配置成为死字段。这些都属于“执行到一半才发现要返工”的问题，建议先修订计划再开工。

## Strengths

- 任务顺序合理：先 scaffold，再 config、normalize、storage、summary、render、fetchers，最后组装 CLI。
- TDD 形态清楚：每个核心模块都有先失败、再实现、再通过的步骤。
- 对 spec review 的吸收不错：计划已经加入 `market_timezone`、结构化 `errors`、字段映射、缺失字段处理、partial success、atomic latest 写入。
- 边界保持得住：计划反复强调不加入策略阈值、买卖建议、状态标签。
- 对当前工作区非 git 仓库有说明，commit 步骤不会误导执行者硬提交。

## Findings

### P1: `request_timeout_seconds` 和 `retry_count` 被配置和验证，但没有任何执行路径使用

相关位置：计划第 105-106 行、第 417-418 行、第 481-484 行、第 1815-1824 行、第 2063-2091 行。

计划在配置里新增了 `request_timeout_seconds` 和 `retry_count`，并在 `validate_config` 中校验它们，但 `fetch_stocks()`、`fetch_indices()`、`collect_records()` 都没有接收或使用这些值。执行结果会给用户一种“请求有 timeout/retry 保护”的错觉，实际 AKShare 调用仍可能长时间阻塞，也不会 retry。

建议二选一：

- MVP 不实现 timeout/retry：从 config、测试和 README 中移除这两个字段。
- 实现 timeout/retry：增加 fetcher 或 orchestration 层测试，例如 “第一次 provider 抛错、第二次成功时返回记录”、以及 “超过重试次数后产生 `SOURCE_FETCH_FAILED` error”。如果 AKShare 函数本身不支持 timeout，就不要把 timeout 配置伪装成已经生效的能力。

### P1: Task 6 的 missing-value Markdown 测试按计划实现后会失败

相关位置：计划第 1532-1541 行、第 1602-1611 行。

`test_render_markdown_displays_missing_values_as_dash()` 传入的是 `index_record()`，其中只有 `turnover_rate`、`speed`、`five_min_change` 被设为 `None`。但 `INDEX_COLUMNS` 不渲染这些字段，因此生成的指数表没有任何缺失值，断言 `assert " - " in markdown or "| - |" in markdown` 很可能失败。

建议修改测试 fixture，让一个实际会显示的字段为空，例如：

```python
record = index_record()
record["amount"] = None
markdown = render_markdown(...)
assert "| - |" in markdown or " - " in markdown
```

或者单独用 stock record，把 `five_min_change` 设为 `None`，因为股票表确实会渲染该字段。

### P1: `runtime.loop` 是默认配置的一部分，但 CLI 完全忽略它

相关位置：计划第 101 行、第 413 行、第 2115-2130 行。

默认 `config.yaml` 写了 `runtime.loop: true`，`DEFAULT_CONFIG` 也写了 `"loop": True`，但 `main()` 只看 CLI 的 `--loop`。这会造成行为冲突：配置说 loop，用户运行 `python watch.py` 却执行 once。

建议明确一个单一来源：

- 如果 CLI 是主控制面，就删除 `runtime.loop`，只保留 README 中的 `--once` / `--loop`。
- 如果 config 是主控制面，就让 `main()` 在没有显式 `--once` / `--loop` 时读取 `runtime.loop`。

当前计划两边都写，会让后续维护者猜。

### P1: `market_hours_only` 只约束 loop，不约束 `--once`

相关位置：计划第 102 行、第 2015-2021 行、第 2024-2054 行、第 2136-2144 行、第 2344-2357 行。

计划实现里 `run_loop()` 会检查 `market_hours_only`，但 `run_once()` 不检查。这个设计可以成立，但需要明确：`--once` 是否允许在非交易时段写入 stale sample？原 spec 说 `market_hours_only` 为 true 时避免在 A 股常规交易时段外写重复 stale data，这更像是 loop 约束；但计划没有把这个边界写清。

建议在计划中补一条显式决策：

- `--once` 始终采样，用于手动 smoke test 和调试；`market_hours_only` 只影响 loop。
- 或者 `--once` 也尊重 `market_hours_only`，提供 `--force` 绕过。

没有这个决策，执行结果和用户预期很容易错位。

### P2: Markdown 历史窗口标题写死为 `15 / 30 / 60`

相关位置：计划第 1476-1479 行、第 1526 行、第 1643-1667 行。

`history_windows_minutes` 是可配置项，但 render 测试和实现把标题固定为 `最近 15 / 30 / 60 分钟客观统计`。如果用户配置 `[5, 15]`，JSON 会是 `[5, 15]`，Markdown 却仍显示 `15 / 30 / 60`。

建议把标题从 `history_summary["windows_minutes"]` 动态生成，并增加测试：

```python
history_summary={"windows_minutes": [5, 15], "items": []}
assert "最近 5 / 15 分钟客观统计" in markdown
```

### P2: Summary 只对“窗口内有样本”的资产输出 item，和 spec 的“每个 target 每个窗口”不完全一致

相关位置：计划第 1245-1260 行、第 1293-1312 行。

当前 `summarize_history()` 从已有 CSV rows 推导 asset keys，并且只有 `window_rows` 非空才 append summary item。这意味着某个 configured target 当前缺失、或者某个窗口没有样本时，summary 中没有对应 item。

这可能是可接受的 MVP 行为，但需要写清。原 spec 表述是 “For each configured target and each configured window”，更像是每个 target/window 都应有一个明确结果，哪怕 `sample_count: 0`。

建议计划增加一条决策：

- MVP 只输出有样本的窗口，并依赖 `errors` 表达当前缺失 target。
- 或 summary 接收 configured targets，输出 `sample_count: 0` 的空窗口 item。

### P2: CSV append 和 latest 写入之间没有失败恢复契约

相关位置：计划第 1120-1127 行、第 2029-2052 行。

计划实现了 `latest.md/json` 的 atomic write，这是好事。但 `run_once()` 先 append CSV，再读历史并写 latest。如果 CSV 写成功、latest 写失败，历史已经更新但 latest 可能停留在上一轮；如果 CSV append 半途异常，latest 不会写，但错误也不会被结构化记录。

建议至少在计划中定义 MVP 行为：

- CSV append 异常是否应返回 exit code 1。
- 是否写一个 `errors` latest payload 表示 storage failure。
- 是否接受 CSV 与 latest 不是事务一致的关系。

第一版可以不做事务，但不应该让执行者自己猜。

### P2: Fetcher 测试只覆盖成功过滤，不覆盖字段缺失或 source failure

相关位置：计划第 1755-1790 行、第 1815-1833 行。

`_filter_by_codes()` 在缺少 `代码` 列时返回空 DataFrame，这个行为会在 normalize 阶段变成 `TARGET_MISSING` warnings，而不是更直接的 `SOURCE_FIELD_MISSING`。normalize 本身有缺 `代码` 列测试，但 fetcher 把该错误吞成空表后，真实 pipeline 不会走到 normalize 的缺列错误路径。

建议给 fetchers 或 collect_records 增加一条测试：provider 返回不含 `代码` 的 DataFrame 时，应产生 `SOURCE_FIELD_MISSING` 或明确的 fetch-stage error，而不是把所有 target 都报告成 missing。

### P3: Task 9 有一个条件式修补步骤，不太符合“可线性执行”的计划风格

相关位置：计划第 2263-2268 行。

Task 9 Step 2 说测试预期 PASS，如果失败再执行 Step 3。这不算严重，但对 agentic execution 来说会引入分支。既然 Step 3 的实现更清楚，可以直接把 Task 8 的 `run_loop()` 写成最终版本，或者把 Task 9 改成明确的重构任务，而不是条件式补丁。

### P3: 最终 strategy-language 检查只扫中文禁词

相关位置：计划第 2361-2367 行。

计划的 README 使用了英文 “buy/sell rules”，最终 `rg` 只扫中文禁词，所以它不能证明项目没有英文策略语言。当前 README 那句话是边界声明，不是建议，问题不大；但如果目标是防止策略语言泄漏，建议把英文词也加进去，或者把检查目标限定为 generated outputs 和 implementation，而不是 README 边界说明。

## Recommended Plan Edits

1. 先修 Task 6 missing-value test，让它确实覆盖一个会被 Markdown 渲染的 `None` 字段。
2. 决定 timeout/retry 是否进入 MVP；如果进入，补测试和实现；如果不进入，删配置项。
3. 决定 `runtime.loop` 是否保留；保留则让 CLI 使用它，删除则让配置更干净。
4. 明确 `market_hours_only` 对 `--once` 的语义。
5. 把 Markdown 历史窗口标题改为根据配置动态生成。
6. 明确 summary 对空窗口/缺失 target 的输出策略。
7. 补一个 source DataFrame 缺 `代码` 列的 pipeline-level 测试。

## Execution Readiness

修完以上 P1 后，这份计划可以进入执行。P2/P3 如果暂时不修，也建议至少在计划里写明“这是 MVP 取舍”，这样执行 agent 不会把未定义行为随手定死在代码里。
