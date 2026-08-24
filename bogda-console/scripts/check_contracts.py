from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_openapi import export


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bogda-contracts-") as temporary:
        temp = Path(temporary)
        schema = temp / "openapi.json"
        generated = temp / "generated.ts"
        export(schema)
        executable = "npx.cmd" if sys.platform == "win32" else "npx"
        subprocess.run(
            [executable, "openapi-typescript", str(schema), "-o", str(generated)],
            cwd=ROOT,
            check=True,
        )
        expected = {
            ROOT / "openapi.json": schema,
            ROOT / "frontend/src/api/generated.ts": generated,
        }
        changed = [str(target.relative_to(ROOT)) for target, candidate in expected.items() if not target.exists() or target.read_bytes() != candidate.read_bytes()]
        if changed:
            print("Generated API contract drift: " + ", ".join(changed), file=sys.stderr)
            print("Run: npm run generate:contracts", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
