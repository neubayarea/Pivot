"""One pivot, written for one viewer: audience, language, focus team and player (A11; FR-23, FR-24, FR-25).

The worker writes the default version (analyst, English) and stores it on the pivot. Any other
set of `ViewerPrefs` is written here on first request, with the D line's own parts:

    explainer (D11/D12) ⇄ verifier, up to MAX_CHECKS ──fail / no model──> template ──> verifier

Every version passes the same Verifier as the default one. A version that passes is stored
through the repository, keyed by (pivot_id, prefs), so the next request for it does no model call.
If not even the template passes, the default version is returned, unstored, and `prefs`
says so: the caller always gets a card, never an error.

The worker code is only called, not changed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass

from pydantic import ValidationError

from pivot_core.domain import Narrative, Pivot, PivotCandidate, Verdict, VerifierIssue, ViewerPrefs
from pivot_core.ports import MatchRepository
from pivot_worker import explainer
from pivot_worker.context import known_ids
from pivot_worker.detect import EXPLAINER_TIMEOUT, MatchView, StatsFactory, load_view, with_computed
from pivot_worker.models import ModelClient, ModelUnavailable, model_client_from_env
from pivot_worker.template import template_explain
from pivot_worker.verifier import verify

log = logging.getLogger("pivot_api.personalize")

MAX_CHECKS = 2                                # a viewer is waiting on this request: one draft plus one rewrite
MAX_CONCURRENT = 4                            # versions written at once (a pivot list asks for several)
SWING_MINUTES = 5


@dataclass(frozen=True)
class Personalized:
    pivot: Pivot
    prefs: ViewerPrefs                        # what the narrative was actually written for


def candidate_of(pivot: Pivot, view: MatchView) -> PivotCandidate:
    """The detector's candidate, rebuilt from a stored pivot (the explainer and template work from it)."""
    m = pivot.minute

    def mean(lo: int, hi: int) -> float:
        values = [x.momentum for x in view.metrics if lo <= x.minute < hi]
        return sum(values) / len(values) if values else 0.0

    swing = mean(m, m + SWING_MINUTES) - mean(m - SWING_MINUTES, m)
    return PivotCandidate(match_id=pivot.match_id, minute=m, direction=pivot.direction, cusum_stat=0.0,
                          swing=swing, key_event_ids=pivot.trigger_event_ids,
                          window=(max(0, m - SWING_MINUTES), min(180, m + SWING_MINUTES)))


class Personalizer:
    def __init__(self, repo: MatchRepository, models: ModelClient | None = None,
                 stats_factory: StatsFactory | None = None) -> None:
        self.repo, self.models, self.stats_factory = repo, models, stats_factory
        self._locks: defaultdict[tuple[str, ViewerPrefs], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._slots = asyncio.Semaphore(MAX_CONCURRENT)

    async def personalize(self, pivot: Pivot, prefs: ViewerPrefs) -> Personalized:
        base = pivot.narrative
        if base is None:                      # pending: nothing written yet, in any version
            return Personalized(pivot, prefs)
        if prefs == base.prefs:
            return Personalized(pivot, base.prefs)
        async with self._locks[(pivot.pivot_id, prefs)]:   # two viewers asking at once: write it once
            narrative = await self._stored(pivot, prefs)
            if narrative is None:
                async with self._slots:
                    narrative = await self._write(pivot, prefs)
                if narrative is None:
                    log.warning("%s: no version for %s passed the verifier; serving the default",
                                pivot.pivot_id, prefs.model_dump())
                    return Personalized(pivot, base.prefs)
                await self.repo.upsert_narrative(pivot.match_id, pivot.pivot_id, narrative)
        return Personalized(pivot.model_copy(update={"narrative": narrative}), narrative.prefs)

    async def _stored(self, pivot: Pivot, prefs: ViewerPrefs) -> Narrative | None:
        narrative = await self.repo.get_narrative(pivot.match_id, pivot.pivot_id, prefs)
        # Written for an earlier run of this pivot (the worker wrote it again since): stale.
        return narrative if narrative and narrative.chain_id == pivot.chain_id else None

    async def _write(self, pivot: Pivot, prefs: ViewerPrefs) -> Narrative | None:
        view = await load_view(self.repo, pivot.match_id, self.stats_factory)
        candidate = candidate_of(pivot, view)
        checks = 0
        if self.models is not None:
            feedback = None
            for checks in range(1, MAX_CHECKS + 1):
                try:
                    draft = await self._draft(candidate, view, prefs, pivot.chain_id, feedback)
                except ModelUnavailable as e:
                    log.info("%s: explainer unavailable (%s); using the template", pivot.pivot_id, e)
                    break
                except ValidationError as e:
                    feedback = Verdict(passed=False, issues=[VerifierIssue(code="schema_invalid",
                                                                           message=e.errors()[0]["msg"])])
                    continue
                feedback = self._verify(draft, candidate, view)
                if feedback.passed:
                    return with_computed(draft, view.stats).model_copy(update={"verifier_attempts": checks})
        card = template_explain(candidate, events=view.events, stats=view.stats, team_names=view.team_names,
                                prefs=prefs, chain_id=pivot.chain_id, verifier_attempts=checks,
                                context=view.context)
        return card if self._verify(card, candidate, view).passed else None

    async def _draft(self, candidate: PivotCandidate, view: MatchView, prefs: ViewerPrefs, chain_id: str,
                     feedback: Verdict | None) -> Narrative:
        _, messages = explainer.build_messages(
            candidate, events=view.events, stats=view.stats, team_names=view.team_names, prefs=prefs,
            player_names=view.player_names, context=view.context, feedback=feedback)
        reply = await self.models.complete_json("standard", messages, timeout=EXPLAINER_TIMEOUT)
        return explainer.parse_draft(reply.text, prefs=prefs, chain_id=chain_id)

    def _verify(self, narrative: Narrative, candidate: PivotCandidate, view: MatchView) -> Verdict:
        return verify(narrative, pivot_minute=candidate.minute, events=view.events, stats=view.stats,
                      context_ids=known_ids(view.context))


def personalizer_from_env(repo: MatchRepository) -> Personalizer:
    """Same model choice as the worker: the explainer only with `PIVOT_PIPELINE=detect`, else the template."""
    models = model_client_from_env() if os.getenv("PIVOT_PIPELINE", "fake") == "detect" else None
    return Personalizer(repo, models)
