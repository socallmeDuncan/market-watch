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
    del sample_config_dict["runtime"]["retry_count"]
    sample_config_dict["targets"].pop("etfs")
    path = write_yaml(tmp_path / "config.yaml", sample_config_dict)

    config = load_config(path)

    assert config["runtime"]["market_timezone"] == "Asia/Shanghai"
    assert config["runtime"]["request_timeout_seconds"] == 15
    assert config["runtime"]["retry_count"] == 1
    assert config["targets"]["etfs"] == []


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


def test_validate_config_rejects_duplicate_asset_code(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"].append(
        {"code": "300857", "name": "重复协创", "role": "compare"}
    )

    with pytest.raises(ConfigError, match="Duplicate target"):
        validate_config(sample_config_dict)


def test_validate_config_allows_same_code_in_different_asset_types(
    sample_config_dict: dict,
) -> None:
    sample_config_dict["targets"]["etfs"].append(
        {"code": "300857", "name": "测试ETF", "role": "context"}
    )

    validate_config(sample_config_dict)


def test_validate_config_rejects_invalid_role(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"][0]["role"] = "leader"

    with pytest.raises(ConfigError, match="Invalid role"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_missing_targets(sample_config_dict: dict) -> None:
    sample_config_dict["targets"]["stocks"] = []
    sample_config_dict["targets"]["indices"] = []
    sample_config_dict["targets"]["etfs"] = []

    with pytest.raises(ConfigError, match="At least one target"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_non_positive_interval(sample_config_dict: dict) -> None:
    sample_config_dict["runtime"]["interval_seconds"] = 0

    with pytest.raises(ConfigError, match="interval_seconds"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_boolean_interval(sample_config_dict: dict) -> None:
    sample_config_dict["runtime"]["interval_seconds"] = True

    with pytest.raises(ConfigError, match="interval_seconds"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_boolean_history_window(sample_config_dict: dict) -> None:
    sample_config_dict["runtime"]["history_windows_minutes"] = [15, True]

    with pytest.raises(ConfigError, match="history_windows_minutes"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_boolean_retry_count(sample_config_dict: dict) -> None:
    sample_config_dict["runtime"]["retry_count"] = False

    with pytest.raises(ConfigError, match="retry_count"):
        validate_config(sample_config_dict)


def test_validate_config_rejects_non_boolean_market_hours_only(
    sample_config_dict: dict,
) -> None:
    sample_config_dict["runtime"]["market_hours_only"] = "yes"

    with pytest.raises(ConfigError, match="market_hours_only"):
        validate_config(sample_config_dict)


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


def test_validate_config_rejects_missing_index_symbol(sample_config_dict: dict) -> None:
    del sample_config_dict["source"]["index_symbol"]

    with pytest.raises(ConfigError, match="index_symbol"):
        validate_config(sample_config_dict)


def test_load_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Config file not found"):
        load_config(tmp_path / "missing.yaml")
