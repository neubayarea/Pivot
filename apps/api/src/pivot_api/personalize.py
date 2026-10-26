"""One pivot, written for one viewer: audience, language, focus team and player (A11; FR-23, FR-24, FR-25).

The worker writes the default version (analyst, English) and stores it on the pivot. Any other
set of `ViewerPrefs` is written here on first request, with the D line's own parts:

    explainer (D11/D12) ⇄ verifier, up to MAX_CHECKS ──fail / no model──> template ──> verifier

A Chinese or Spanish version is a translation (Ax35, #220): the verified English version for the
same audience and focus is written (or read) first, and the model only translates its headline and
sentence texts. Evidence ids, claims and context ids are copied over, so the numbers cannot drift; the
Verifier still checks the result (numbers against the claims, `wrong_script`, players on the pitch).

    English llm version ──> translate ⇄ verifier, up to MAX_CHECKS ──fail──> template ──> verifier
    English template version ──> template in the target language ──> verifier
    no English version ──> the explainer path above

Every version passes the same Verifier as the default one. A version that passes is stored
through the repository, keyed by (pivot_id, prefs), so the next request for it does no model call.
If not even the template passes, or any step raises (a bug in a stat source, say), the default
version is returned, unstored, and `prefs` says so: the caller always gets a card, never an error.

The worker code is only called, not changed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from pivot_core.domain import Narrative, Pivot, PivotCandidate, Verdict, VerifierIssue, ViewerPrefs
from pivot_core.ports import MatchRepository
from pivot_worker import explainer
from pivot_worker.detect import EXPLAINER_TIMEOUT, MatchView, StatsFactory, load_view, match_stats, with_computed
from pivot_worker.languages import INSTRUCTIONS, MAX_HEADLINE, wrong_script
from pivot_worker.models import ModelClient, ModelUnavailable, model_client_from_env
from pivot_worker.template import template_explain
from pivot_worker.verifier import verify

log = logging.getLogger("pivot_api.personalize")

MAX_CHECKS = 2                                # a viewer is waiting on this request: one draft plus one rewrite
MAX_CONCURRENT = 4                            # versions written at once (a pivot list asks for several)
SWING_MINUTES = 5
LANGUAGE_NAMES = {"zh": "Simplified Chinese (简体中文)", "es": "Spanish (español neutro)"}
TRANSLATE_PROMPT = """You translate football match commentary cards from English into {language}.
Return JSON only: {{"headline": "...", "sentences": ["...", ...]}}, one translated text per input sentence,
in the same order. Translate the meaning faithfully and naturally for a {audience}; add nothing and drop nothing.
Keep every number exactly as written, with the same digits (no number words), and minutes as 61'.
Keep team and player names exactly as given, in their original Latin spelling.
The headline has no digits and at most {headline} {unit}. {instruction}"""


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
                source = await self._english(pivot, prefs) if prefs.language != "en" else None
                async with self._slots:
                    try:
                        narrative = await self._write(pivot, prefs, source)
                    except Exception:
                        log.warning("%s: writing the version for %s failed; serving the default",
                                    pivot.pivot_id, prefs.model_dump(), exc_info=True)
                        return Personalized(pivot, base.prefs)
                if narrative is None:
                    log.warning("%s: no version for %s passed the verifier; serving the default",
                                pivot.pivot_id, prefs.model_dump())
                    return Personalized(pivot, base.prefs)
                await self.repo.upsert_narrative(pivot.match_id, pivot.pivot_id, narrative)
        return Personalized(pivot.model_copy(update={"narrative": narrative}), narrative.prefs)

    async def prewarm(self, match_id: str, languages: Sequence[str], wait: float = 1800.0) -> int:
        """Write every pivot of a match in `languages` for both audiences ahead of the viewers (Ax35).

        One version at a time (a 2-core VM, a rate-limited model). Pivots come from the worker, so this
        waits (up to `wait` seconds) for them to be written first. Returns how many versions are stored.
        """
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            pivots = await self.repo.list_pivots(match_id)
            if pivots and all(p.status == "rejected" or p.narrative is not None for p in pivots):
                break
            await asyncio.sleep(10)
        written = 0
        for pivot in await self.repo.list_pivots(match_id):
            if pivot.status == "rejected" or pivot.narrative is None:
                continue
            for language in languages:
                for audience in ("analyst", "fan"):
                    prefs = ViewerPrefs(audience=audience, language=language)
                    try:
                        written += (await self.personalize(pivot, prefs)).prefs == prefs
                    except Exception:
                        log.warning("%s: prewarm of %s failed", pivot.pivot_id, prefs.model_dump(), exc_info=True)
        return written

    async def _stored(self, pivot: Pivot, prefs: ViewerPrefs) -> Narrative | None:
        narrative = await self.repo.get_narrative(pivot.match_id, pivot.pivot_id, prefs)
        # Written for an earlier run of this pivot (the worker wrote it again since): stale.
        if narrative is None or narrative.chain_id != pivot.chain_id:
            return None
        # Stored before the Verifier checked the language (#184): an English card kept as the Chinese one.
        texts = [narrative.headline, *(s.text for s in narrative.sentences)]
        return None if any(wrong_script(text, prefs.language) for text in texts) else narrative

    async def _english(self, pivot: Pivot, prefs: ViewerPrefs) -> Narrative | None:
        """The verified English version a translation starts from, or None if there is none."""
        english = prefs.model_copy(update={"language": "en"})
        try:
            result = await self.personalize(pivot, english)
        except Exception:
            log.warning("%s: no English version to translate", pivot.pivot_id, exc_info=True)
            return None
        return result.pivot.narrative if result.prefs == english else None

    async def _write(self, pivot: Pivot, prefs: ViewerPrefs, source: Narrative | None = None) -> Narrative | None:
        view = await load_view(self.repo, pivot.match_id, self.stats_factory)
        candidate = candidate_of(pivot, view)
        checks = 0
        if source is not None:
            if source.source == "llm" and self.models is not None:
                translated, checks = await self._translate(pivot, source, prefs, candidate, view)
                if translated is not None:
                    return translated
            # An English template, or a translation that never passed: the template in this language.
        elif self.models is not None:
            feedback, previous = None, None
            for checks in range(1, MAX_CHECKS + 1):
                try:
                    previous = await self._ask(candidate, view, prefs, feedback, previous)
                except ModelUnavailable as e:
                    log.info("%s: explainer unavailable (%s); using the template", pivot.pivot_id, e)
                    break
                except Exception:
                    log.warning("%s: explainer failed; using the template", pivot.pivot_id, exc_info=True)
                    break
                try:
                    draft = explainer.parse_draft(previous, prefs=prefs, chain_id=pivot.chain_id)
                except ValidationError as e:
                    feedback = Verdict(passed=False, issues=[VerifierIssue(code="schema_invalid",
                                                                           message=e.errors()[0]["msg"])])
                    continue
                try:
                    feedback = self._verify(draft, candidate, view)
                except Exception:             # a rewrite cannot fix it; the template still gets its check
                    log.warning("%s: verifier failed on the draft; using the template", pivot.pivot_id,
                                exc_info=True)
                    break
                if feedback.passed:
                    return with_computed(draft, view.stats).model_copy(update={"verifier_attempts": checks})
        card = template_explain(candidate, events=view.events, stats=view.stats, team_names=view.team_names,
                                prefs=prefs, chain_id=pivot.chain_id, verifier_attempts=checks,
                                context=explainer.shown_context(candidate, view.events, view.context))
        return card if self._verify(card, candidate, view).passed else None

    async def _translate(self, pivot: Pivot, source: Narrative, prefs: ViewerPrefs, candidate: PivotCandidate,
                         view: MatchView) -> tuple[Narrative | None, int]:
        """`source` translated into `prefs.language`, checked; (None, checks) if no attempt passed."""
        lang = prefs.language
        messages = translation_messages(source, prefs)
        checks = 0
        for checks in range(1, MAX_CHECKS + 1):
            try:
                reply = await self.models.complete_json("standard", messages, timeout=EXPLAINER_TIMEOUT)
            except ModelUnavailable as e:
                log.info("%s: translator unavailable (%s); using the template", pivot.pivot_id, e)
                break
            except Exception:
                log.warning("%s: translator failed; using the template", pivot.pivot_id, exc_info=True)
                break
            messages = messages[:2] + [{"role": "assistant", "content": reply.text}]
            try:
                draft = translated_narrative(source, reply.text, prefs, checks, pivot.chain_id)
            except (ValueError, TypeError, KeyError) as e:
                messages.append({"role": "user", "content": f"That reply was not usable ({e}). Try again."})
                continue
            try:
                verdict = self._verify(draft, candidate, view)
            except Exception:
                log.warning("%s: verifier failed on the translation", pivot.pivot_id, exc_info=True)
                break
            if verdict.passed:
                return with_computed(draft, view.stats), checks
            log.info("%s: %s translation rejected: %s", pivot.pivot_id, lang, [i.code for i in verdict.issues])
            fixes = "\n".join(f"- {i.code}: {i.message}" for i in verdict.issues)
            messages.append({"role": "user", "content": f"The Verifier rejected that translation:\n{fixes}\n"
                                                        "Fix it and return the whole card again."})
        return None, checks

    async def _ask(self, candidate: PivotCandidate, view: MatchView, prefs: ViewerPrefs,
                   feedback: Verdict | None, previous: str | None) -> str:
        """The explainer's raw reply; on a rewrite it sees the Verifier's verdict and its own last reply."""
        _, messages = explainer.build_messages(
            candidate, events=view.events, stats=view.stats, team_names=view.team_names, prefs=prefs,
            player_names=view.player_names, context=view.context, feedback=feedback, previous=previous)
        reply = await self.models.complete_json("standard", messages, timeout=EXPLAINER_TIMEOUT)
        return reply.text

    def _verify(self, narrative: Narrative, candidate: PivotCandidate, view: MatchView) -> Verdict:
        return verify(narrative, pivot_minute=candidate.minute, events=view.events, stats=view.stats,
                      context=explainer.shown_context(candidate, view.events, view.context),
                      team_names=view.team_names)


def translation_messages(source: Narrative, prefs: ViewerPrefs) -> list[dict[str, str]]:
    """The translator's request: `source`'s headline and sentence texts, in order, into `prefs.language`."""
    lang = prefs.language
    system = TRANSLATE_PROMPT.format(
        language=LANGUAGE_NAMES[lang], audience="football fan" if prefs.audience == "fan" else "match analyst",
        headline=MAX_HEADLINE[lang], unit="characters" if lang == "zh" else "words", instruction=INSTRUCTIONS[lang])
    user = json.dumps({"headline": source.headline, "sentences": [s.text for s in source.sentences]},
                      ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def translated_narrative(source: Narrative, raw: str, prefs: ViewerPrefs, checks: int,
                         chain_id: str | None = None) -> Narrative:
    """`source` with the translated texts from the model's reply; everything else is copied unchanged."""
    reply = json.loads(raw)
    texts = reply["sentences"]
    if not isinstance(reply["headline"], str) or not reply["headline"].strip():
        raise ValueError("headline missing")
    if len(texts) != len(source.sentences) or not all(isinstance(t, str) and t.strip() for t in texts):
        raise ValueError(f"expected {len(source.sentences)} sentence texts")
    return source.model_copy(update={
        "prefs": prefs, "headline": reply["headline"].strip(), "verifier_attempts": checks,
        "chain_id": chain_id or source.chain_id,
        "sentences": [s.model_copy(update={"text": t.strip()}) for s, t in zip(source.sentences, texts)]})


def personalizer_from_env(repo: MatchRepository) -> Personalizer:
    """Same model choice as the worker: the explainer only with `PIVOT_PIPELINE=detect`, else the template."""
    models = model_client_from_env() if os.getenv("PIVOT_PIPELINE", "fake") == "detect" else None
    return Personalizer(repo, models, stats_factory=match_stats)
