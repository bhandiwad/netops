#!/usr/bin/env python3
"""CI Architecture Gate: Enforce Topology-Agnostic Backend Code.

Scans every Python file under `backend/app/` (ignoring comments and docstrings)
and fails with exit code 1 if any topology-specific asset ID from the reference
dataset (`CBL-*`, `OCH-*`, `D-*`, `RAN_*`, `SPL-*`, `MW-*`, `SUBSEA-*`, `CUST-*`,
`SVC-*`, `PFE-*`) is hardcoded in executable backend code.

Why this exists:
Non-domain and domain engineers alike must write topology-agnostic graph, spatial,
and classifier logic parameterized strictly by PostgreSQL/PostGIS inventory rows
and canonical alarm payloads — never hardcoded demo strings!
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend" / "app"

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Hardcoded OSP Cable ID", re.compile(r"\bCBL-[A-Z0-9-]+\b")),
    ("Hardcoded Optical Wavelength ID", re.compile(r"\bOCH-[A-Z0-9-]+\b")),
    ("Hardcoded OSP Duct ID", re.compile(r"\bD-(?:JBL|I[1-5]|DG|TC|AK|KRM|MB|DRA|AIR|GB|DSO|RAK|BRS|MRN|QZ)[A-Z0-9-]*\b")),
    ("Hardcoded RAN Site ID", re.compile(r"\bRAN_(?:BB|MRN|DSO)[A-Z0-9_]*\b")),
    ("Hardcoded GPON Splitter ID", re.compile(r"\bSPL-[A-Z0-9-]+\b")),
    ("Hardcoded Microwave Link ID", re.compile(r"\bMW-(?:DSO|ACAD)[A-Z0-9-]*\b")),
    ("Hardcoded Subsea System ID", re.compile(r"\bSUBSEA-[A-Z0-9-]+\b")),
    ("Hardcoded Customer/Service ID", re.compile(r"\b(?:CUST-10\d\d|SVC-[A-Z0-9-]+)\b")),
    ("Hardcoded Dubai POP/Node Tuple", re.compile(r"\b(?:C_EGB|C_MHH|C_AQI|C_JLC|C_SODC|J_DG|J_RAK|J_GB)\b")),
]


def _iter_code_string_literals(py_file: Path) -> list[tuple[int, str]]:
    """Yield `(lineno, string_value)` for executable string literals (excluding module/class/func docstrings)."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                docstring_nodes.add(id(node.body[0].value))

    literals: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_nodes:
            literals.append((node.lineno, node.value))
    return literals


def main() -> int:
    violations: list[str] = []
    scanned = 0
    for py_file in sorted(BACKEND_DIR.rglob("*.py")):
        scanned += 1
        for lineno, val in _iter_code_string_literals(py_file):
            for label, pat in FORBIDDEN_PATTERNS:
                m = pat.search(val)
                if m:
                    rel = py_file.relative_to(ROOT)
                    violations.append(f"  - {rel}:{lineno} [{label}] matched '{m.group(0)}' in literal: {val!r}")

    if violations:
        print("❌ Topology-Agnostic Architecture Gate FAILED! Hardcoded dataset IDs found in backend/app/:")
        for v in violations:
            print(v)
        return 1

    print(f"✅ Topology-Agnostic Architecture Gate PASSED ({scanned} backend Python modules verified clean).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
