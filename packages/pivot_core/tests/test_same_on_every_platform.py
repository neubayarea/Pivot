"""Bx7: the same seed plays the same match on every machine (Windows, Linux, macOS on arm64).

The fingerprints below were made on Windows (x86-64); CI runs this on a Mac (arm64). Seeds 4
and 17 are two of the matches that used to end differently there. Fingerprints hash the raw
events and the exact player positions (scripts/sim_fingerprint.py).

When a change is meant to alter the run of play, rerun these seeds with
`uv run scripts/sim_fingerprint.py --seeds 4 17 --preset-seeds 29` and update FINGERPRINTS,
saying so in the PR.
"""

import sys
from pathlib import Path

import pytest

from pivot_core.sim import DEMO_1021, build_demo_match, simulate

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from sim_fingerprint import fingerprint  # noqa: E402

FINGERPRINTS = {
    "seed 4": "0-0 events=2027 ev:23801f73fea611bc pos:b9e6c6d2cfc85ed8 frames:55efe7b88e413c07",
    "seed 17": "2-1 events=1912 ev:ba2a6863dc1b1fd3 pos:839d7f2326af4ba3 frames:8bb13a64ce842b7a",
    "demo-1021 seed 29": "3-1 events=1726 ev:31a91007251c8990 pos:9dc094627f8d2a22 frames:dbe8b98272f2c006",
}


@pytest.mark.parametrize("name", sorted(FINGERPRINTS))
def test_bx7_same_seed_same_match_on_every_platform(name):
    if name.startswith("demo"):
        out = simulate(DEMO_1021.build(int(name.split()[-1])), plants=list(DEMO_1021.plants))
    else:
        out = simulate(build_demo_match(int(name.split()[-1])))
    assert fingerprint(out) == FINGERPRINTS[name]
