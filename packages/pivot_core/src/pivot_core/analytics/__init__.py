"""Deterministic analytics on simulated matches: statistics (B05), momentum and player ratings."""

from .changepoint import DetectorParams, PivotDetector, detect_candidates, key_events, severity
from .momentum import momentum_series
from .ratings import player_match_stats
from .stats import StatCalculator

__all__ = [
    "DetectorParams", "PivotDetector", "StatCalculator", "detect_candidates", "key_events",
    "momentum_series", "player_match_stats", "severity",
]
