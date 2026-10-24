"""Match simulator: per-second positional engine (ADR-0014) and movement model."""

from .engine import Engine, SimOutput, simulate
from .presets import DEMO_1021, PRESETS, Preset
from .squads import build_demo_match, build_team

__all__ = [
    "DEMO_1021", "PRESETS", "Engine", "Preset", "SimOutput", "build_demo_match", "build_team", "simulate",
]
