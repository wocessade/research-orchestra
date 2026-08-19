#!/usr/bin/env python3
"""ctl arm: single-shot LLM extraction for EXP-001.

Reads the extraction material (--text) and the field list from gold.json
(--gold), sends ONE chat-completions request to the DeepSeek API with a
prompt requiring strict JSON output (keys = gold field names, values
copied verbatim from the source text), then writes
{"fields": {...}} to --out.

Requires the DEEPSEEK_API_KEY environment variable (never stored in git).
On the Pi side the key lives in the system environment.

stdlib only (urllib.request); no real API call is made on Windows
(no key available there).

Exit codes: 0 success; 2 missing/empty API key, HTTP error, or invalid
model output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.deepseek.com/chat/completions"


def die(msg: str) -> "SystemExit":
    print(msg, file=sys.stderr)
    return SystemExit(2)


def read_gold_fields(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fields = data.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise die(f"ERROR: {path} must contain a non-empty \"fields\" object")
    return list(fields)


def build_prompt(text: str, field_names: list) -> str:
    names = ", ".join(field_names)
    return (
        "你是严格的信息抽取器。请从下面的文本中抽取指定字段。\n"
        "要求：\n"
        "1. 只输出一个 JSON 对象，不要输出任何其他内容"
        "（不要 markdown 代码块、不要解释）。\n"
        f"2. JSON 的键必须与字段名完全一致：{names}。\n"
        "3. 每个值必须逐字摘自文本原文，不得改写、翻译、补充或省略；"
        "找不到对应信息时用空字符串。\n"
        "4. 输出必须能被 json.loads 直接解析。\n\n"
        f"文本：\n{text}\n"
    )


def call_api(prompt: str, api_key: str) -> dict:
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你只输出严格 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise die(f"ERROR: API HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise die(f"ERROR: API request failed: {e.reason}") from None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--text", required=True, type=Path,
                    help="path to the extraction material text file")
    ap.add_argument("--gold", required=True, type=Path,
                    help="path to gold.json (field names come from here)")
    ap.add_argument("--out", required=True, type=Path,
                    help="path to write result.json (parent dirs created)")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise die("ERROR: environment variable DEEPSEEK_API_KEY is not set "
                  "or empty. Set it (system env on the Pi side) before "
                  "running the ctl arm.")

    field_names = read_gold_fields(args.gold)
    text = args.text.read_text(encoding="utf-8")
    prompt = build_prompt(text, field_names)

    response = call_api(prompt, api_key)
    choices = response.get("choices") or []
    if not choices:
        raise die("ERROR: API response has no choices: "
                  + json.dumps(response, ensure_ascii=False)[:300])
    content = choices[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        raise die(f"ERROR: model output is not valid JSON: {e}\n"
                  f"content: {content[:300]}") from None
    fields = parsed.get("fields", parsed)  # accept {"fields": {...}} or flat
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"fields": fields}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"OK: wrote result to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
