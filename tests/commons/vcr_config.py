"""VCR cassette configuration (T029): records/replays outbound HTTP for
the notification adapter tests."""

from __future__ import annotations

from pathlib import Path

import vcr as vcr_module

CASSETTE_DIR = Path(__file__).resolve().parents[1] / "vcr_cassettes"


def make_vcr(cassette_name: str):
    return vcr_module.VCR(
        cassette_library_dir=str(CASSETTE_DIR),
        record_mode="none",  # never hit the network from the suite
        match_on=("method", "path"),
        filter_headers=("authorization",),
    )