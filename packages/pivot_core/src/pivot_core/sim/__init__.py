"""Match simulator: per-second positional engine (ADR-0014), movement model and What-if reruns."""

from .engine import Engine, SimOutput, simulate
from .presets import DEMO_1021, PRESETS, Preset
from .squads import build_demo_match, build_team
from .whatif import run_whatif

__all__ = [
    "DEMO_1021", "PRESETS", "Engine", "Preset", "SimOutput", "build_demo_match", "build_team", "run_whatif",
    "simulate",
]
