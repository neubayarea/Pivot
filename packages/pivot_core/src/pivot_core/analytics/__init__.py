"""Deterministic analytics on simulated matches: statistics (B05), momentum and player ratings."""

from .momentum import momentum_series
from .ratings import player_match_stats
from .stats import StatCalculator

__all__ = ["StatCalculator", "momentum_series", "player_match_stats"]
