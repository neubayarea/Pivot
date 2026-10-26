"""Comparator: explains why the what-if group ended differently from the baseline (D07).

Outcome probabilities are not stat-vocabulary metrics, so a comparison carries no claims and
never writes them; the S3 chart shows the recomputed distribution. The Verifier instead checks that
each "more likely" style word matches the change of the outcome it describes, and that
significance words only appear about outcomes whose intervals do not overlap (`significant`
from the SimResult). The replays are a simulation, so the wording never goes past that.

Why the groups differ (Bx10): a result with `baseline_stats` / `counterfactual_stats` also gives
the usual final scores and each team's averages from the moment the replays start. A comparison
may write those numbers (`replay_numbers`), and the Verifier checks each against the result
(`replay_facts`): the right team, the right stat, as-played first in "from A to B", and "rose" or
"fell" only for a change bigger than noise (`stat_changes`, Dx3). The template names the usual
score in each group and the clearest change in shots or chance quality.

`compare` is the entry point once a scenario has finished: Comparator ⇄ Verifier, then the
template if no draft passes.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping

from pydantic import ValidationError

from pivot_core.domain import (
    ExplanationSentence,
    MatchEvent,
    Narrative,
    SimResult,
    StatRef,
    Verdict,
    VerifierIssue,
    ViewerPrefs,
    label_at,
    period_starts,
)

from .explainer import KEY_TYPES, ExplainerDraft, audience_brief, parse_draft
from .languages import COMPARISON, REASONS, has_cjk
from .models import ModelClient, ModelUnavailable
from .pipeline import Step, StepRecorder
from .prompts import Prompt, render
from .template import _label, clean_headline, possessive
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, OutcomeMention, ReplayFact, Replays, StatSource, verify
from .vocabulary import BANNED_TERMS, SIGNIFICANCE_WORDS

OUTCOMES = ("home_win", "draw", "away_win")
MAX_CHECKS = 3                                # first draft plus two rewrites, as for pivot cards
COMPARATOR_TIMEOUT = 8.0
MAX_CITABLE = 5

EXAMPLE = ExplainerDraft(
    headline="Keeping Moreau on protects the lead",
    sentences=[
        ExplanationSentence(text="With Moreau still on the left, a Harbour City win became more likely in the replays.",
                            evidence_ids=["m063-s02302"]),
        ExplanationSentence(text="Northvale Rovers no longer found the space behind the full-back that the change had opened.",
                            evidence_ids=["m063-s02302"]),
    ],
)


def outcome_names(team_names: Mapping[str, str], lang: str = "en") -> dict[str, tuple[str, ...]]:
    """Phrases that name each outcome in a sentence; English ones are accepted in every language."""
    home, away = team_names["home"], team_names["away"]
    names = {
        "home_win": [f"{home} win", f"{home} victory", "home win"],
        "away_win": [f"{away} win", f"{away} victory", "away win"],
        "draw": ["draw"],
        "home_advance": [f"{home} go through", f"{home} going through", f"{away} go out"],
    }
    if lang == "zh":
        for k, team, side in (("home_win", home, "主"), ("away_win", away, "客")):
            names[k] += [f"{team}获胜", f"{team}取胜", f"{team}赢球", f"{team}胜出", f"{side}队获胜", f"{side}胜"]
        names["draw"] += ["平局", "战平", "打平", "握手言和"]
        names["home_advance"] += [f"{home}晋级", f"{away}出局", f"{away}被淘汰"]
    elif lang == "es":
        for k, team, side in (("home_win", home, "local"), ("away_win", away, "visitante")):
            names[k] += [f"victoria de {team}", f"victoria del {team}", f"triunfo de {team}", f"gane {team}",
                         f"{team} gane", f"victoria {side}"]
        names["draw"] += ["empate"]
        names["home_advance"] += [f"{home} pase", f"{home} se clasifique", f"clasificación de {home}",
                                  f"{away} quede eliminado"]
    return {k: tuple(v) for k, v in names.items()}


def changes(result: SimResult) -> dict[str, float]:
    keys = OUTCOMES + (("home_advance",) if result.baseline.home_advance is not None else ())
    return {k: (getattr(result.counterfactual, k) or 0) - (getattr(result.baseline, k) or 0) for k in keys}


# The replays' per-team numbers a comparison may write (Bx10): decimals to write them with and the
# Verifier's tolerance beyond rounding. Shares are written as percentages.
REPLAY_STATS = {"goals": (1, 0.0), "shots": (1, 0.0), "shots_on_target": (1, 0.0), "xg": (2, 0.01),
                "possession_pct": (0, 0.5), "cards": (1, 0.0), "red_cards": (1, 0.0)}
GROUPS = (("baseline", "baseline_stats"), ("with_change", "counterfactual_stats"))
Z95 = 1.959963984540054


def _clear(m0: float, sd0: float, m1: float, sd1: float, n0: int, n1: int) -> bool:
    """The two groups' means differ by more than about two standard errors, so it is not noise (Dx3).

    The runs are paired, which would make the error smaller still; leaving that out only errs on
    the side of calling a change small.
    """
    return _size(m0, sd0, m1, sd1, n0, n1) > Z95


def _size(m0: float, sd0: float, m1: float, sd1: float, n0: int, n1: int) -> float:
    """The gap between the means in standard errors (infinite when neither group varies)."""
    gap, se = abs(m1 - m0), math.sqrt(sd0 * sd0 / n0 + sd1 * sd1 / n1)
    if se == 0:
        return math.inf if gap > 1e-9 else 0.0
    return gap / se


def stat_changes(result: SimResult) -> list[dict]:
    """Each team's replay numbers as played and with the change, clearest change first; [] for an old result."""
    b, c = result.baseline_stats, result.counterfactual_stats
    if b is None or c is None:
        return []
    out = []
    for side in ("home", "away"):
        tb, tc = getattr(b, side), getattr(c, side)
        for metric, (dp, _) in REPLAY_STATS.items():
            sb, sc = getattr(tb, metric), getattr(tc, metric)
            out.append({"team": side, "stat": metric, "baseline": round(sb.mean, dp), "with_change": round(sc.mean, dp),
                        "clear": _clear(sb.mean, sb.sd, sc.mean, sc.sd, b.n_runs, c.n_runs),
                        "_raw": (sb.mean, sc.mean), "_size": _size(sb.mean, sb.sd, sc.mean, sc.sd, b.n_runs, c.n_runs)})
        pb, pc = tb.scored_share, tc.scored_share
        sdb, sdc = math.sqrt(pb * (1 - pb)), math.sqrt(pc * (1 - pc))
        out.append({"team": side, "stat": "scored_pct", "baseline": round(100 * pb), "with_change": round(100 * pc),
                    "clear": _clear(pb, sdb, pc, sdc, b.n_runs, c.n_runs),
                    "_raw": (100 * pb, 100 * pc), "_size": _size(pb, sdb, pc, sdc, b.n_runs, c.n_runs)})
    out.sort(key=lambda d: (not d["clear"], -d["_size"]))
    return out


def replay_numbers(result: SimResult) -> dict | None:
    """What the Comparator is shown of the replays, rounded as it may write them; None for an old result."""
    if result.baseline_stats is None or result.counterfactual_stats is None:
        return None
    out = {}
    for group, field in GROUPS:
        a = getattr(result, field)
        out[group] = {"top_scores": [{"score": f"{s.home}-{s.away}", "share_pct": round(100 * s.share)} for s in a.top_scores],
                      **{side: {**{m: round(getattr(getattr(a, side), m).mean, dp) for m, (dp, _) in REPLAY_STATS.items()},
                                "scored_pct": round(100 * getattr(a, side).scored_share)} for side in ("home", "away")}}
    return out


def replay_facts(result: SimResult) -> Replays | None:
    """For the Verifier: every replay number a comparison may write, with its change and whether it is clear."""
    if result.baseline_stats is None or result.counterfactual_stats is None:
        return None
    changes_ = {(d["team"], d["stat"]): d for d in stat_changes(result)}
    facts, scores = [], set()
    for group, field in GROUPS:
        a = getattr(result, field)
        for s in a.top_scores:
            scores.add((s.home, s.away))
            facts.append(ReplayFact("score_share", None, group, 100 * s.share, 0.5, None, False))
        for side in ("home", "away"):
            t = getattr(a, side)
            for metric, (_, tol) in [*REPLAY_STATS.items(), ("scored_pct", (0, 0.5))]:
                value = 100 * t.scored_share if metric == "scored_pct" else getattr(t, metric).mean
                d = changes_[(side, metric)]
                facts.append(ReplayFact(metric, side, group, value, tol, d["_raw"], d["clear"]))
    return Replays(tuple(facts), frozenset(scores))


def _spans(text: str, phrase: str):
    """Where a phrase occurs in lower-cased text; Chinese has no word boundaries."""
    pattern = re.escape(phrase.lower()) if has_cjk(phrase) else rf"\b{re.escape(phrase.lower())}\b"
    return re.finditer(pattern, text)


# A team named before "more likely to win" names its win: "Harbour City were more likely to win",
# "Harbour City更有可能获胜". The team's name is where the outcome is.
_LIKELY_TO_WIN = {
    "en": r"(?=[^.;:,]{0,30}?\b(?:more likely|less likely|likelier) to win\b)",
    "zh": r"(?=[^。；，,]{0,6}?(?:更有可能|可能性更大|可能性更小|更不可能)(?:获胜|取胜|赢球|胜出))",
}


def outcome_mentions(result: SimResult, team_names: Mapping[str, str], lang: str = "en"):
    """For the Verifier: every outcome a sentence names, where, and how it changed."""
    deltas, names = changes(result), outcome_names(team_names, lang)
    likely = [p for p in (_LIKELY_TO_WIN["en"], _LIKELY_TO_WIN.get(lang)) if p]
    teams = [(f"{side}_win", team_names[side]) for side in ("home", "away")]

    def mentioned(text: str) -> list[OutcomeMention]:
        lowered, found = text.lower(), {}

        def add(k: str, m: re.Match) -> None:
            found.setdefault(m.start(), OutcomeMention(text[m.start():m.end()], m.start(), m.end(), deltas[k],
                                                       bool(result.significant.get(k))))
        for k, phrases in names.items():
            if k not in deltas:
                continue
            for p in phrases:
                for m in _spans(lowered, p):
                    add(k, m)
        for k, team in teams:
            for pattern in likely:
                for m in re.finditer(rf"(?<![a-z0-9]){re.escape(team.lower())}(?![a-z0-9]){pattern}", lowered):
                    add(k, m)
        return sorted(found.values(), key=lambda m: m.start)

    return mentioned


def citable_events(target_event_id: str | None, at_minute: int, events: Mapping[str, MatchEvent]) -> list[str]:
    """Evidence a comparison may cite: the event the scenario changed, wherever it is.

    A tactical change (change_press) has no such event, so the events nearest the minute it
    starts from are offered instead, key events first.
    """
    if target_event_id:
        return [target_event_id]
    lo, hi = at_minute - EVIDENCE_BEFORE, at_minute + EVIDENCE_AFTER
    near = [e for e in events.values() if lo <= e.minute <= hi]

    def rank(e: MatchEvent) -> tuple:
        return (abs(e.minute - at_minute), KEY_TYPES.index(e.type) if e.type in KEY_TYPES else len(KEY_TYPES), e.seq)

    return [e.event_id for e in sorted(near, key=rank)[:MAX_CITABLE]]


def system_prompt(result: SimResult, prefs: ViewerPrefs, team_names: Mapping[str, str]) -> Prompt:
    if any(result.significant.values()):
        rule = (f"You may use {', '.join(SIGNIFICANCE_WORDS)} only about these outcomes, whose intervals do not "
                f"overlap: {', '.join(k for k, v in result.significant.items() if v)}.")
    else:
        rule = (f"No interval separates the groups: say the difference is within noise, and never use "
                f"{', '.join(SIGNIFICANCE_WORDS)}.")
    if replay_numbers(result) is None:
        numbers = ("**Write no numbers at all.** The chart next to your text already shows every percentage "
                   "and interval, recomputed.")
    else:
        numbers = ("Say **why** the groups differ, with numbers from `replay_numbers` only, written as given: a final "
                   "score from `top_scores` (\"2-1\") and its `share_pct`, or one team's average from the moment the "
                   "replays start. Name the team and the stat before each number. Write \"from A to B\" with the "
                   "as-played (baseline) value first. Say a number rose or fell only when `stat_changes` marks it "
                   "`clear`; otherwise say it hardly changed. Never write the win, draw or loss percentages: the chart "
                   "shows them.")
    return render("comparator", audience=audience_brief(prefs, team_names),
                  schema=json.dumps(ExplainerDraft.model_json_schema()), significance_rule=rule,
                  numbers_rule=numbers, banned_terms=", ".join(BANNED_TERMS), example=EXAMPLE.model_dump_json(indent=1))


def build_messages(result: SimResult, *, scenario_label: str, target_event_id: str | None, at_minute: int,
                   team_names: Mapping[str, str], events: Mapping[str, MatchEvent] | None = None,
                   prefs: ViewerPrefs | None = None,
                   feedback: Verdict | None = None) -> tuple[Prompt, list[dict[str, str]]]:
    from_clock = label_at(period_starts((events or {}).values()), at_minute * 60)
    request = {
        "scenario": scenario_label, "changed_event_id": target_event_id, "from_clock": from_clock,
        "evidence_ids": citable_events(target_event_id, at_minute, events or {}),
        "teams": dict(team_names),
        "baseline": result.baseline.model_dump(), "with_change": result.counterfactual.model_dump(),
        "change": {k: round(v, 3) for k, v in changes(result).items()},
        "significant": result.significant,
    }
    if (numbers := replay_numbers(result)) is not None:
        request["replay_numbers"] = numbers
        request["stat_changes"] = [{k: v for k, v in d.items() if not k.startswith("_")} for d in stat_changes(result)]
    text = json.dumps(request, ensure_ascii=False)
    if feedback and not feedback.passed:
        text += "\n\nThe Verifier rejected your previous comparison:\n" + "\n".join(
            f"- {i.code}: {i.message}" for i in feedback.issues)
    prompt = system_prompt(result, prefs or ViewerPrefs(), team_names)
    return prompt, [{"role": "system", "content": prompt.text}, {"role": "user", "content": text}]


def verify_comparison(narrative: Narrative, result: SimResult, *, at_minute: int, events: Mapping[str, MatchEvent],
                      stats: StatSource, team_names: Mapping[str, str], target_event_id: str | None) -> Verdict:
    return verify(narrative, pivot_minute=at_minute, events=events, stats=stats, significant=result.significant,
                  outcomes=outcome_mentions(result, team_names, narrative.prefs.language),
                  allowed_evidence=citable_events(target_event_id, at_minute, events), team_names=team_names,
                  replays=replay_facts(result))


def _phrase(outcome: str, team_names: Mapping[str, str], lang: str = "en", key: str = "win") -> str:
    phrases = COMPARISON[lang]
    if outcome == "draw":
        return phrases[key.replace("win", "draw")]
    return phrases[key].format(team=team_names[outcome.split("_")[0]])


def template_comparison(result: SimResult, *, evidence_id: str, team_names: Mapping[str, str],
                        prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                        verifier_attempts: int = 0) -> Narrative:
    """Fallback that names a change only when its intervals do not overlap, and says it is a replay."""
    prefs = prefs or ViewerPrefs()
    lang = prefs.language
    phrases = COMPARISON[lang]
    deltas = changes(result)
    clear = [o for o in OUTCOMES if result.significant.get(o) and abs(deltas[o]) > 1e-9]
    if clear:
        k = max(clear, key=lambda o: abs(deltas[o]))
        word = phrases["more" if deltas[k] > 0 else "less"]
        first = phrases["first"].format(outcome=_phrase(k, team_names, lang), word=word)
        headline = phrases["first_h"].format(outcome=_phrase(k, team_names, lang, "win_h"), word=word)
        second = phrases["apart"]
    else:
        first, headline, second = phrases["none"], phrases["none_h"], phrases["noise"]
    texts = [first] + (reasons(result, team_names, lang, prefs.audience == "fan") or [second])
    return Narrative(prefs=prefs, headline=clean_headline(headline, lang),
                     sentences=[ExplanationSentence(text=t, evidence_ids=[evidence_id]) for t in texts[:3]],
                     source="template", verifier_attempts=verifier_attempts, chain_id=chain_id)


TEMPLATE_STATS = ("shots", "xg")              # labelled in every language; fans get shots only (xG is jargon)


def reasons(result: SimResult, team_names: Mapping[str, str], lang: str = "en", fan: bool = False) -> list[str]:
    """Why the groups differ, for the template (Bx10): the usual final score in each group, and the
    clearest change in one team's shots or chance quality, if any is clear. [] for an old result."""
    b, c = result.baseline_stats, result.counterfactual_stats
    if b is None or c is None or not b.top_scores or not c.top_scores:
        return []
    phrases = REASONS[lang]
    was, now = (f"{s.home}-{s.away}" for s in (b.top_scores[0], c.top_scores[0]))
    out = [phrases["scores_same"].format(a=was) if was == now else phrases["scores"].format(a=was, b=now)]
    picks = [d for d in stat_changes(result) if d["clear"] and d["stat"] in TEMPLATE_STATS[:1 if fan else 2]]
    if picks:
        d = picks[0]
        team, label, dp = team_names[d["team"]], _label(d["stat"], lang, fan), REPLAY_STATS[d["stat"]][0]
        verb = "rose" if d["_raw"][1] > d["_raw"][0] else "fell"
        if f"{verb}_pl" in phrases and label.startswith(("los ", "las ")):     # plural subject, plural verb
            verb += "_pl"
        out.append(phrases["stat_fan" if fan else "stat"].format(
            team=team, owner=possessive(team), label=label, verb=phrases[verb],
            a=f"{d['baseline']:.{dp}f}", b=f"{d['with_change']:.{dp}f}"))
    return out


class _NoClaims:
    """Comparisons carry no claims, so nothing is ever recomputed."""

    def compute(self, ref: StatRef) -> float:
        raise LookupError("comparisons carry no claims")


async def _skip(step: Step) -> None:
    return None


async def compare(result: SimResult, *, scenario_label: str, target_event_id: str | None, at_minute: int,
                  events: Mapping[str, MatchEvent], team_names: Mapping[str, str], models: ModelClient,
                  record: StepRecorder | None = None, prefs: ViewerPrefs | None = None,
                  chain_id: str | None = None) -> Narrative:
    """Comparator ⇄ Verifier for a finished scenario, falling back to the template. Never raises.

    The result goes in `SimResult.narrative`. `record` gets one Step per agent call, like the
    Detect chain, so the caller can store them as AgentTraces.
    """
    record, prefs = record or _skip, prefs or ViewerPrefs()
    feedback, checks = None, 0
    while checks < MAX_CHECKS:
        prompt, messages = build_messages(result, scenario_label=scenario_label, target_event_id=target_event_id,
                                          at_minute=at_minute, team_names=team_names, events=events, prefs=prefs,
                                          feedback=feedback)
        try:
            reply = await models.complete_json("standard", messages, timeout=COMPARATOR_TIMEOUT)
        except ModelUnavailable as e:
            await record(Step("comparator", f"unavailable: {e}"[:200], "error", prompt_hash=prompt.hash))
            break
        checks += 1
        try:
            draft = parse_draft(reply.text, prefs=prefs, chain_id=chain_id, verifier_attempts=checks)
        except ValidationError as e:
            draft = None
            verdict = Verdict(passed=False, issues=[VerifierIssue(
                code="schema_invalid", message=f"{e.error_count()} schema errors: {e.errors()[0]['msg']}")])
        else:
            verdict = verify_comparison(draft, result, at_minute=at_minute, events=events, stats=_NoClaims(),
                                        team_names=team_names, target_event_id=target_event_id)
        await record(Step("comparator", draft.headline if draft else "invalid output",
                          "retried" if checks > 1 else "ok", reply.model, prompt.hash, reply.tokens))
        await record(Step("verifier", "pass" if verdict.passed else "; ".join(i.code for i in verdict.issues),
                          "ok" if verdict.passed else "rejected", verdict=verdict))
        if verdict.passed:
            return draft
        feedback = verdict
    evidence = (citable_events(target_event_id, at_minute, events) or list(events) or ["none"])[0]
    narrative = template_comparison(result, evidence_id=evidence, team_names=team_names, prefs=prefs,
                                    chain_id=chain_id, verifier_attempts=checks)
    await record(Step("template", narrative.headline, "degraded"))
    return narrative
