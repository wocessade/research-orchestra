from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_contracts import contract_bytes_equal


def test_same_text_with_lf_versus_crlf_is_not_drift() -> None:
    lf = b"export interface Run {\n  id: string;\n}\n"
    crlf = b"export interface Run {\r\n  id: string;\r\n}\r\n"
    assert contract_bytes_equal(lf, crlf)


def test_real_shadow_runbook_contains_operational_contract() -> None:
    runbook = Path(__file__).resolve().parents[2] / "docs" / "real-shadow-runbook.md"
    text = runbook.read_text(encoding="utf-8")

    required_terms = (
        "real-readonly",
        "allowlisted-test",
        "PREFECT_API_AUTH_STRING",
        "BOGDA_CONSOLE_REPLICA_COUNT=1",
        "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS",
        "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS",
        "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS",
        "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES",
        "3100",
        "authoritative post-read",
    )

    missing = [term for term in required_terms if term not in text]
    assert not missing, f"runbook is missing required terms: {missing}"


def test_real_shadow_runbook_has_exactly_six_phases() -> None:
    runbook = Path(__file__).resolve().parents[2] / "docs" / "real-shadow-runbook.md"
    headings = [
        line
        for line in runbook.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]

    assert headings == [
        "## 1. Ownership preflight",
        "## 2. 3100 before-check",
        "## 3. S1 start/read/compare",
        "## 4. Restore",
        "## 5. S2 dedicated-resource setup",
        "## 6. S2 command matrix/restore",
    ]


def test_non_newline_content_change_is_drift() -> None:
    committed = b"export interface Run {\n  id: string;\n}\n"
    generated = b"export interface Run {\n  id: number;\n}\n"
    assert not contract_bytes_equal(committed, generated)
    assert not contract_bytes_equal(committed, b"export interface Run {\n  id: string;\n }\n")
    assert not contract_bytes_equal(
        b'{"paths":{"/a":{}}}\n',
        b'{"paths":{"/b":{}}}\n',
    )
