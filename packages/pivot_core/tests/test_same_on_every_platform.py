"""Bx7: the same seed plays the same match on every machine (Windows, Linux, macOS on arm64).

The fingerprints below were made on Windows (x86-64) and match the Mac CI runner (arm64). Seeds
4 and 17 are two of the matches that used to end differently: np.argsort's default sort breaks
ties between equally distant players differently on the two chips, so a different player was
sent to press. Fingerprints hash the raw events and the exact player positions
(scripts/sim_fingerprint.py).

When a change is meant to alter the run of play, rerun these seeds with
`uv run scripts/sim_fingerprint.py --seeds 4 17 --preset-seeds 29` and update FINGERPRINTS,
saying so in the PR. Ax44 changed only `pos` and `frames` (set-piece positions in the tracking
frames); `ev`, the score and the event count are as before.
"""

import sys
from pathlib import Path

import pytest

from pivot_core.sim import DEMO_1021, build_demo_match, simulate

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from sim_fingerprint import fingerprint  # noqa: E402

FINGERPRINTS = {
    "seed 4": "1-0 events=1894 ev:26fe64692a092b42 pos:dc81a91d7cb4b701 frames:271abeadc7dd4281",
    "seed 17": "2-2 events=1834 ev:76951f21fd03bf8c pos:43d183d22d653f16 frames:98f3acce22a397a7",
    "demo-1021 seed 29": "3-1 events=1726 ev:31a91007251c8990 pos:4f6c0a2fb0958d04 frames:8d491110d2988c3d",
}


@pytest.mark.parametrize("name", sorted(FINGERPRINTS))
def test_bx7_same_seed_same_match_on_every_platform(name):
    if name.startswith("demo"):
        out = simulate(DEMO_1021.build(int(name.split()[-1])), plants=list(DEMO_1021.plants))
    else:
        out = simulate(build_demo_match(int(name.split()[-1])))
    assert fingerprint(out) == FINGERPRINTS[name]
