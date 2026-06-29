#!/usr/bin/env python3
"""Local configuration loader for China Birding.

The project intentionally keeps runtime code environment-variable based.
This loader maps a small local YAML file into those environment variables so
local testing does not require exporting secrets in every shell.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional, Union


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.local.yaml"

ENV_MAPPING = {
    "EBIRD_API_KEY": ("ebird.api_key", "ebird_api_key"),
    "BIRDING_REGION": ("birding.region", "region"),
    "BIRDING_PROVINCE": ("birding.province", "province"),
}


def _strip_inline_comment(value: str) -> str:
    quote = ""
    escaped = False
    for i, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in ("'", '"'):
            if quote == char:
                quote = ""
            elif not quote:
                quote = char
            continue
        if char == "#" and not quote:
            return value[:i].rstrip()
    return value.strip()


def _parse_scalar(value: str) -> Any:
    value = _strip_inline_comment(value).strip()
    if not value:
        return ""
    if (value[0], value[-1]) in {('"', '"'), ("'", "'")}:
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small nested mapping subset used by config.local.yaml.

    This is deliberately not a general YAML parser. If PyYAML is installed,
    load_config_file uses it first. The fallback supports simple mappings:

      section:
        key: value
    """
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for line_no, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[: len(raw_line) - len(raw_line.lstrip())].count("\t"):
            raise ValueError(f"Tabs are not supported in YAML indentation at line {line_no}")

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"Expected 'key: value' at line {line_no}")

        key = key.strip()
        if not key:
            raise ValueError(f"Empty YAML key at line {line_no}")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"Invalid indentation at line {line_no}")

        parent = stack[-1][1]
        if value.strip():
            parent[key] = _parse_scalar(value)
            continue

        child: dict[str, Any] = {}
        parent[key] = child
        stack.append((indent, child))

    return root


ConfigPath = Union[os.PathLike[str], str]


def load_config_file(path: ConfigPath) -> dict[str, Any]:
    """Read a YAML config file into a dictionary."""
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(text)

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top level in {config_path}")
    return data


def _get_nested(config: dict[str, Any], dotted_path: str) -> Optional[Any]:
    current: Any = config
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _first_config_value(config: dict[str, Any], paths: tuple[str, ...]) -> Optional[Any]:
    for path in paths:
        value = _get_nested(config, path)
        if value not in (None, ""):
            return value
    return None


def apply_config_to_env(config: dict[str, Any], override_env: bool = False) -> None:
    """Map local YAML values into environment variables."""
    for env_name, paths in ENV_MAPPING.items():
        if not override_env and os.environ.get(env_name):
            continue
        value = _first_config_value(config, paths)
        if value in (None, ""):
            continue
        os.environ[env_name] = str(value)


def load_local_config(
    path: Optional[ConfigPath] = None,
    override_env: bool = False,
) -> dict[str, Any]:
    """Load local YAML config and apply missing environment variables.

    Path resolution:
      1. explicit path argument
      2. CHINA_BIRDING_CONFIG
      3. ./config.local.yaml
    """
    config_path = Path(path or os.environ.get("CHINA_BIRDING_CONFIG") or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        return {}

    config = load_config_file(config_path)
    apply_config_to_env(config, override_env=override_env)
    logger.debug("Loaded local config from %s", config_path)
    return config
