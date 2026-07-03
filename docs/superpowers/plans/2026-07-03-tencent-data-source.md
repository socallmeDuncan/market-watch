# 腾讯/新浪双数据源切换 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 market-watch 的实时行情和分钟线数据源从失效的东财 push 接口切换到腾讯（主源）+ 新浪（备源），akshare/东财分支代码保留休眠、配置可切回。

**Architecture:** 改动收敛在 `fetchers.py`（新增腾讯模块 + dispatcher）和 `config.py`（默认 provider 改 tencent）。normalize.py / watch.py / render.py / storage.py 因"中文列名 DataFrame"契约而零改动。关键设计：`provider` 参数保持现有"对象语义"（兼容全部现有 mock 测试），新增 `source` 字符串参数（`"tencent"` / `"akshare"`）做分发。

**Tech Stack:** Python 3.9, requests, pandas, pyyaml, pytest

**Spec:** `docs/superpowers/specs/2026-07-03-tencent-data-source-design.md`

---

## 设计澄清（实现前必读）

spec 第 9.4 节原说"扩展 provider 参数为字符串"，但实测现有 `tests/test_fetchers.py` 全部把 provider 当**对象**传（如 `fetch_stocks([...], provider=StockProvider())`）。如果改 provider 为字符串语义，会破坏所有现有测试。

**调整后的契约**（更干净，向后兼容）：

- `provider` 参数：**保持对象语义不变**，用于注入测试 mock。生产环境传 `None`（默认），fetchers 内部按 source 决定 import akshare 还是走 requests。
- `source` 参数：**新增字符串参数**，默认 `None`。`None` 时按 config 默认值（tencent）走；显式传 `"tencent"` / `"akshare"` 时走对应分支。
- watch.py 读 `config["source"]["provider"]`，作为 `source=` 传给 fetcher。

签名变化（仅新增 source 参数，旧调用方式全部兼容）：

```python
def fetch_stocks(codes, provider=None, *, source=None): ...
def fetch_indices(codes, symbol, provider=None, *, source=None): ...
def fetch_etfs(codes, provider=None, *, source=None): ...
def fetch_stock_intraday(code, start, end, *, provider=None, source=None): ...
def fetch_index_intraday(code, start, end, *, provider=None, source=None): ...
def fetch_etf_intraday(code, start, end, *, provider=None, source=None): ...
```

---

## 文件结构

| 文件 | 责任 | 改动 |
|---|---|---|
| `market_watch/fetchers.py` | 数据源抓取 + dispatcher | 重构 + 新增腾讯模块 |
| `market_watch/config.py` | 配置加载校验 | 默认值 + 校验合法值 |
| `config.yaml` | 运行配置 | provider 改 tencent |
| `watch.py` | 调度入口 | collect_records 传 source 参数 |
| `tests/test_fetchers.py` | fetcher 测试 | 新增腾讯路径测试 + 保留 akshare 测试 |
| `tests/test_config.py` | config 测试 | 新增 provider 校验测试 |
| `tests/conftest.py` | 测试 fixture | sample_config_dict 的 provider 默认值 |

**不改动**：`market_watch/normalize.py`、`market_watch/render.py`、`market_watch/storage.py`、`market_watch/summary.py`、`market_watch/intraday.py`。

---

## Task 1: Config 支持 tencent provider

**Files:**
- Modify: `market_watch/config.py:31-36` (DEFAULT_CONFIG)
- Modify: `market_watch/config.py:109-114` (validate_config 的 source 校验)
- Modify: `tests/conftest.py:41` (sample_config_dict fixture)
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试 — provider=tencent 合法**

在 `tests/test_config.py` 末尾追加：

```python
def test_validate_config_accepts_tencent_provider(sample_config_dict: dict) -> None:
    sample_config_dict["source"]["provider"] = "tencent"

    validate_config(sample_config_dict)


def test_validate_config_rejects_unknown_provider(sample_config_dict: dict) -> None:
    sample_config_dict["source"]["provider"] = "unknown_src"

    with pytest.raises(ConfigError, match="provider must be"):
        validate_config(sample_config_dict)


def test_default_config_uses_tencent_provider() -> None:
    from market_watch.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["source"]["provider"] == "tencent"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_config.py -k "tencent_provider or unknown_provider or default_config_uses_tencent" -v`
Expected: 3 个测试 FAIL（默认值仍是 akshare，校验只接受 akshare）

- [ ] **Step 3: 改 DEFAULT_CONFIG 默认值**

`market_watch/config.py` 第 31-35 行，把 `"provider": "akshare"` 改为 `"provider": "tencent"`：

```python
    "source": {
        "provider": "tencent",
        "stock_source": "eastmoney_with_sina_fallback",
        "index_symbol": "沪深重要指数",
    },
```

- [ ] **Step 4: 改 validate_config 接受 tencent**

`market_watch/config.py` 第 109-114 行，原代码：

```python
    source = _require_mapping(config, "source")
    provider = _require_non_empty_string(source, "provider")
    if provider != "akshare":
        raise ConfigError("source.provider must be akshare")
    if indices:
        _require_non_empty_string(source, "index_symbol")
```

改为：

```python
    source = _require_mapping(config, "source")
    provider = _require_non_empty_string(source, "provider")
    if provider not in {"akshare", "tencent"}:
        raise ConfigError("source.provider must be akshare or tencent")
    if indices:
        _require_non_empty_string(source, "index_symbol")
```

- [ ] **Step 5: 改 conftest fixture 默认值**

`tests/conftest.py` 第 41 行，把 `"provider": "akshare"` 改为 `"provider": "tencent"`，使所有用到 sample_config_dict 的测试默认走 tencent（与新默认值一致）：

```python
        "source": {
            "provider": "tencent",
            "stock_source": "eastmoney_with_sina_fallback",
            "index_symbol": "沪深重要指数",
        },
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: 全部 PASS（包括新增 3 个 + 原有全部）

- [ ] **Step 7: 提交**

```bash
git add market_watch/config.py tests/conftest.py tests/test_config.py
git commit -m "feat(config): support tencent as data source provider"
```

---

## Task 2: fetchers 加 source 参数（保持现有行为不变）

这一步只改签名，把 `source` 参数加到所有 fetch 函数，但暂时不实现分发逻辑——source=None 或 source="akshare" 时行为完全不变。目的是建立参数骨架，让后续 task 能挂载腾讯分支。

**Files:**
- Modify: `market_watch/fetchers.py` (6 个 fetch 函数签名)
- Modify: `tests/test_fetchers.py` (确认现有测试仍通过)

- [ ] **Step 1: 先确认现有测试基线全绿**

Run: `python3 -m pytest tests/test_fetchers.py -v`
Expected: 全部 PASS（记录通过数，作为回归基线）

- [ ] **Step 2: 给 fetch_stocks 加 source 参数**

`market_watch/fetchers.py` 第 14 行，函数签名从：

```python
def fetch_stocks(codes: Iterable[str], provider: Any | None = None) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
```

改为（注意：原代码里局部变量名 `source` 和我们要加的参数 `source` 冲突，把局部变量改名为 `akshare_module`）：

```python
def fetch_stocks(
    codes: Iterable[str],
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_stocks_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = _with_source(akshare_module.stock_zh_a_spot_em(), "akshare_em")
        return _filter_by_codes(frame, codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(akshare_module.stock_zh_a_spot(), "akshare_sina_spot")
            return _filter_by_codes(frame, codes)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney stock fetch failed: {primary_exc}; "
                f"Sina stock fetch failed: {fallback_exc}"
            ) from fallback_exc
```

注意：`_fetch_stocks_tencent` 此时还未实现，会在 Task 3 实现。但函数体里 `if source == "tencent"` 这一行先写上，本 task 不会触发它（现有测试都传 source=None）。

- [ ] **Step 3: 同样改 fetch_indices 签名**

`market_watch/fetchers.py` 第 30-31 行，从：

```python
def fetch_indices(
    codes: Iterable[str], symbol: str, provider: Any | None = None
) -> pd.DataFrame:
    source = provider if provider is not None else _import_akshare()
```

改为：

```python
def fetch_indices(
    codes: Iterable[str],
    symbol: str,
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_indices_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
```

后续 akshare 逻辑体里所有 `source.xxx()` 调用改为 `akshare_module.xxx()`。原函数体内 `source` 出现的地方都要改名。完整改后的函数（替换 fetchers.py 第 30-65 行整段）：

```python
def fetch_indices(
    codes: Iterable[str],
    symbol: str,
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_indices_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    requested_codes = [str(code) for code in codes]
    try:
        frame = _with_source(akshare_module.stock_zh_index_spot_em(symbol=symbol), "akshare_em")
        filtered = _filter_by_codes(frame, requested_codes)
    except Exception as primary_exc:
        try:
            frame = _with_source(
                akshare_module.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
            )
            return _filter_by_codes(frame, requested_codes)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney index fetch failed: {primary_exc}; "
                f"Sina index fetch failed: {fallback_exc}"
            ) from fallback_exc

    missing_codes = _missing_codes(filtered, requested_codes)
    if not missing_codes:
        return filtered

    try:
        fallback_frame = _with_source(
            akshare_module.stock_zh_index_spot_sina(), "akshare_sina_index_spot"
        )
        fallback_filtered = _filter_by_codes(fallback_frame, missing_codes)
    except Exception:
        return filtered

    return _filter_by_codes(
        pd.concat([filtered, fallback_filtered], ignore_index=True),
        requested_codes,
    )
```

- [ ] **Step 4: 同样改 fetch_etfs 签名**

`market_watch/fetchers.py` 第 68-71 行：

```python
def fetch_etfs(
    codes: Iterable[str],
    provider: Any | None = None,
    *,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_etfs_tencent(codes)
    akshare_module = provider if provider is not None else _import_akshare()
    frame = _with_source(akshare_module.fund_etf_spot_em(), "akshare_em_etf_spot")
    return _filter_by_codes(frame, codes)
```

- [ ] **Step 5: 同样改 fetch_stock_intraday 签名**

`market_watch/fetchers.py` 第 75-104 行，原 `source = provider if ...` 改名 + 加 source 参数 + 加 tencent 分发：

```python
def fetch_stock_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="stock")
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = akshare_module.stock_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            adjust="",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = akshare_module.stock_zh_a_minute(
                symbol=_stock_sina_symbol(code),
                period="1",
                adjust="",
            )
            return _convert_sina_minute_frame(frame, start=start, end=end)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney stock minute fetch failed: {primary_exc}; "
                f"Sina stock minute fetch failed: {fallback_exc}"
            ) from fallback_exc
```

- [ ] **Step 6: 同样改 fetch_index_intraday 签名**

`market_watch/fetchers.py` 第 107-135 行：

```python
def fetch_index_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="index")
    akshare_module = provider if provider is not None else _import_akshare()
    try:
        frame = akshare_module.index_zh_a_hist_min_em(
            symbol=str(code),
            period="1",
            start_date=start,
            end_date=end,
        )
        return _with_source(frame, "akshare_em_intraday_1m")
    except Exception as primary_exc:
        try:
            frame = akshare_module.stock_zh_a_minute(
                symbol=_index_sina_symbol(code),
                period="1",
                adjust="",
            )
            return _convert_sina_minute_frame(frame, start=start, end=end)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Eastmoney index minute fetch failed: {primary_exc}; "
                f"Sina index minute fetch failed: {fallback_exc}"
            ) from fallback_exc
```

- [ ] **Step 7: 同样改 fetch_etf_intraday 签名**

`market_watch/fetchers.py` 第 138-153 行：

```python
def fetch_etf_intraday(
    code: str,
    start: str,
    end: str,
    *,
    provider: Any | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    if source == "tencent":
        return _fetch_intraday_tencent(code, start, end, asset_type="etf")
    akshare_module = provider if provider is not None else _import_akshare()
    frame = akshare_module.fund_etf_hist_min_em(
        symbol=str(code),
        period="1",
        adjust="",
        start_date=start,
        end_date=end,
    )
    return _with_source(frame, "akshare_em_etf_intraday_1m")
```

- [ ] **Step 8: 运行测试确认 akshare 路径未退化**

Run: `python3 -m pytest tests/test_fetchers.py -v`
Expected: 全部 PASS（数量与 Step 1 基线一致）。腾讯分支函数 `_fetch_*_tencent` 此时还未定义，但因为现有测试都不传 `source="tencent"`，不会触发 NameError。

- [ ] **Step 9: 提交**

```bash
git add market_watch/fetchers.py
git commit -m "refactor(fetchers): add source param, rename local var to akshare_module"
```

---

## Task 3: 实现腾讯代码前缀函数

腾讯接口需要带交易所前缀的代码（如 `sz300857`）。这是腾讯模块的基础工具函数，先单独实现并测试。

**Files:**
- Modify: `market_watch/fetchers.py` (新增 `_tencent_prefix`)
- Test: `tests/test_fetchers.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_fetchers.py` 顶部 import 区追加：

```python
from market_watch.fetchers import _tencent_prefix
```

在文件末尾追加测试：

```python
def test_tencent_prefix_stock_chuangye() -> None:
    assert _tencent_prefix("300857", "stock") == "sz"


def test_tencent_prefix_stock_hushi() -> None:
    assert _tencent_prefix("600000", "stock") == "sh"


def test_tencent_prefix_index_shanghai_series() -> None:
    assert _tencent_prefix("000001", "index") == "sh"
    assert _tencent_prefix("000300", "index") == "sh"
    assert _tencent_prefix("000688", "index") == "sh"


def test_tencent_prefix_index_shenzhen_series() -> None:
    assert _tencent_prefix("399006", "index") == "sz"
    assert _tencent_prefix("399001", "index") == "sz"


def test_tencent_prefix_etf_hushi() -> None:
    assert _tencent_prefix("512480", "etf") == "sh"
    assert _tencent_prefix("588000", "etf") == "sh"


def test_tencent_prefix_etf_shenshi() -> None:
    assert _tencent_prefix("159915", "etf") == "sz"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_fetchers.py -k "tencent_prefix" -v`
Expected: 7 个测试 FAIL（`_tencent_prefix` 未定义，ImportError）

- [ ] **Step 3: 实现 _tencent_prefix**

在 `market_watch/fetchers.py` 的 `_import_akshare` 函数**之前**（文件末尾附近）新增：

```python
def _tencent_prefix(code: str, asset_type: str) -> str:
    """Return "sh" or "sz" for a given code based on asset type.

    asset_type ∈ {"stock", "index", "etf"}.
    Rules (see spec section 7.1):
      stock: 6开头->sh, 0/3开头->sz
      index: 000/001/002/003开头->sh, 399开头->sz
      etf:   5开头->sh, 1开头->sz
    """
    normalized = str(code).strip()
    if asset_type == "index":
        if normalized.startswith("399"):
            return "sz"
        return "sh"
    # stock and etf share the same prefix rule
    if normalized.startswith(("5", "6", "9")):
        return "sh"
    return "sz"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_fetchers.py -k "tencent_prefix" -v`
Expected: 7 个 PASS

- [ ] **Step 5: 提交**

```bash
git add market_watch/fetchers.py tests/test_fetchers.py
git commit -m "feat(fetchers): add tencent code prefix function"
```

---

## Task 4: 实现腾讯实时快照（个股 + 指数 + ETF）

腾讯 `qt.gtimg.cn/q=` 返回 `v_sz300857="51~协创数据~..."` 格式，按 `~` 分隔，字段索引见 spec 第 2 节表。

**Files:**
- Modify: `market_watch/fetchers.py` (新增 `_fetch_stocks_tencent` / `_fetch_indices_tencent` / `_fetch_etfs_tencent` + 解析辅助函数)
- Test: `tests/test_fetchers.py`

- [ ] **Step 1: 写失败测试 — 腾讯个股实时**

在 `tests/test_fetchers.py` 顶部 import 区追加（如果 `unittest.mock` 未导入）：

```python
from unittest.mock import patch, MagicMock
```

在文件末尾追加测试：

```python
TENCENT_STOCK_RESPONSE = (
    'v_sz300857="51~协创数据~300857~300.41~293.59~293.59~173803~92752~81051'
    '~300.40~50~300.39~10~300.38~14~300.37~3~300.35~14~300.41~0~300.50~67'
    '~300.51~11~300.53~29~300.55~113~~20260703161421~6.82~2.32~309.80~289.23'
    '~300.41/173803/5208699946~173803~520870~3.57~84.22~~309.80~289.23~7.01'
    '~1462.58~1470.10~28.72~352.31";'
)


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_parses_fields(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert len(result) == 1
    row = result.iloc[0]
    assert row["代码"] == "300857"
    assert row["名称"] == "协创数据"
    assert row["最新价"] == 300.41
    assert row["昨收"] == 293.59
    assert row["今开"] == 293.59
    assert row["最高"] == 309.80
    assert row["最低"] == 289.23
    assert row["涨跌额"] == 6.82
    assert row["涨跌幅"] == 2.32
    assert row["成交量"] == 173803
    assert row["换手率"] == 3.57
    assert row["振幅"] == 7.01
    assert row["市盈率-动态"] == 84.22
    assert row["_market_watch_source"] == "tencent_qt"


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_amount_in_yuan_not_wan(mock_requests):
    """成交额[37]腾讯单位是万，必须×10000转成元."""
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert result.iloc[0]["成交额"] == 520870 * 10000


@patch("market_watch.fetchers.requests")
def test_fetch_stocks_tencent_market_value_in_yuan(mock_requests):
    """总市值[45]/流通市值[44]腾讯单位是亿，必须×1e8转成元."""
    mock_resp = MagicMock()
    mock_resp.text = TENCENT_STOCK_RESPONSE
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stocks(["300857"], source="tencent")

    assert result.iloc[0]["总市值"] == 1470.10 * 1e8
    assert result.iloc[0]["流通市值"] == 1462.58 * 1e8
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_fetchers.py -k "fetch_stocks_tencent" -v`
Expected: 3 个 FAIL（`_fetch_stocks_tencent` 未实现）

- [ ] **Step 3: 实现腾讯解析辅助函数**

在 `market_watch/fetchers.py` 顶部 `import pandas as pd` 之后，确认有 `import requests`（如果没有则加）。然后在 `_tencent_prefix` 函数**之后**新增：

```python
TENCENT_QT_URL = "https://qt.gtimg.cn/q="
TENCENT_QT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://gu.qq.com/",
}

# 腾讯 qt 字段索引 → 中文列名。单位坑：成交额[37]是万，市值[44][45]是亿。
# 见 spec 第 2 节字段索引表。
_TENCENT_QT_FIELD_INDEX = {
    1: "名称",
    2: "代码",
    3: "最新价",
    4: "昨收",
    5: "今开",
    6: "成交量",
    31: "涨跌额",
    32: "涨跌幅",
    33: "最高",
    34: "最低",
    37: "成交额",
    38: "换手率",
    39: "市盈率-动态",
    43: "振幅",
    44: "流通市值",
    45: "总市值",
}


def _tencent_qt_session() -> Any:
    session = requests.Session()
    session.trust_env = False
    return session


def _parse_tencent_qt_response(text: str) -> dict[str, Any]:
    """Parse a single v_code="..."; response into a {col: value} dict.

    Returns empty dict if response is malformed or empty quote.
    """
    if "=" not in text:
        return {}
    payload = text.split("=", 1)[1].strip().rstrip(";").strip('"')
    parts = payload.split("~")
    if len(parts) < 50:
        return {}
    row: dict[str, Any] = {}
    for index, col in _TENCENT_QT_FIELD_INDEX.items():
        if index >= len(parts):
            continue
        raw = parts[index]
        if col in {"名称", "代码"}:
            row[col] = raw
            continue
        row[col] = _parse_optional_number(raw)
    # 单位转换：万 -> 元，亿 -> 元
    if row.get("成交额") is not None:
        row["成交额"] = row["成交额"] * 10000
    if row.get("流通市值") is not None:
        row["流通市值"] = row["流通市值"] * 1e8
    if row.get("总市值") is not None:
        row["总市值"] = row["总市值"] * 1e8
    return row
```

- [ ] **Step 4: 实现 _fetch_stocks_tencent**

在 `_parse_tencent_qt_response` 之后新增：

```python
def _fetch_stocks_tencent(codes: Iterable[str]) -> pd.DataFrame:
    """Fetch realtime stock quotes from Tencent qt.gtimg.cn, fallback to Sina."""
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="stock")
    except Exception as primary_exc:
        try:
            return _sina_stocks_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent stock fetch failed: {primary_exc}; "
                f"Sina stock fetch failed: {fallback_exc}"
            ) from fallback_exc


def _tencent_realtime_multi(codes: list[str], *, asset_type: str) -> pd.DataFrame:
    """Query Tencent qt for multiple codes, return 中文列名 DataFrame."""
    session = _tencent_qt_session()
    rows: list[dict[str, Any]] = []
    for code in codes:
        prefix = _tencent_prefix(code, asset_type)
        response = session.get(
            f"{TENCENT_QT_URL}{prefix}{code}",
            headers=TENCENT_QT_HEADERS,
            timeout=15,
        )
        row = _parse_tencent_qt_response(response.text)
        if not row or row.get("最新价") is None:
            raise SourceDataError(f"Tencent returned empty/invalid quote for {code}")
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame = _with_source(frame, "tencent_qt")
    return frame


def _sina_stocks_fallback(codes: list[str]) -> pd.DataFrame:
    """Fallback: use akshare Sina spot, filter to requested codes."""
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.stock_zh_a_spot(), "sina_spot")
    return _filter_by_codes(frame, codes)
```

- [ ] **Step 5: 运行个股测试确认通过**

Run: `python3 -m pytest tests/test_fetchers.py -k "fetch_stocks_tencent" -v`
Expected: 3 个 PASS

- [ ] **Step 6: 实现 _fetch_indices_tencent 和 _fetch_etfs_tencent**

在 `_fetch_stocks_tencent` 之后新增（复用 `_tencent_realtime_multi`）：

```python
def _fetch_indices_tencent(codes: Iterable[str]) -> pd.DataFrame:
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="index")
    except Exception as primary_exc:
        try:
            return _sina_indices_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent index fetch failed: {primary_exc}; "
                f"Sina index fetch failed: {fallback_exc}"
            ) from fallback_exc


def _fetch_etfs_tencent(codes: Iterable[str]) -> pd.DataFrame:
    code_list = [str(c) for c in codes]
    try:
        return _tencent_realtime_multi(code_list, asset_type="etf")
    except Exception as primary_exc:
        try:
            return _sina_etfs_fallback(code_list)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent etf fetch failed: {primary_exc}; "
                f"Sina etf fetch failed: {fallback_exc}"
            ) from fallback_exc


def _sina_indices_fallback(codes: list[str]) -> pd.DataFrame:
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.stock_zh_index_spot_sina(), "sina_spot")
    return _filter_by_codes(frame, codes)


def _sina_etfs_fallback(codes: list[str]) -> pd.DataFrame:
    akshare_module = _import_akshare()
    frame = _with_source(akshare_module.fund_etf_spot_em(), "sina_spot")
    return _filter_by_codes(frame, codes)
```

- [ ] **Step 7: 写指数/ETF 测试**

在 `tests/test_fetchers.py` 末尾追加：

```python
@patch("market_watch.fetchers.requests")
def test_fetch_indices_tencent_uses_sh_prefix_for_shanghai_index(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = (
        'v_sh000001="51~上证指数~000001~4043.64~4028.93~4030.12~~0~0'
        '~~~~~~~20260703150000~14.71~0.36~4044.12~4028.93'
        '~~~~~~~~1465563104854~~~~~";'
    )
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_indices(["000001"], source="tencent")

    # 验证用了 sh 前缀
    called_url = mock_requests.Session.return_value.get.call_args[0][0]
    assert "sh000001" in called_url
    assert result.iloc[0]["代码"] == "000001"
    assert result.iloc[0]["名称"] == "上证指数"
    assert result.iloc[0]["最新价"] == 4043.64
    assert result.iloc[0]["_market_watch_source"] == "tencent_qt"


@patch("market_watch.fetchers.requests")
def test_fetch_etfs_tencent_uses_sh_prefix_for_hushi_etf(mock_requests):
    mock_resp = MagicMock()
    mock_resp.text = (
        'v_sh512480="51~UC半导体ETF国联安~512480~1.331~1.325~1.326~~0~0'
        '~~~~~~~20260703150000~0.006~0.45~1.332~1.330~~~~~~~~~~~~~~";'
    )
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_etfs(["512480"], source="tencent")

    called_url = mock_requests.Session.return_value.get.call_args[0][0]
    assert "sh512480" in called_url
    assert result.iloc[0]["最新价"] == 1.331
```

- [ ] **Step 8: 运行全部腾讯测试确认通过**

Run: `python3 -m pytest tests/test_fetchers.py -k "tencent" -v`
Expected: 全部 PASS

- [ ] **Step 9: 提交**

```bash
git add market_watch/fetchers.py tests/test_fetchers.py
git commit -m "feat(fetchers): implement tencent realtime snapshot for stocks/indices/etfs"
```

---

## Task 5: 实现腾讯分钟线（含字段重排）

腾讯 mkline 返回 `[时间, 开, 收, 高, 低, 量, {}, 额]`，需重排为契约 `[时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额]`（注意：腾讯是开收高低，契约是开高低收）。

**Files:**
- Modify: `market_watch/fetchers.py` (新增 `_fetch_intraday_tencent`)
- Test: `tests/test_fetchers.py`

- [ ] **Step 1: 写失败测试 — 腾讯分钟线字段重排**

在 `tests/test_fetchers.py` 末尾追加：

```python
@patch("market_watch.fetchers.requests")
def test_fetch_intraday_tencent_reorders_fields(mock_requests):
    """腾讯 mkline=[时间,开,收,高,低,量,{},额] → 契约=[时间,开,高,低,收,量,额]."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "sz300857": {
                "m1": [
                    ["202607030931", "294.50", "295.20", "296.00", "294.00",
                     "1234", {}, "3651000"],
                    ["202607030932", "295.20", "295.50", "295.80", "295.00",
                     "2000", {}, "591000"],
                ]
            }
        }
    }
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stock_intraday(
        "300857",
        start="2026-07-03 09:30:00",
        end="2026-07-03 15:00:00",
        source="tencent",
    )

    assert len(result) == 2
    row0 = result.iloc[0]
    # 验证重排：开=294.50 高=296.00 低=294.00 收=295.20（不是腾讯原始顺序）
    assert row0["开盘"] == 294.50
    assert row0["最高"] == 296.00
    assert row0["最低"] == 294.00
    assert row0["收盘"] == 295.20
    assert row0["成交量"] == 1234
    assert row0["成交额"] == 3651000
    assert row0["时间"] == pd.Timestamp("2026-07-03 09:31:00")
    assert row0["_market_watch_source"] == "tencent_mkline_1m"


@patch("market_watch.fetchers.requests")
def test_fetch_intraday_tencent_filters_by_time_range(mock_requests):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "sz300857": {
                "m1": [
                    ["202607030929", "294.00", "294.00", "294.00", "294.00",
                     "100", {}, "29400"],  # 早于 start，应过滤
                    ["202607030931", "294.50", "295.20", "296.00", "294.00",
                     "1234", {}, "3651000"],
                ]
            }
        }
    }
    mock_requests.Session.return_value.get.return_value = mock_resp

    result = fetch_stock_intraday(
        "300857",
        start="2026-07-03 09:30:00",
        end="2026-07-03 15:00:00",
        source="tencent",
    )

    assert len(result) == 1
    assert result.iloc[0]["时间"] == pd.Timestamp("2026-07-03 09:31:00")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_fetchers.py -k "fetch_intraday_tencent" -v`
Expected: 2 个 FAIL（`_fetch_intraday_tencent` 未实现）

- [ ] **Step 3: 实现 _fetch_intraday_tencent**

在 `_sina_etfs_fallback` 之后新增：

```python
TENCENT_MKLINE_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"

# 腾讯 mkline 返回 8 元素: [时间, 开, 收, 高, 低, 量, {}, 额]
# 契约要求: [时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额]
# 注意腾讯是"开收高低"，契约是"开高低收"，需重排。
_TENCENT_MKLINE_INDEX = {
    "时间": 0,
    "开盘": 1,
    "收盘": 2,
    "最高": 3,
    "最低": 4,
    "成交量": 5,
    "成交额": 7,  # 索引6是空{}，跳过
}


def _fetch_intraday_tencent(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    try:
        return _tencent_mkline(code, start, end, asset_type=asset_type)
    except Exception as primary_exc:
        try:
            return _sina_intraday_fallback(code, start, end, asset_type=asset_type)
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Tencent intraday fetch failed: {primary_exc}; "
                f"Sina intraday fetch failed: {fallback_exc}"
            ) from fallback_exc


def _tencent_mkline(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    prefix = _tencent_prefix(code, asset_type)
    session = _tencent_qt_session()
    response = session.get(
        TENCENT_MKLINE_URL,
        params={"param": f"{prefix}{code},m1,,320"},
        headers=TENCENT_QT_HEADERS,
        timeout=15,
    )
    payload = response.json()
    node = payload.get("data", {}).get(f"{prefix}{code}", {})
    klines = node.get("m1", [])
    if not klines:
        raise SourceDataError(f"Tencent mkline returned no data for {code}")

    rows: list[dict[str, Any]] = []
    for kline in klines:
        if len(kline) < 8:
            continue
        time_str = str(kline[_TENCENT_MKLINE_INDEX["时间"]])
        parsed_time = pd.to_datetime(time_str, format="%Y%m%d%H%M", errors="coerce")
        row = {
            "时间": parsed_time,
            "开盘": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["开盘"]]),
            "最高": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["最高"]]),
            "最低": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["最低"]]),
            "收盘": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["收盘"]]),
            "成交量": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["成交量"]]),
            "成交额": _parse_optional_number(kline[_TENCENT_MKLINE_INDEX["成交额"]]),
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    start_time = pd.to_datetime(start)
    end_time = pd.to_datetime(end)
    frame = frame[
        frame["时间"].notna()
        & (frame["时间"] >= start_time)
        & (frame["时间"] <= end_time)
    ].copy()
    frame = _with_source(frame, "tencent_mkline_1m")
    return frame


def _sina_intraday_fallback(
    code: str, start: str, end: str, *, asset_type: str
) -> pd.DataFrame:
    """Fallback to akshare Sina minute data."""
    akshare_module = _import_akshare()
    if asset_type == "index":
        sina_symbol = _index_sina_symbol(code)
    else:
        sina_symbol = _stock_sina_symbol(code)
    frame = akshare_module.stock_zh_a_minute(
        symbol=sina_symbol,
        period="1",
        adjust="",
    )
    return _convert_sina_minute_frame(frame, start=start, end=end)
```

- [ ] **Step 4: 运行分钟线测试确认通过**

Run: `python3 -m pytest tests/test_fetchers.py -k "fetch_intraday_tencent" -v`
Expected: 2 个 PASS

- [ ] **Step 5: 运行全部 fetcher 测试确认无退化**

Run: `python3 -m pytest tests/test_fetchers.py -v`
Expected: 全部 PASS（akshare 旧测试 + tencent 新测试）

- [ ] **Step 6: 提交**

```bash
git add market_watch/fetchers.py tests/test_fetchers.py
git commit -m "feat(fetchers): implement tencent mkline intraday with field reorder"
```

---

## Task 6: watch.py 接入 source 分发

让 watch.py 从 config 读 provider，作为 `source=` 传给 fetch 函数。

**Files:**
- Modify: `watch.py:84-90, 104-113, 127-133` (collect_records 的三处 fetch 调用)
- Modify: `watch.py:163-209` (collect_intraday_records)

- [ ] **Step 1: 在 collect_records 读取 source 并传入**

`watch.py` 第 78 行附近，在 `targets = config["targets"]` 之前加一行读 source：

```python
    targets = config["targets"]
    runtime = config["runtime"]
    retry_count = runtime["retry_count"]
    slow_threshold_seconds = runtime["request_timeout_seconds"]
    source_provider = config["source"]["provider"]
```

然后修改三处 fetch 调用。第 84-90 行的 stocks 调用，把 lambda 改为传 `source=source_provider`：

```python
        stock_frame, fetch_errors = _fetch_with_retry(
            lambda: fetch_stocks(
                [target["code"] for target in stock_targets],
                source=source_provider,
            ),
            stage="fetch_stocks",
```

第 104-113 行的 indices 调用：

```python
        index_frame, fetch_errors = _fetch_with_retry(
            lambda: fetch_indices(
                [target["code"] for target in index_targets],
                config["source"]["index_symbol"],
                source=source_provider,
            ),
            stage="fetch_indices",
```

第 127-133 行的 etfs 调用：

```python
        etf_frame, fetch_errors = _fetch_with_retry(
            lambda: fetch_etfs(
                [target["code"] for target in etf_targets],
                source=source_provider,
            ),
            stage="fetch_etfs",
```

- [ ] **Step 2: 在 collect_intraday_records 读取 source 并传入**

`watch.py` 第 158-161 行附近，加 `source_provider`：

```python
    records: list[dict] = []
    errors: list[dict] = []
    targets = config["targets"]
    runtime = config["runtime"]
    retry_count = runtime["retry_count"]
    slow_threshold_seconds = runtime["request_timeout_seconds"]
    source_provider = config["source"]["provider"]
```

然后修改 `_normalize_intraday_target` 的调用——它通过 `fetcher=target_fetcher` 传入。需要把 source 透传下去。三个循环（stocks/indices/etfs）的 `_normalize_intraday_target` 调用都加 `source=source_provider` 参数。

最简单的方式：把 `fetcher` 改成 lambda 包一层。第 163-175 行 stocks 循环：

```python
    for target in targets.get("stocks", []):
        target_records, target_errors = _normalize_intraday_target(
            target,
            asset_type="stock",
            fetcher=lambda c, s, e: fetch_stock_intraday(c, s, e, source=source_provider),
            stage="fetch_stock_intraday",
            timestamp=timestamp,
            trade_date=trade_date,
            start=start,
            end=end,
            retry_count=retry_count,
            slow_threshold_seconds=slow_threshold_seconds,
        )
```

indices 循环（第 179-191 行）同理，`fetcher=lambda c, s, e: fetch_index_intraday(c, s, e, source=source_provider)`。

etfs 循环（第 195-207 行）同理，`fetcher=lambda c, s, e: fetch_etf_intraday(c, s, e, source=source_provider)`。

- [ ] **Step 3: 检查 watch.py 没有现成测试需要更新**

Run: `grep -r "source_provider\|source=" tests/test_watch.py`
Expected: 无输出（watch.py 的测试应该不直接测 fetch 调用细节，而是测整体行为）。如果有相关测试命中，需相应更新。

- [ ] **Step 4: 运行 watch.py 测试**

Run: `python3 -m pytest tests/test_watch.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add watch.py
git commit -m "feat(watch): pass source provider from config to fetchers"
```

---

## Task 7: 更新 config.yaml 默认值 + 端到端验证

**Files:**
- Modify: `config.yaml:128`

- [ ] **Step 1: 改 config.yaml provider 为 tencent**

`config.yaml` 第 128 行，把 `provider: "akshare"` 改为 `provider: "tencent"`：

```yaml
source:
  provider: "tencent"
  stock_source: "eastmoney_with_sina_fallback"
  index_symbol: "沪深重要指数"
```

- [ ] **Step 2: 运行全套测试**

Run: `python3 -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 3: 端到端验证 — 实时快照**

Run: `python3 watch.py --once`
Expected: 成功输出 Markdown，包含协创数据、香农芯创、润泽科技、指数、ETF 的实时行情。检查 `outputs/latest.json` 的 `source` 字段应为 `tencent_qt` 或 `sina_spot`（fallback 时）。

- [ ] **Step 4: 端到端验证 — 分钟线 backfill**

Run: `python3 watch.py --backfill-today`
Expected: 成功输出 `outputs/today.md` 和 `data/intraday/2026-07-03-1m.csv`。检查 JSON 的 source 字段应为 `tencent_mkline_1m` 或 `sina_minute_1m`。

- [ ] **Step 5: 端到端验证 — akshare 回退路径不破坏**

临时把 `config.yaml` 改回 `provider: "akshare"`，运行：

Run: `python3 watch.py --once`
Expected: 行为与改动前一致（东财主源尝试失败 → 新浪备源兜底，能出数据）。验证后改回 `provider: "tencent"`。

- [ ] **Step 6: 验证中间层零改动**

Run: `git diff main -- market_watch/normalize.py market_watch/render.py market_watch/storage.py market_watch/summary.py market_watch/intraday.py | cat`
Expected: 空输出（这 5 个文件零改动）。如果 task 是在 feature 分支做的，把 `main` 换成对应 base 分支名。

- [ ] **Step 7: 提交**

```bash
git add config.yaml
git commit -m "feat(config): switch default data source to tencent"
```

---

## Task 8: 更新 README 数据源说明

**Files:**
- Modify: `README.md:88-96` (第 7 节 数据源)

- [ ] **Step 1: 更新 README 第 7 节**

把 README 第 88-96 行（## 7. 数据源 整节）替换为：

```markdown
## 7. 数据源

- 实时行情主源：腾讯财经 `qt.gtimg.cn` 接口，逐只查询，字段含五档盘口、换手率、市盈率等。
- 实时行情备源：AKShare 新浪接口；主源失败时自动切换。
- 当日 1 分钟线主源：腾讯 `ifzq.gtimg.cn` mkline 接口。
- 当日 1 分钟线备源：AKShare 新浪分钟线接口；主源失败时自动切换。

腾讯主源通过 `source.provider: tencent` 启用（默认）。如需切回东方财富主源，把
`config.yaml` 里 `source.provider` 改为 `akshare`。东财接口在部分网络环境下存在
不稳定拦截，建议默认使用腾讯主源。

JSON/CSV 中的 `source` 字段标记本条数据来自哪个接口（`tencent_qt` / `tencent_mkline_1m`
/ `sina_spot` / `sina_minute_1m` / `akshare_em` 等）。新浪备源能提高可用性，但部分字段
会为空，例如量比、估值和市值字段。
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: update README for tencent/sina data sources"
```
