"""Static import-direction lint (T026, plan.md § Project Structure).

Enforced by the test suite: any forbidden import direction fails the build.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

FORBIDDEN = {
    "app/api": ("app.adapters",),
    "app/services": ("app.adapters", "app.api"),
    "app/adapters": ("app.api", "app.services"),
    "app/core": ("app.api", "app.services", "app.adapters"),
}


def module_of(import_text: str) -> str:
    return import_text.split(" ")[0]


def imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def violations() -> list[str]:
    problems: list[str] = []
    layers = {"api": APP_ROOT / "api", "services": APP_ROOT / "services", "adapters": APP_ROOT / "adapters", "core": APP_ROOT / "core"}
    for layer_name, layer_root in layers.items():
        forbidden_prefixes = FORBIDDEN[f"app/{layer_name}"]
        for path in sorted(layer_root.rglob("*.py")):
            relative = path.relative_to(APP_ROOT.parent).as_posix()
            for imported in imports_of(path):
                for prefix in forbidden_prefixes:
                    if imported == prefix or imported.startswith(prefix + "."):
                        # core may not import adapters/api/services at all;
                        # adapters may import core only.
                        violations.append(f"{relative}: imports {imported} (forbidden: {prefix})")
    return problems


class TestImportDirection(unittest.TestCase):
    def test_forbidden_imports_fail_the_build(self):
        v = violations()
        self.assertEqual(v, [], "\n".join(v))


if __name__ == "__main__":
    unittest.main()