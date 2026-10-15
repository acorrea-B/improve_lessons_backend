"""Local wall-clock field type (contract § Conventions).

``HH:MM`` strings are NOT instants: they are validated for shape only and
evaluated in the user's time zone at the application boundary.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _validate_hhmm(value: str) -> str:
    if not _HHMM.match(value):
        raise ValueError(
            "invalid_HHMM: local wall-clock fields must be HH:MM strings "
            "(they are not instants)."
        )
    return value


HHMMString = Annotated[str, AfterValidator(_validate_hhmm)]