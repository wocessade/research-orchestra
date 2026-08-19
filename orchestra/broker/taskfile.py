"""T-*.md 任务文件解析。严格格式：
头部为 key: value 行（# 开头为注释），`---` 单独一行后为执行体。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

@dataclass
class TaskSpec:
    slug: str
    executor: str   # dsh | shell
    net: str        # required | optional
    result_dir: str
    timeout: int
    body: str
    model: str | None = None   # dsh 模型档位（flash|pro），缺省用 profile 默认
    depends_on: tuple[str, ...] = ()
    mode: str = "execute"
    detail: str = "standard"
    required_outputs: tuple[str, ...] = ()
    json_outputs: tuple[str, ...] = ()
    validation_output: str | None = None
    validator: str | None = None

_REQUIRED = ("executor", "net", "result")
_VALID_MODES = ("execute", "explore", "decide", "audit", "brief")
_VALID_DETAILS = ("brief", "standard", "deep")
_VALID_VALIDATORS = ("radar-fetch", "radar-rank", "radar-render")


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _validate_relative_path(path: str, field: str, source: Path) -> None:
    candidates = (PurePosixPath(path), PureWindowsPath(path))
    invalid = path in ("", ".") or any(
        candidate.is_absolute() or candidate.drive or ".." in candidate.parts
        for candidate in candidates
    )
    if invalid:
        raise ValueError(f"{source}: {field} 只能包含工作目录内的相对路径: {path!r}")

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
    _validate_relative_path(fields["result"], "result", p)
    body = body.strip()
    if not body:
        raise ValueError(f"{p}: 执行体为空")
    depends_on = _parse_csv(fields.get("depends_on", ""))
    if p.stem in depends_on:
        raise ValueError(f"{p}: depends_on 不能包含任务自身")
    if len(depends_on) != len(set(depends_on)):
        raise ValueError(f"{p}: depends_on 包含重复任务")
    mode = fields.get("mode", "execute")
    if mode not in _VALID_MODES:
        raise ValueError(f"{p}: mode 必须为 {'|'.join(_VALID_MODES)}")
    detail = fields.get("detail", "standard")
    if detail not in _VALID_DETAILS:
        raise ValueError(f"{p}: detail 必须为 {'|'.join(_VALID_DETAILS)}")
    required_outputs = _parse_csv(fields.get("required_outputs", ""))
    json_outputs = _parse_csv(fields.get("json_outputs", ""))
    validation_output = fields.get("validation_output") or None
    validator = fields.get("validator") or None
    if validator is not None and validator not in _VALID_VALIDATORS:
        raise ValueError(f"{p}: validator 必须为 {'|'.join(_VALID_VALIDATORS)}")
    for output in required_outputs:
        _validate_relative_path(output, "required_outputs", p)
    for output in json_outputs:
        _validate_relative_path(output, "json_outputs", p)
    if validation_output is not None:
        _validate_relative_path(validation_output, "validation_output", p)
    undeclared_json = set(json_outputs) - set(required_outputs)
    if undeclared_json:
        raise ValueError(f"{p}: json_outputs 必须同时出现在 required_outputs")
    if validation_output is not None and validation_output not in json_outputs:
        raise ValueError(f"{p}: validation_output 必须同时出现在 json_outputs")
    return TaskSpec(
        slug=p.stem,
        executor=fields["executor"],
        net=fields["net"],
        result_dir=fields["result"],
        timeout=int(fields.get("timeout", "3600")),
        body=body,
        model=fields.get("model"),
        depends_on=depends_on,
        mode=mode,
        detail=detail,
        required_outputs=required_outputs,
        json_outputs=json_outputs,
        validation_output=validation_output,
        validator=validator,
    )
