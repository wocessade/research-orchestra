#!/usr/bin/env python3
"""Academic Skills Environment Doctor — check what's available without importing
non-stdlib dependencies. Pure stdlib: no PyYAML, no python-docx, no requests.

Usage:
    python doctor.py           # human-readable report
    python doctor.py --json    # machine-parseable JSON output
"""

import importlib.util
import json
import socket
import subprocess
import sys


def check_python():
    return {
        "version": sys.version,
        "executable": sys.executable,
        "ok": sys.version_info >= (3, 8),
    }


def check_module(module_name, import_name=None):
    """Check if a module is importable WITHOUT importing it."""
    name = import_name or module_name
    try:
        spec = importlib.util.find_spec(name)
        if spec is None:
            return {"available": False}
        version = None
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", module_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Version:"):
                        version = line.split(":", 1)[1].strip()
        except Exception:
            pass
        return {"available": True, "version": version, "path": spec.origin}
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_network(host, port=443, timeout=5):
    """TCP connect check — no HTTP library needed."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {"host": host, "port": port, "reachable": True}
    except Exception as e:
        return {"host": host, "port": port, "reachable": False, "error": str(e)}


def check_command(cmd_name, args=None):
    if args is None:
        args = ["--version"]
    try:
        result = subprocess.run(
            [cmd_name] + args, capture_output=True, text=True, timeout=10
        )
        out = (result.stdout + result.stderr).strip()[:200]
        return {"available": True, "output": out}
    except FileNotFoundError:
        return {"available": False}
    except Exception as e:
        return {"available": True, "error": str(e)[:200]}


def main():
    as_json = "--json" in sys.argv

    results = {
        "python": check_python(),
        "dependencies": {
            "PyYAML": check_module("PyYAML", "yaml"),
            "python-docx": check_module("python-docx", "docx"),
            "PyMuPDF": check_module("PyMuPDF", "fitz"),
            "PaddleOCR": check_module("paddleocr"),
        },
        "network": {
            "pypi.org": check_network("pypi.org", 443),
            "doi.org": check_network("doi.org", 443),
        },
        "commands": {
            "git": check_command("git"),
            "pandoc": check_command("pandoc", ["--version"]),
        },
    }

    # ── JSON mode ──
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # ── Human-readable mode ──
    print("=" * 60)
    print("  Academic Skills — Environment Doctor")
    print("=" * 60)
    print()

    py = results["python"]
    status = "OK" if py["ok"] else "FAIL"
    ver = py["version"].split()[0]
    print(f"  Python:        {status}  ({ver})")
    print(f"                 {py['executable']}")
    if not py["ok"]:
        print("                 ^ Requires Python 3.8+")
    print()

    print("  Dependencies:")
    width = max(len(k) for k in results["dependencies"]) + 2
    for name, info in results["dependencies"].items():
        label = name.ljust(width)
        if info["available"]:
            v = f" v{info['version']}" if info.get("version") else ""
            print(f"    {label} FOUND{v}")
        else:
            print(f"    {label} MISSING  (pip install {name})")
    print()

    print("  Network (TCP connect):")
    all_net_ok = True
    for label, info in results["network"].items():
        if info["reachable"]:
            print(f"    {label:25s} REACHABLE")
        else:
            err = info.get("error", "timeout")
            print(f"    {label:25s} UNREACHABLE ({err})")
            all_net_ok = False
    print()

    print("  Commands:")
    for name, info in results["commands"].items():
        if info["available"]:
            snippet = info.get("output", "available")[:60]
            print(f"    {name:15s} FOUND  ({snippet})")
        else:
            print(f"    {name:15s} MISSING")
    print()

    # ── Summary ──
    issues = []
    if not py["ok"]:
        issues.append("Python 3.8+ required")
    for name, info in results["dependencies"].items():
        if not info["available"]:
            issues.append(f"{name} not installed")
    if not all_net_ok:
        issues.append("some network targets unreachable")

    print("=" * 60)
    if issues:
        print(f"  DOCTOR: {len(issues)} issue(s) found")
        for i in issues:
            print(f"    - {i}")
    else:
        print("  DOCTOR: All checks passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
