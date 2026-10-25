"""B14 (first half): the pre-match context turned into ContextEffects (CTX-001, CTX-002, QA-012)."""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

from pivot_core.domain import Match, OffFieldEvent, PreMatchCondition, Relationship
from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.effects import MAX_EFFECT, MAX_TOTAL, can_combine, context_effects, with_effects
from pivot_core.sim.season import load_season, with_season

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"
# Sources that come from the match itself rather than one news item, career stint or relationship.
WHOLE_MATCH = {"competition": "competition", "stakes": "stakes", "crowd": "attendance", "weather": "weather"}


@pytest.fixture(scope="module")
def demo():
    return with_season(DEMO_1021.build(), load_season(FIXTURES))


def by_id(effects):
    return {e.effect_id: e for e in effects}


def assert_qa_012(match: Match, effects) -> None:
    ctx = match.context
    people = {p.player_id: p for t in (match.home, match.away) for p in t.squad}
    subjects = set(people) | {match.home.coach.coach_id, match.away.coach.coach_id, "home", "away"}
    refs = ({n.news_id for n in ctx.news} | {r.relationship_id for r in ctx.relationships}
            | {s.stint_id for p in people.values() for s in p.career})
    assert len(by_id(effects)) == len(effects)                      # ids are unique
    for e in effects:
        assert e.subject_id in subjects
        assert abs(e.delta) <= MAX_EFFECT and e.delta != 0
        if e.source_ref is not None:
            assert e.source_ref in refs, e.effect_id
        else:
            assert e.source in WHOLE_MATCH or e.source in ("form", "fatigue"), e.effect_id
            if e.source in ("form", "fatigue"):
                assert e.subject_id in {c.player_id for c in ctx.conditions}
    side = {p.player_id: p.team for p in people.values()}
    total = defaultdict(float)
    for e in effects:
        if e.subject_id in ("home", "away"):
            for pid, s in side.items():
                if s == e.subject_id:
                    total[pid, e.target] += e.delta
        else:
            total[e.subject_id, e.target] += e.delta
    assert all(abs(v) <= MAX_TOTAL + 1e-9 for v in total.values())


def test_qa_012_demo_effects_point_to_their_sources_and_stay_small(demo):
    assert_qa_012(demo, context_effects(demo))


def test_b14_demo_turning_points_get_their_effects(demo):
    fx = by_id(context_effects(demo))
    # 38' red card: a04 is away at the club left on bad terms: 0.03 + 0.02 bad terms + 0.01 away
    a04 = fx["fx-a04-former_club-motivation-a04-c1"]
    assert a04.delta == 0.06 and a04.source_ref == "a04-c1" and "Harbour City" in a04.note
    # 85' substitute h13 faces Rovers, left on good terms, at home: the base 0.03
    assert fx["fx-h13-former_club-motivation-h13-c2"].delta == 0.03
    # 38,000 in Harbour Park, which holds 42,000: home motivation 0.04 x 0.905
    assert fx["fx-home-crowd-motivation"].delta == 0.036
    # title race (CTX-005 stakes) lifts both sides
    assert fx["fx-home-stakes-motivation"].delta == fx["fx-away-stakes-motivation"].delta == 0.03
    # the home coach's "under pressure" headline costs concentration
    coach = [e for e in fx.values() if e.source_ref == "news-h-coach-form"]
    assert [(e.target, e.delta) for e in coach] == [("concentration", -0.025)]


def test_b14_story_effects_come_first_and_read_without_numbers(demo):
    fx = context_effects(demo)
    assert fx[0].source == "former_club"
    a04 = next(e for e in fx if e.subject_id == "a04")              # what D13's template cites at 38'
    assert a04.source == "former_club" and not any(ch.isdigit() for ch in a04.note)


def test_b14_effects_are_a_pure_function_of_the_match(demo):
    before = demo.model_dump()
    assert context_effects(demo) == context_effects(demo)
    assert demo.model_dump() == before
    filled = with_effects(demo)
    assert filled.context.effects == context_effects(demo)
    assert filled.model_copy(update={"context": demo.context}) == demo


def test_b14_fixture_carries_the_effects(demo):
    saved = Match.model_validate(json.loads((FIXTURES / "demo-1021.json").read_text(encoding="utf-8"))["match"])
    assert saved.context.effects and saved.context.effects == context_effects(saved)


def crowded(demo, **context) -> Match:
    return demo.model_copy(update={"context": demo.context.model_copy(update=context)})


def test_ctx_001_totals_are_capped_per_person_and_target(demo):
    news = [OffFieldEvent(news_id=f"n{k}", subject_id="h07", kind="contract_dispute", hours_before_kickoff=10,
                          severity=3, sentiment="negative", headline="contract row") for k in range(9)]
    m = crowded(demo, news=news)
    fx = context_effects(m)
    assert sum(e.delta for e in fx if e.subject_id == "h07" and e.target == "concentration") >= -MAX_TOTAL
    assert_qa_012(m, fx)


def test_ctx_001_team_wide_effects_count_towards_the_cap(demo):
    # two spells at the opponent, both as a cast-off who left on bad terms: 2 x 0.09, plus stakes and crowd
    a04 = next(p for p in demo.away.squad if p.player_id == "a04")
    spell = a04.career[0].model_copy(update={"departure": "released", "appearances": 5})
    career = [spell, spell.model_copy(update={"stint_id": "a04-c9", "from_year": 2015, "to_year": 2017}),
              *a04.career[1:]]
    squad = [p.model_copy(update={"career": career}) if p.player_id == "a04" else p for p in demo.away.squad]
    m = demo.model_copy(update={"away": demo.away.model_copy(update={"squad": squad})})
    fx = context_effects(m)
    own = sum(e.delta for e in fx if e.subject_id == "a04" and e.target == "motivation")
    shared = sum(e.delta for e in fx if e.subject_id == "away" and e.target == "motivation")
    assert own + shared <= MAX_TOTAL and own > 0.15
    assert_qa_012(m, fx)


def test_ctx_002_rivalry_chemistry_news_form_fatigue_and_weather(demo):
    rels = [Relationship(relationship_id="r-feud", person_id="h07", other_id="a09", kind="feud", sentiment=-0.8),
            Relationship(relationship_id="r-mates", person_id="h02", other_id="h03", kind="former_teammate",
                         shared_seasons=7, sentiment=0.4),
            Relationship(relationship_id="r-cross", person_id="h04", other_id="a05", kind="former_teammate",
                         shared_seasons=4, sentiment=0.3)]
    news = [OffFieldEvent(news_id="n-night", subject_id="a10", kind="nightlife", hours_before_kickoff=30, severity=2,
                          sentiment="negative", headline="seen at a nightclub"),
            OffFieldEvent(news_id="n-old", subject_id="a11", kind="nightlife", hours_before_kickoff=100, severity=3,
                          sentiment="negative", headline="old story")]
    conditions = [PreMatchCondition(player_id="h10", recent_ratings=[7.5, 7.9, 7.1, 7.7, 7.3]),
                  PreMatchCondition(player_id="h11", days_since_last_match=3)]
    m = crowded(demo, relationships=rels, news=news, conditions=conditions, weather="rain")
    fx = context_effects(m)
    assert_qa_012(m, fx)
    got = {(e.subject_id, e.source, e.target): e.delta for e in fx}
    assert got["h07", "rivalry", "aggression"] == got["a09", "rivalry", "card_risk"] == 0.05
    assert got["h02", "former_teammate", "chemistry"] == got["h03", "former_teammate", "chemistry"] == 0.05
    assert not any(e.source_ref == "r-cross" for e in fx)       # no CTX-002 rule for opponents who were team-mates
    pro = next(p for p in m.away.squad if p.player_id == "a10").personality.professionalism
    assert got["a10", "off_field", "stamina_decay"] == round(0.06 * (1 - pro / 100), 3)
    assert got["a10", "off_field", "concentration"] == -0.02
    assert not any(e.source_ref == "n-old" for e in fx)         # older than 72 hours
    assert got["h10", "form", "motivation"] == round((7.5 - 6.7) * 0.03, 3)
    assert got["h11", "fatigue", "injury_risk"] == 0.15
    assert got["home", "weather", "chemistry"] == got["away", "weather", "chemistry"] == -0.03


def test_ctx_006_chemistry_needs_positions_that_link_up_and_no_falling_out(demo):
    role = {p.player_id: p.role for p in demo.home.squad}
    gk, st = next(p for p, r in role.items() if r == "GK"), next(p for p, r in role.items() if r == "ST")
    lb, rw = next(p for p, r in role.items() if r == "LB"), next(p for p, r in role.items() if r == "RW")
    cb1, cb2 = [p for p, r in role.items() if r == "CB"][:2]
    rels = [Relationship(relationship_id=f"r-{a}-{b}", person_id=a, other_id=b, kind="former_teammate",
                         shared_seasons=3, sentiment=s)
            for a, b, s in ((gk, st, 0.3), (lb, rw, 0.3), (cb1, cb2, 0.3), (lb, cb1, 0.0))]
    fx = context_effects(crowded(demo, relationships=rels))
    chem = {e.source_ref for e in fx if e.source == "former_teammate"}
    assert chem == {f"r-{cb1}-{cb2}"}          # keeper and striker, opposite flanks, and a sour exit do not count


def test_ctx_006_crowd_counts_against_the_grounds_capacity(demo):
    away = context_effects(crowded(demo, venue="Northgate Lane", attendance=31000))   # Rovers' ground, full
    assert by_id(away)["fx-home-crowd-motivation"].delta == 0.04
    unknown = context_effects(crowded(demo, venue="Somewhere Else", attendance=25000))  # half of 50,000
    assert by_id(unknown)["fx-home-crowd-motivation"].delta == 0.02


def test_b14_demo_form_and_chemistry_come_from_the_season(demo):
    fx = context_effects(demo)
    form = [e for e in fx if e.source == "form"]
    assert form and all(e.target == "motivation" for e in form)
    rated = {c.player_id: c.recent_ratings for c in demo.context.conditions}
    for e in form:
        avg = sum(rated[e.subject_id]) / len(rated[e.subject_id])
        assert e.delta == round((avg - 6.7) * 0.03, 3)
    role = {p.player_id: p.role for t in (demo.home, demo.away) for p in t.squad}
    rels = {r.relationship_id: r for r in demo.context.relationships}
    for e in fx:
        if e.source == "former_teammate":
            r = rels[e.source_ref]
            assert r.sentiment > 0 and can_combine(role[r.person_id], role[r.other_id])


def test_ctx_002_neutral_ground_and_empty_stands_have_no_crowd_effect(demo):
    empty = context_effects(crowded(demo, attendance=0))
    neutral = demo.context.competition.model_copy(update={"neutral_venue": True})
    assert not any(e.source == "crowd" for e in empty)
    assert not any(e.source == "crowd" for e in context_effects(crowded(demo, competition=neutral)))


def test_b14_effects_do_not_change_how_the_match_is_played_yet(demo):
    # the second half of B14 applies them; until then a match with effects plays exactly the same
    plants = list(DEMO_1021.plants)
    a, b = simulate(with_effects(demo), plants=plants), simulate(demo, plants=plants)
    assert a.events == b.events and np.array_equal(a.frames_pos, b.frames_pos)
