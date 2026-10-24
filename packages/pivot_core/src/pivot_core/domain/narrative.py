"""Viewer preferences and the text the agents write for them.

The same pivot, what-if result or recap is written once per set of viewer
preferences. Evidence and numbers stay the same across versions; only the
wording and point of view change, so the Verifier checks every version the same way.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Model, Side
from .stats import Claim

Audience = Literal["analyst", "fan"]
Language = Literal["en", "zh", "es"]


class ViewerPrefs(Model):
    audience: Audience = "analyst"
    language: Language = "en"
    focus_team: Side | None = None            # tell the story from this team's side
    focus_player_id: str | None = None        # highlight this player's events and stats


class ExplanationSentence(Model):
    text: str                                 # at most 30 words (checked by the Verifier)
    evidence_ids: Annotated[list[str], Field(min_length=1, max_length=4)]
    claims: list[Claim] = []                  # every number in `text` must appear here
    # Off-pitch facts the sentence relies on ("back at his former club"): effect_id, news_id,
    # stint_id or relationship_id from the match context. The Verifier checks they exist.
    context_ids: Annotated[list[str], Field(max_length=3)] = []


class Narrative(Model):
    prefs: ViewerPrefs
    headline: str                             # card title, at most 8 words, no digits
    sentences: Annotated[list[ExplanationSentence], Field(min_length=1, max_length=8)]
    source: Literal["llm", "template"]        # "template" = Verifier gave up and we degraded
    verifier_attempts: Annotated[int, Field(ge=0, le=3)] = 0
    chain_id: str | None = None               # agent chain that wrote it, same as the trace id
