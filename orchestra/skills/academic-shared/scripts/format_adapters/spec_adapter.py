"""
Spec-document adapter (stub).

Reserved for parsing a textual format specification document.
Returns an empty dict, signalling "no source available".
"""


def parse(source_path: str) -> dict:
    # TODO (v3.0): Implement spec-document parsing for real-world format spec docs
    # (ELSPDF, journal-provided .docx templates, 中国高校学位论文模板). Needs actual
    # spec documents as test fixtures to verify parser output against ground truth.
    # For now, returns empty dict to signal "no source available."
    print(f"  [INFO] spec-adapter: stub -- no parsing logic yet for '{source_path}'")
    return {}
