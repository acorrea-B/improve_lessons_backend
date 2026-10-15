"""Static lint (T027, quickstart.md § 9.3): the build fails if any
module in ``app/`` outside ``app/core/time/`` uses an implicit local time."""



from __future__ import annotations

import ast
import unittest
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from zoneinfo import ZoneInfo

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

# Modules allowed to construct a non-UTC ZoneInfo explicitly: the central
# time helpers and the time-boundary strategies.
LOCAL_ZONE_ALLOWED = ("app/core/time/", "app/core/strategies/")

UTC_ARGUMENTS = ("UTC", "timezone.utc", "utc")


def app_sources():
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT.parent).as_posix()
        yield relative, path


class TestNoImplicitLocalTime(unittest.TestCase):
    """quickstart.md § 9.3 — the static lint."""

    def _violations(self) -> list[str]:
        problems: list[str] = []
        for relative, path in app_sources():
            source = path.read_text()
            if relative.startswith("app/core/time/"):
                continue
            problems.extend(self._scan_for_now(relative, source))
            problems.extend(self._scan_for_pytz(relative, source))
            problems.extend(self._scan_for_astimezone(relative, source))
        return problems

    def _scan_for_now(self, relative: str, source: str) -> list[str]:
        violations: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name == "now" and not node.args and not node.keywords:
                    # datetime.now() with no tz argument.
                    owner = getattr(node.func, "value", None)
                    owner_name = (
                        getattr(owner, "id", "") or getattr(owner, "attr", "")
                        if owner is not None else ""
                    )
                    if owner_name == "datetime":
                        violations.append(f"{relative}: datetime.now() without tz (line {node.lineno})")
        return violations

    def _scan_for_pytz(self, relative: str, source: str) -> list[str]:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pytz":
                        return [f"{relative}: import pytz forbidden (line {node.lineno})"]
            if isinstance(node, ast.ImportFrom) and node.module == "pytz":
                return [f"{relative}: import pytz forbidden (line {node.lineno})"]
        return []

    def _scan_for_astimezone(self, relative: str, source: str) -> list[str]:
        if relative.startswith(LOCAL_ZONE_ALLOWED):
            return []
        violations: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "astimezone":
                arg = node.args[0] if node.args else node.keywords[0].value if node.keywords else None
                arg_text = ast.unparse(arg) if arg is not None else ""
                if arg_text not in UTC_ARGUMENTS and "utc" not in arg_text.lower():
                    violations.append(
                        f"{relative}: astimezone to a non-UTC zone (line {node.lineno})"
                    )
        return violations

    def test_no_implicit_local_time(self):
        violations = self._violations()
        self.assertEqual(violations, [], "\n".join(violations))