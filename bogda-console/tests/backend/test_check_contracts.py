from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_contracts import contract_bytes_equal


def test_same_text_with_lf_versus_crlf_is_not_drift() -> None:
    lf = b"export interface Run {\n  id: string;\n}\n"
    crlf = b"export interface Run {\r\n  id: string;\r\n}\r\n"
    assert contract_bytes_equal(lf, crlf)


def test_non_newline_content_change_is_drift() -> None:
    committed = b"export interface Run {\n  id: string;\n}\n"
    generated = b"export interface Run {\n  id: number;\n}\n"
    assert not contract_bytes_equal(committed, generated)
    assert not contract_bytes_equal(committed, b"export interface Run {\n  id: string;\n }\n")
    assert not contract_bytes_equal(
        b'{"paths":{"/a":{}}}\n',
        b'{"paths":{"/b":{}}}\n',
    )
