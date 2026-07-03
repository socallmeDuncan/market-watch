import pytest
import yaml


@pytest.fixture
def sample_config_dict():
    return {
        "targets": {
            "stocks": [
                {"code": "300857", "name": "协创数据", "role": "primary"},
                {"code": "300475", "name": "香农芯创", "role": "compare"},
                {"code": "300442", "name": "润泽科技", "role": "compare"},
            ],
            "indices": [
                {"code": "399006", "name": "创业板指", "role": "context"},
                {"code": "399001", "name": "深证成指", "role": "context"},
                {"code": "000001", "name": "上证指数", "role": "context"},
            ],
            "etfs": [
                {"code": "159915", "name": "创业板ETF易方达", "role": "context"},
                {"code": "588000", "name": "科创50ETF华夏", "role": "context"},
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
            "intraday_dir": "data/intraday",
            "today_markdown": "outputs/today.md",
            "today_json": "outputs/today.json",
        },
        "source": {
            "provider": "tencent",
            "stock_source": "eastmoney",
            "index_symbol": "沪深重要指数",
        },
    }


@pytest.fixture
def config_file(tmp_path, sample_config_dict):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(sample_config_dict, allow_unicode=True), encoding="utf-8")
    return path
