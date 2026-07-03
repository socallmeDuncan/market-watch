"""Configuration loading and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


VALID_ROLES = {"primary", "compare", "context"}
DEFAULT_CONFIG: dict[str, Any] = {
    "targets": {"stocks": [], "indices": [], "etfs": []},
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
    etfs = _require_list(targets, "etfs")
    if not stocks and not indices and not etfs:
        raise ConfigError("At least one target must be configured")

    seen: set[tuple[str, str]] = set()
    for asset_type, items in [("stock", stocks), ("index", indices), ("etf", etfs)]:
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
    _require_bool(runtime, "market_hours_only")
    _require_non_empty_string(runtime, "market_timezone")
    windows = _require_list(runtime, "history_windows_minutes")
    if not windows or not all(
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        for value in windows
    ):
        raise ConfigError("history_windows_minutes must be a non-empty list of positive integers")

    storage = _require_mapping(config, "storage")
    _require_non_empty_string(storage, "snapshot_dir")
    _require_non_empty_string(storage, "latest_markdown")
    _require_non_empty_string(storage, "latest_json")
    _require_non_empty_string(storage, "intraday_dir")
    _require_non_empty_string(storage, "today_markdown")
    _require_non_empty_string(storage, "today_json")

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


def _require_bool(config: dict[str, Any], key: str) -> bool:
    value = config.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean")
    return value


def _require_positive_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _require_non_negative_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{key} must be a non-negative integer")
    return value
