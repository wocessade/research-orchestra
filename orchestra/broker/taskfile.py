"""T-*.md 任务文件解析。严格格式：
头部为 key: value 行（# 开头为注释），`---` 单独一行后为执行体。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass
class TaskSpec:
    slug: str
    executor: str   # dsh | shell
    net: str        # required | optional
    result_dir: str
    timeout: int
    body: str
    model: str | None = None   # dsh 模型档位（flash|pro），缺省用 profile 默认

_REQUIRED = ("executor", "net", "result")

def parse_taskfile(path: str | Path) -> TaskSpec:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    header, sep, body = text.partition("\n---\n")
    if not sep:
        raise ValueError(f"{p}: 缺少 '---' 分隔行")
    fields: dict[str, str] = {}
    for line in header.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{p}: 头部行不是 key: value 格式: {line!r}")
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    missing = [k for k in _REQUIRED if k not in fields]
    if missing:
        raise ValueError(f"{p}: 缺少字段 {missing}")
    if fields["executor"] not in ("dsh", "shell"):
        raise ValueError(f"{p}: executor 必须为 dsh|shell，实际 {fields['executor']!r}")
    if fields["net"] not in ("required", "optional"):
        raise ValueError(f"{p}: net 必须为 required|optional")
    body = body.strip()
    if not body:
        raise ValueError(f"{p}: 执行体为空")
    return TaskSpec(
        slug=p.stem,
        executor=fields["executor"],
        net=fields["net"],
        result_dir=fields["result"],
        timeout=int(fields.get("timeout", "3600")),
        body=body,
        model=fields.get("model"),
    )
