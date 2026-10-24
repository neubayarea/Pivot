"""Match simulator: per-second positional engine (ADR-0014) and movement model."""

from .engine import Engine, SimOutput, simulate
from .squads import build_demo_match, build_team

__all__ = ["Engine", "SimOutput", "build_demo_match", "build_team", "simulate"]
