"""TemplateExplainer: the fallback card when the Explainer cannot pass the Verifier (D05).

It builds up to three sentences from the key events and one recomputed stat change, so
what it writes passes the same Verifier. With a focus team it tells the story from their side,
even when the match turned against them; fan versions write only the newer value of the change.
It must never raise: if anything goes wrong it returns a minimal card that still fits the
Narrative contract. It only cites events in the Verifier's evidence window; when there are none,
it writes only the momentum sentence, which needs no evidence, and cites `NO_EVIDENCE`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, PivotCandidate, StatRef, ViewerPrefs
from pivot_core.domain.stats import STAT_UNITS, Claim

from .context import ContextItem, involved_in
from .languages import FAN_LABELS, LABELS, MAX_HEADLINE, PHRASES, length
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, NO_EVIDENCE, StatSource
from .vocabulary import STAT_TERMS, UNIT_SUFFIX

# Stats the template tries, in order of preference when changes are equal.
CANDIDATE_METRICS = ("threat_total", "passes_final_third", "box_entries", "shots", "pressures", "xg")
# Fan versions only count things a fan can picture: no index (threat) and no xG, whose numbers mean
# nothing without the model behind them. Each reads as a noun after "Rovers'" (possession has its own
# sentence), and the sentence writes one number, the newer value.
FAN_METRICS = ("shots", "shots_on_target", "box_entries", "passes_final_third", "possession_pct")
# English fan nouns where StatTerm.fan_label is a clause ("times they got into the box").
FAN_NOUNS_EN = {"box_entries": "trips into the box"}
# How a relationship reads in a sentence; either person may come first, so none of these has a direction.
RELATIONS_EN = {
    "former_teammate": "{a} and {b} used to be teammates.",
    "national_teammate": "{a} and {b} play together for their country.",
    "former_coach": "{a} and {b} have worked together before, as coach and player.",
    "former_player": "{a} and {b} have worked together before, as coach and player.",
    "mentor": "{a} and {b} go back a long way, as mentor and pupil.",
    "friend": "{a} and {b} are friends off the pitch.",
    "rival": "{a} and {b} are old rivals.",
    "feud": "{a} and {b} do not get on.",
}
# Kinds the template turns into a sentence, best story first. Effects ("pressure rating 58") are left
# out: they are notes for the simulator and repeat what these say.
CONTEXT_KINDS = ("former_club", "relationship", "news")
COMPARE_MINUTES = 5
_DECIMALS = {"count": 0, "pct": 0, "xg": 2, "index": 2, "m": 0, "km": 1, "ratio": 1}


def format_value(value: float, unit: str) -> str:
    return f"{value:.{_DECIMALS[unit]}f}{UNIT_SUFFIX[unit]}"


def _trigger(event: MatchEvent, team: str, lang: str = "en") -> tuple[str, str]:
    """Headline and first sentence for the event that set the pivot off."""
    kind = "goal" if event.type == "shot" and event.shot_outcome == "goal" else event.type
    phrases = PHRASES[lang]
    if kind not in ("goal", "card", "substitution", "tactical_shift", "injury"):
        return "", ""
    return (phrases[f"{kind}_h"].format(team=team),
            phrases[kind].format(team=team, at=event.clock_label))


def _label(metric: str, lang: str, fan: bool) -> str:
    if lang in LABELS:
        return (FAN_LABELS if fan else LABELS)[lang][metric]
    term = STAT_TERMS[metric]
    return FAN_NOUNS_EN.get(metric, term.fan_label) if fan else term.label


# "The next five minutes" reads as the minutes after the event just named; when that event came earlier than
# the pivot, the stat sentence says the minutes after the game turned instead (#396).
_LATER = {"en": ("in the next five minutes", "in the five minutes after the game turned"),
          "zh": ("此后五分钟", "比赛转折后五分钟"),
          "es": ("En los cinco minutos siguientes", "En los cinco minutos tras el giro del partido")}


def _stat_sentence(c: PivotCandidate, side: str, team: str, stats: StatSource, evidence: list[str],
                   fan: bool = False, lang: str = "en", found: Sequence[MatchEvent] = ()) -> ExplanationSentence | None:
    """The biggest change for `side`: a rise if the match turned their way, a fall if it turned against them."""
    m = c.minute
    before, after = (max(0, m - COMPARE_MINUTES), m), (m, m + COMPARE_MINUTES)
    gaining = side == c.direction
    best = None
    for metric in FAN_METRICS if fan else CANDIDATE_METRICS:
        try:
            refs = [StatRef(metric=metric, team=side, window=w) for w in (before, after)]
            a, b = (stats.compute(r) for r in refs)
        except Exception:
            continue
        unit = STAT_UNITS[metric]
        if format_value(a, unit) == format_value(b, unit):
            continue
        score = ((b - a > 0) == gaining, abs(b - a) / (abs(a) + 1))
        if best is None or score > best[0]:
            best = (score, metric, refs, a, b)
    if best is None:
        return None
    _, metric, refs, a, b = best
    unit = STAT_UNITS[metric]
    phrases, label = PHRASES[lang], _label(metric, lang, fan)
    verb = "rose" if b > a else "fell"
    if f"{verb}_pl" in phrases and label.startswith(("los ", "las ")):     # plural subject, plural verb
        verb += "_pl"
    key = "stat_fan" if fan else "stat"
    text = phrases.get(f"{key}_{metric}", phrases[key]).format(
        team=team, owner=possessive(team), label=label, verb=phrases[verb],
        a=format_value(a, unit), b=format_value(b, unit))
    if c.minute - min((e.minute for e in found), default=c.minute) >= 3:
        # Set off by an earlier event (#396: a substitution at 82', a pivot at 88'): the windows are the pivot's.
        text = text.replace(*_LATER[lang])
    if lang == "es":
        text = text[0].upper() + text[1:]
    claims = [Claim(value=v, unit=unit, stat_ref=r) for v, r in ((a, refs[0]), (b, refs[1]))]
    return ExplanationSentence(text=text, evidence_ids=evidence, claims=claims)


def _evidence(c: PivotCandidate, events: Mapping[str, MatchEvent]) -> list[MatchEvent]:
    lo, hi = c.minute - EVIDENCE_BEFORE, c.minute + EVIDENCE_AFTER
    keyed = [events[e] for e in c.key_event_ids if e in events and lo <= events[e].minute <= hi]
    if keyed:
        return keyed
    nearby = sorted((e for e in events.values() if lo <= e.minute <= hi), key=lambda e: abs(e.minute - c.minute))
    return nearby[:1]


def context_text(item: ContextItem, people: set[str]) -> str | None:
    """A context item as a whole English sentence (#219), the person in the event first; None if it has none."""
    if item.kind == "former_club":                # "E. Quinvika played for Northgate Rovers before"
        return f"{item.text}."
    if item.kind == "news":                       # "E. Lisais: Harbour City fans plan a hostile welcome ..."
        story = item.text.split(": ", 1)[-1].rstrip(".")
        return f"In the news before the match: {story}." if story else None
    if item.kind == "relationship" and item.relation in RELATIONS_EN and len(item.subject_names) == 2:
        a, b = item.subject_names
        if item.subject_ids[1] in people and item.subject_ids[0] not in people:
            a, b = b, a
        return RELATIONS_EN[item.relation].format(a=a, b=b)
    return None


def _context_sentence(trigger: MatchEvent, context: Sequence[ContextItem],
                      evidence: list[str]) -> ExplanationSentence | None:
    """Cite the best context item about someone in the trigger event, if it reads cleanly."""
    people = involved_in(trigger)
    about = [i for i in context if i.kind in CONTEXT_KINDS and people & set(i.subject_ids)]
    for item in sorted(about, key=lambda i: CONTEXT_KINDS.index(i.kind)):
        text = context_text(item, people)
        if text and not re.search(r"\d", text) and len(text.split()) <= 30:
            return ExplanationSentence(text=text, evidence_ids=evidence, context_ids=[item.context_id])
    return None


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def clean_headline(text: str, lang: str = "en") -> str:
    """No digits, and cut to the language's headline limit."""
    text = re.sub(r"\d", "", text).strip()
    limit = MAX_HEADLINE[lang]
    if lang == "zh":                              # Latin words (team names) count as one each
        while length(text, lang) > limit:
            text = text[:-1].rstrip()
        return text or PHRASES["zh"]["fallback_h"]
    return " ".join(text.split()[:limit]) or PHRASES[lang]["fallback_h"]


def template_explain(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str] | None = None,
    prefs: ViewerPrefs | None = None,
    chain_id: str | None = None,
    verifier_attempts: int = 0,
    context: Sequence[ContextItem] = (),
) -> Narrative:
    prefs = prefs or ViewerPrefs()
    lang = prefs.language
    names = {"home": "Home", "away": "Away", **(team_names or {})}
    side = prefs.focus_team or candidate.direction
    team = names[side]
    gaining = side == candidate.direction
    try:
        phrases = PHRASES[lang]
        found = _evidence(candidate, events)
        ids = [e.event_id for e in found][:4] or [NO_EVIDENCE]
        headline, first = _trigger(found[0], names[found[0].team], lang) if found else ("", "")
        sentences = []
        if first:
            sentences.append(ExplanationSentence(text=first, evidence_ids=ids[:1]))
        note = _context_sentence(found[0], context, ids[:1]) if found and lang == "en" else None
        if note:
            sentences.append(note)
        stat = _stat_sentence(candidate, side, team, stats, ids[:4], fan=prefs.audience == "fan",
                              lang=lang, found=found[:1]) if found else None
        if stat:
            sentences.append(stat)
        momentum = "momentum" if gaining else "momentum_lost"
        sentences.append(ExplanationSentence(text=phrases[momentum].format(team=team), evidence_ids=ids[:4]))
        fallback_headline = phrases[f"{momentum}_h"].format(team=team)
        # A viewer who picked a team reads the headline from their side ("Northgate Rovers lose their
        # grip"), not the event's ("A card changes the game").
        if prefs.focus_team:
            headline = fallback_headline
        return Narrative(prefs=prefs, headline=clean_headline(headline or fallback_headline, lang),
                         sentences=sentences[:3], source="template", verifier_attempts=verifier_attempts,
                         chain_id=chain_id)
    except Exception:
        phrases = PHRASES.get(lang, PHRASES["en"])
        try:
            ids = [e.event_id for e in _evidence(candidate, events)][:1]
        except Exception:
            ids = []
        return Narrative(
            prefs=prefs, headline=phrases["fallback_h"],
            sentences=[ExplanationSentence(text=phrases["fallback"], evidence_ids=ids or [NO_EVIDENCE])],
            source="template", verifier_attempts=verifier_attempts, chain_id=chain_id,
        )
