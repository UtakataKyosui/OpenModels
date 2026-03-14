from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def snake_case(value: str) -> str:
    step_1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    step_2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step_1)
    step_3 = step_2.replace("-", "_").replace(" ", "_")
    return step_3.lower()


def camel_case(value: str) -> str:
    parts = re.split(r"[_\-\s]+", value)
    head = parts[0].lower()
    tail = "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)
    return head + tail


def upper_camel_case(value: str) -> str:
    parts = re.split(r"[_\-\s]+", value)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def to_json_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def escape_template_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
