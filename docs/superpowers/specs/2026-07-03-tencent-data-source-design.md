# 腾讯/新浪双数据源切换设计

- 日期：2026-07-03
- 状态：已确认，待实现
- 适用项目：market-watch-v1

## 1. 背景与问题

当前实时行情和分钟线的主源是 AKShare 的东方财富接口（`stock_zh_a_spot_em`、`stock_zh_index_spot_em`、`stock_zh_a_hist_min_em` 等）。实测在当前出口 IP（120.225.27.243 山东移动）环境下，东财 push 系列接口出现**漂移性拦截**：

- TCP 连接和 TLS 握手都能成功。
- 服务端在收到 HTTP 请求 0.1 秒后主动断开（`Empty reply from server`）。
- 同一个 host（如 `push2his.eastmoney.com`）在不同时刻表现不同：某次 curl 能拿到 HTTP 200，随后连测 3 次全部 HTTP 000。
- 拦截是按 **path 粒度**，不是 host 粒度：同一个 `push2his.eastmoney.com`，根路径返回 HTTP 404（连接通），`/api/qt/stock/get` 被秒断。
- 直连和走系统代理（127.0.0.1:7897）结果一致，地域（中国山东）不是问题。

后果：盘中 `--loop` 每 60 秒采样一次，主源会频繁撞超时（每次约 10-20 秒）才切到备源，严重拖慢采样节奏，README 第 88-96 行承诺的"东财主源"已经名存实亡。

## 2. 验证过的可用数据源

实测 2026-07-03 收盘前后，以下接口稳定可用：

| 接口 | host / 路径 | 用途 | 个股 | 指数 | ETF |
|---|---|---|---|---|---|
| 腾讯实时 | `qt.gtimg.cn/q=<code>` | 实时快照，88 字段 | ✅ | ✅ | ✅ |
| 腾讯分钟线 | `ifzq.gtimg.cn/appstock/app/kline/mkline?param=<code>,m1,,320` | 当日 1 分钟 K 线，320 条 | ✅ | ✅ | ✅ |
| 新浪全量 | AKShare `stock_zh_a_spot` / `stock_zh_index_spot_sina` | 实时快照备源 | ✅ | ✅ | ✅ |
| 新浪分钟线 | AKShare `stock_zh_a_minute` | 分钟线备源 | ✅ | ✅ | ✅ |

腾讯实时返回示例（协创 `sz300857`，共 88 字段）：

```
v_sz300857="51~协创数据~300857~300.41~293.59~293.59~173803~..."
```

腾讯实时字段索引表（0 基，实测 2026-07-03，实现时按此映射）：

| 索引 | 含义 | 示例值 | 映射到中文列 |
|---|---|---|---|
| 1 | 名称 | 协创数据 | 名称 |
| 2 | 代码 | 300857 | 代码 |
| 3 | 最新价 | 300.41 | 最新价 |
| 4 | 昨收 | 293.59 | 昨收 |
| 5 | 今开 | 293.59 | 今开 |
| 6 | 成交量(手) | 173803 | 成交量 |
| 31 | 涨跌额 | 6.82 | 涨跌额 |
| 32 | 涨跌幅(%) | 2.32 | 涨跌幅 |
| 33 | 最高 | 309.80 | 最高 |
| 34 | 最低 | 289.23 | 最低 |
| 37 | 成交额(万) | 520870 | 成交额（注意单位是万，需 ×10000 转元） |
| 38 | 换手率(%) | 3.57 | 换手率 |
| 39 | 市盈率 | 84.22 | 市盈率-动态 |
| 43 | 振幅(%) | 7.01 | 振幅 |
| 44 | 流通市值(亿) | 1462.58 | 流通市值（注意单位是亿） |
| 45 | 总市值(亿) | 1470.10 | 总市值（注意单位是亿） |

**单位坑**：腾讯成交额 [37] 单位是"万"，需 ×10000 转成元才能与东财/新浪的"元"对齐；市值 [44][45] 单位是"亿"，需 ×1e8 转元。spec 第 12 节风险表里已隐含，此处显式标出。

字段不全（如指数无换手率、ETF 无市盈率）对应索引返回空串，解析时填 `None`。

腾讯分钟线返回示例（`mkline`，末条）：

```
['202607031500', '300.40', '300.41', '300.41', '300.40', '820.00', {}, '1.68']
   ↑时间YYYYMMDDHHMM ↑开   ↑收   ↑高   ↑低   ↑成交量     {} ↑成交额
```

## 3. 目标

1. 让盘中采集主路径（实时快照 + 分钟线 backfill）稳定可用。
2. 实时和分钟线都切换到腾讯作为主源。
3. 新浪作为腾讯的备源兜底。
4. 东财/akshare 分支代码原样保留休眠，通过一行配置即可切回。

## 4. 不做（YAGNI）

- **不做浏览器抓取**：腾讯/新浪接口不需要 token、不需要登录，纯 HTTP 请求即可。
- **不做容器化部署**：Docker 是部署方式，不改变出口 IP，解决不了反爬拦截。官方文档明确 Docker 是给"想用 HTTP API 跨语言调用"的人用的，与抓数据无关。
- **不新增 `fetchers_tencent.py` 并行模块**：双模块（fetchers.py + fetchers_tencent.py）的维护成本高于在 fetchers.py 内部加一个 dispatcher。watch.py 已经用 `fetch_stocks()` 等抽象函数调用，不需要第二个模块入口。

## 5. 架构改动范围

核心洞察：现有架构已经用"**中文列名的 DataFrame**"这个稳定契约隔离了数据源。`normalize.py`（第 41-78 行的 field_map）只认 `最新价/涨跌幅/今开` 这些中文列名，根本不关心数据来自 akshare 还是腾讯。所以改动可以收敛在数据层。

```
config.yaml  source.provider: "tencent"   (默认，原值 "akshare")
   │
   ▼
fetchers.py  新增 dispatcher: 按 provider 选源
   ├── provider=tencent → _tencent_stocks / _tencent_indices / _tencent_etfs
   │                      / _tencent_stock_intraday / _tencent_index_intraday
   │                      / _tencent_etf_intraday     (全部新增)
   │                      契约: 返回中文列名 DataFrame
   │                      实时主源 qt.gtimg + 备源 新浪全量
   │                      分钟线主源 mkline + 备源 新浪分钟线
   │
   └── provider=akshare → 现有 _em + sina 逻辑原样保留 (重命名为内部函数)
   │
   ▼ (契约不变: 中文列名 DataFrame)
normalize.py / watch.py / render.py / storage.py   0 改动
```

改动文件清单：

| 文件 | 改动 | 量 |
|---|---|---|
| `market_watch/fetchers.py` | 新增腾讯模块 + dispatcher；现有 akshare 逻辑重命名为内部函数（如 `_akshare_stocks`）保留 | 新增约 200 行 |
| `market_watch/config.py` | `DEFAULT_CONFIG.source.provider` 默认值改 `tencent`；`validate_config` 允许 `tencent` 合法值 | 约 5 行 |
| `config.yaml` | `source.provider` 改 `tencent`；保留 `stock_source` 字段（akshare 分支用） | 约 2 行 |
| `market_watch/normalize.py` | **0 改动** | 0 |
| `watch.py` | **0 改动**（已经用 `fetch_stocks()` 抽象调用） | 0 |
| `market_watch/render.py` / `storage.py` / `summary.py` / `intraday.py` | **0 改动** | 0 |

## 6. 关键契约：中文列名 DataFrame

腾讯模块所有函数的返回值，必须与 akshare 分支的返回值在列名上完全一致，这样 normalize.py 无需感知数据源切换。

### 6.1 实时快照契约

个股（对齐 `normalize.COMMON_FIELD_MAP` + `STOCK_ONLY_FIELD_MAP`）：

```
代码, 名称, 最新价, 涨跌幅, 涨跌额, 今开, 最高, 最低, 昨收,
成交量, 成交额, 振幅, 换手率, 量比, 市盈率-动态, 市净率,
总市值, 流通市值, 涨速, 5分钟涨跌, 60日涨跌幅, 年初至今涨跌幅
```

腾讯 `~` 字段不全的部分（如 60日涨跌幅、年初至今涨跌幅、5分钟涨跌、涨速、量比、市净率等），对应列填 `None` / `pd.NA`，normalize.py 的 `_parse_optional_number` 已经能处理空值。

**完整映射表见第 2 节字段索引表**。实现 `_tencent_stocks` 时直接按该表索引取值，不再二次探测。

ETF 列名变体（对齐 `normalize.ETF_FIELD_MAP`）：`开盘价 / 最高价 / 最低价`（带"价"字），其余同上。

### 6.2 分钟线契约

对齐现有 `_convert_sina_minute_frame` 的输出列名：

```
时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额
```

腾讯 mkline 每条 `[时间, 开, 收, 高, 低, 量, {}, 额]` 直接映射，注意腾讯是"开收高低"顺序，而契约是"开高低收"顺序，需要重排。`{}` 字段丢弃。`_market_watch_source` 标记列填 `tencent_mkline_1m`。

### 6.3 source 字段标记（硬约束）

每条数据**必须**通过 `_market_watch_source` 列标记来源，最终写入 record 的 `source` 字段。

**为什么是硬约束**：normalize.py 第 251 行是 `str(row.get("_market_watch_source") or SOURCE_NAME)`，而 `SOURCE_NAME = "akshare_em"` 是硬编码默认值。如果腾讯 DataFrame 漏设 `_market_watch_source` 列，source 字段会静默 fallback 成 `akshare_em`，造成数据来源标记错误（明明是腾讯数据却标成东财）。因此腾讯/新浪路径的 DataFrame **必须**显式设置此列。

| 数据路径 | `_market_watch_source` 值 |
|---|---|
| 腾讯实时 | `tencent_qt` |
| 腾讯分钟线 | `tencent_mkline_1m` |
| 新浪实时（备源） | `sina_spot` |
| 新浪分钟线（备源） | `sina_minute_1m` |
| akshare 东财（休眠分支） | 保留原 `akshare_em` 等 |

## 7. 代码 / secid 映射规则

腾讯接口的代码需要带交易所前缀。

### 7.1 前缀规则

| 代码特征 | 前缀 | 示例 |
|---|---|---|
| 个股 6 开头（沪市） | `sh` | `sh600000` |
| 个股 0/3 开头（深市，含创业板 300） | `sz` | `sz300857` |
| 指数 000 开头（上证系列） | `sh` | `sh000001`、`sh000300` |
| 指数 399 开头（深证系列） | `sz` | `sz399006`、`sz399001` |
| ETF 5 开头（沪市） | `sh` | `sh512480`、`sh588000` |
| ETF 1 开头（深市） | `sz` | `sz159915` |

注意：`000688`（科创50指数）按指数规则走 `sh000688`，不是个股的深市。区分依据是 `config.yaml` 里它在 `indices` 还是 `stocks` 段，由调用方传入 asset_type 决定前缀函数。

前缀函数签名约定（fetchers.py 内部新增）：

```python
def _tencent_prefix(code: str, asset_type: str) -> str:
    """asset_type ∈ {"stock", "index", "etf"}，返回 "sh" 或 "sz"。"""
```

各 fetcher 调用时传入对应的 asset_type（`_tencent_stocks` 传 `"stock"`，`_tencent_indices` 传 `"index"`，`_tencent_etfs` 传 `"etf"`），ETF 与个股的前缀规则一致（5→sh，1→sz），但语义上分开传以便未来 ETF 有独立规则时不污染个股逻辑。

### 7.2 接口 URL 模板

实时：
```
https://qt.gtimg.cn/q=<prefix><code>
```

分钟线：
```
https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=<prefix><code>,m1,,320
```

## 8. Fallback 链

### 8.1 实时快照

```
provider=tencent:
  主源: qt.gtimg.cn 逐只查询 → 成功则返回
  ↓ (失败: 网络错误 / 字段缺失 / 非法响应)
  备源: 新浪 stock_zh_a_spot 全量拉取 + 过滤
  ↓ (失败)
  抛 RuntimeError(同现有 akshare 分支的错误聚合风格)
```

腾讯实时是**逐只查询**（`q=` 一次一只），新浪备源是**全量拉取后过滤**（一次拉全市场再筛）。两种粒度不同，但 fallback 时用新浪全量兜底是可接受的——新浪全量实测 5527 行耗时约 10 秒，作为兜底可接受。

### 8.2 分钟线

```
provider=tencent:
  主源: mkline m1 逐只查询 → 成功则返回
  ↓ (失败)
  备源: 新浪 stock_zh_a_minute
  ↓ (失败)
  抛 RuntimeError
```

注意：新浪分钟线接口的代码格式与 akshare 一致（`_stock_sina_symbol` / `_index_sina_symbol` 已实现），复用现有逻辑。

### 8.3 provider=akshare 分支

保持现有行为不变（东财主源 → 新浪备源）。虽然东财当前不可用，但代码保留，未来 IP 环境变化时可一行配置切回验证。

## 9. 配置改动

### 9.1 DEFAULT_CONFIG（config.py）

```python
"source": {
    "provider": "tencent",          # 原 "akshare"，改为 "tencent" 作为默认
    "stock_source": "eastmoney_with_sina_fallback",  # 保留，仅 akshare 分支用
    "index_symbol": "沪深重要指数",   # 保留，仅 akshare 分支用
},
```

### 9.2 validate_config（config.py）

```python
provider = _require_non_empty_string(source, "provider")
if provider not in {"akshare", "tencent"}:
    raise ConfigError("source.provider must be akshare or tencent")
```

原代码只允许 `akshare`，现在加 `tencent`。

### 9.3 config.yaml

```yaml
source:
  provider: "tencent"
  stock_source: "eastmoney_with_sina_fallback"  # 仅 provider=akshare 时生效
  index_symbol: "沪深重要指数"                    # 仅 provider=akshare 时生效
```

### 9.4 provider 如何传到 fetchers

watch.py 在 `collect_records` 里读 `config["source"]["provider"]`，传给 `fetch_stocks(codes, provider=...)`，复用现有的 `provider` 参数。

现有 `fetch_stocks(codes, provider=None)` 已经预留了 provider 参数（语义原本是"数据源句柄对象"，传 None 时走默认 akshare）。本次扩展它的含义为"数据源标识字符串"（`"tencent"` / `"akshare"`），watch.py 显式传入，fetchers 内部按字符串分发。

不采用"fetchers.py 内部读 config"的方案——那会让 fetchers 引入 config 依赖、职责变模糊。watch.py 作为调度层负责把配置翻译成 fetcher 参数，fetchers 只认传入的 provider 字符串，单向依赖更清晰。

注意：现有 `provider` 参数的 None 分支（默认 akshare）要保留，作为向后兼容；只有显式传 `"tencent"` / `"akshare"` 字符串时才走新分发逻辑。

## 10. 测试策略

### 10.1 腾讯路径单测（mock，不依赖外网）

- `tests/test_fetchers.py` 新增：
  - mock `requests.get` 返回构造的 `~` 分隔串，验证字段索引解析正确（最新价、涨跌幅、最高、最低、成交额、换手率）。
  - mock mkline 返回 JSON，验证"开收高低" → "开高低收" 重排、`{}` 字段丢弃、source 标记。
  - 代码前缀函数单测：`300857→sz`、`600000→sh`、`000001` 指数→`sh`、`512480`ETF→`sh`。
  - 缺失字段容错：腾讯字段不全时填 None，不抛异常。
  - 主源失败 fallback：mock 腾讯抛异常，验证切到新浪备源。

### 10.2 akshare 路径测试

- 现有 `tests/test_fetchers.py` 的 akshare 测试全部保留，确保休眠分支不退化。

### 10.3 配置测试

- `tests/test_config.py`：验证 `provider: tencent` 合法、`provider: foo` 报错、默认值为 `tencent`。

### 10.4 不写真实外网集成测试

腾讯/新浪字段顺序可能漂移，真实接口测试会让 CI 抖动。单测用固定 fixture 覆盖字段映射逻辑即可。字段漂移由"运行时报错或数据异常"发现，不在 CI 层面守。

## 11. HTTP 请求细节

### 11.1 Session 复用

腾讯接口建议用 `requests.Session()` 并设置 `trust_env = False`，避免 macOS 系统代理（127.0.0.1:7897）干扰。实测直连腾讯稳定，不需要代理。

### 11.2 请求头

```python
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://gu.qq.com/",   # 腾讯要求 Referer
}
```

新浪 `hq.sinajs.cn` 需要 Referer `https://finance.sina.com.cn`（否则 403）。

### 11.3 超时

复用 config 的 `runtime.request_timeout_seconds`（默认 15 秒）。腾讯单只查询很快（实测 <0.5 秒），15 秒足够。

### 11.4 重试

复用 watch.py 的 `_fetch_with_retry` / `_fetch_intraday_with_retry`，不在 fetchers 层重复实现重试。

## 12. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 腾讯改 `~` 字段顺序导致数据错位 | 单测覆盖关键字段索引；解析时对关键字段（最新价、代码）做 sanity check，异常时报错而非静默 |
| 腾讯也被拦（小概率） | 新浪备源兜底；最坏情况 `provider: akshare` 切回（东财当前也不稳，但保留逃生通道） |
| 腾讯实时逐只查询慢（目标 30+ 只） | 实测单只 <0.5 秒，30 只串行约 15 秒，可接受；若未来目标增多，可改并发或用新浪全量 |
| 新浪备源代码带 sh/sz 前缀 | 现有 `_filter_by_codes` 已处理，无需改动 |
| mkline 返回的 `{}` 字段 | 解析时按索引跳过，不写入 DataFrame |

## 13. 验收标准

1. `config.yaml` 设 `provider: tencent`，`python3 watch.py --once` 能成功抓取个股/指数/ETF 实时行情，输出 `outputs/latest.md` 和 `outputs/latest.json`，数据字段非空且与新浪交叉验证一致。
2. `python3 watch.py --backfill-today` 能抓到当日 1 分钟 K 线，输出 `data/intraday/2026-07-03-1m.csv` 和 `outputs/today.md`。
3. `config.yaml` 设 `provider: akshare`，行为与改动前完全一致（休眠分支不退化）。
4. 腾讯主源模拟失败时，自动切新浪备源，`source` 字段标记正确。
5. 全部单测通过（腾讯新增 + akshare 保留 + config）。
6. `normalize.py`、`watch.py`、`render.py`、`storage.py` 零改动（git diff 验证）。

## 14. 实现顺序建议

1. 先重构 `fetchers.py`：把现有 akshare 逻辑重命名为 `_akshare_*` 内部函数，外部 `fetch_stocks/indices/etfs/intraday` 改成 dispatcher（此时 provider 只支持 akshare，行为不变）。这一步保证不破坏现状。
2. 加腾讯模块：实现 `_tencent_*` 函数 + 代码前缀函数，返回中文列名 DataFrame。
3. dispatcher 接入腾讯分支。
4. 改 config 默认值和校验。
5. 写腾讯路径单测。
6. 端到端验证（验收标准 1-3）。
7. 检查 git diff 确认中间层零改动（验收标准 6）。

每一步都可独立提交、可回退。
