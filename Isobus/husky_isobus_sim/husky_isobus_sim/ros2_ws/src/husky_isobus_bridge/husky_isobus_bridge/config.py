from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str) -> dict[str, Any]:
    file = Path(path)
    if not path or not file.is_file():
        raise RuntimeError(f'arquivo de configuração não encontrado: {path!r}')
    return yaml.safe_load(file.read_text(encoding='utf-8')) or {}


def parse_int(value: Any) -> int:
    return int(str(value), 0) if isinstance(value, str) else int(value)


def join_topic(namespace: str, topic: str) -> str:
    if topic.startswith('/'):
        return '/' + '/'.join(part for part in topic.split('/') if part)
    return '/' + '/'.join(part for part in f'{namespace}/{topic}'.split('/') if part)
