"""Bx7: the same seed plays the same match on every machine (Windows, Linux, macOS on arm64).

The fingerprints below were made on Windows (x86-64) and match the Mac CI runner (arm64). Seeds
4 and 17 are two of the matches that used to end differently: np.argsort's default sort breaks
ties between equally distant players differently on the two chips, so a different player was
sent to press. Fingerprints hash the raw events and the exact player positions
(scripts/sim_fingerprint.py).

When a change is meant to alter the run of play, rerun these seeds with
`uv run scripts/sim_fingerprint.py --seeds 4 17 --preset-seeds 29` and update FINGERPRINTS,
saying so in the PR. Ax44 (set-piece positions) changed all three.
"""

import sys
from pathlib import Path

import pytest

from pivot_core.sim import DEMO_1021, build_demo_match, simulate

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from sim_fingerprint import fingerprint  # noqa: E402

FINGERPRINTS = {
    "seed 4": "1-0 events=1961 ev:95b06afb642f3e5c pos:65301029b506b448 frames:9e2f882e8d648a5d",
    "seed 17": "1-2 events=1712 ev:d6b7c17b146b2e14 pos:49ab15fca98d34ad frames:7a57e0ea0b517bd3",
    "demo-1021 seed 29": "5-1 events=1681 ev:03dc318d17b06c90 pos:615a973763fb0e2a frames:a9391ff19862baec",
}


@pytest.mark.parametrize("name", sorted(FINGERPRINTS))
def test_bx7_same_seed_same_match_on_every_platform(name):
    if name.startswith("demo"):
        out = simulate(DEMO_1021.build(int(name.split()[-1])), plants=list(DEMO_1021.plants))
    else:
        out = simulate(build_demo_match(int(name.split()[-1])))
    assert fingerprint(out) == FINGERPRINTS[name]
