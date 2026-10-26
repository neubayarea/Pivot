"""B14 (second half): the engine plays by the context effects when the switch is on (CTX-001, QA-012).

The switch is off by default; with it off a match plays exactly as before, whatever the context holds.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

from pivot_core.domain import ContextEffect
from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.effects import MAX_EFFECT, MAX_TOTAL, with_effects
from pivot_core.sim.engine import Engine, Params
from pivot_core.sim.season import load_season, with_season

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"


@pytest.fixture(scope="module")
def demo():
    """The demo match with its season stories, as it stands before kick-off."""
    return with_season(DEMO_1021.build(), load_season(FIXTURES))


def with_extra(match, *effects: ContextEffect):
    return match.model_copy(update={"context": match.context.model_copy(update={"effects": list(effects)})})


def fx(effect_id: str, subject: str, target: str, delta: float, source: str = "off_field") -> ContextEffect:
    return ContextEffect(effect_id=effect_id, subject_id=subject, source=source, target=target, delta=delta,
                         note="test")


def test_b14_switch_is_off_by_default():
    assert Params().context_effects is False and DEMO_1021.context_effects is False


def test_b14_off_plays_exactly_as_before_even_with_effects_in_the_context(demo):
    plants = list(DEMO_1021.plants)
    plain = simulate(DEMO_1021.build(), plants=plants)
    loaded = simulate(with_effects(demo), plants=plants, context_effects=False)
    assert loaded.events == plain.events
    for a in ("frames_pos", "frames_ball", "frames_speed", "frames_fitness", "frames_possession"):
        assert np.array_equal(getattr(loaded, a), getattr(plain, a)), a


def test_qa_012_applied_effects_point_to_sources_and_stay_small(demo):
    eng = Engine(demo, context_effects=True)
    ctx = eng.match.context
    assert ctx.effects                                    # worked out before kick-off and kept with the match
    people = {p.player_id for t in (demo.home, demo.away) for p in t.squad}
    refs = ({n.news_id for n in ctx.news} | {r.relationship_id for r in ctx.relationships}
            | {s.stint_id for t in (demo.home, demo.away) for p in t.squad for s in p.career})
    for e in ctx.effects:
        assert abs(e.delta) <= MAX_EFFECT
        assert e.subject_id in people | {"home", "away", demo.home.coach.coach_id, demo.away.coach.coach_id}
        assert e.source_ref is None or e.source_ref in refs
    # what each player actually plays with: own effects plus the side's, at most 0.25 per target
    for pid, totals in eng.fx.items():
        assert all(abs(v) <= MAX_TOTAL + 1e-9 for v in totals.values()), pid
    for v in eng.chem.values():
        assert 0 < v <= 0.05


def test_ctx_001_team_wide_effects_reach_every_player_of_that_side(demo):
    eng = Engine(with_extra(demo, fx("e1", "home", "motivation", 0.04, "crowd")), context_effects=True)
    home = {p.player_id for p in demo.home.squad}
    assert all(eng._fx(pid, "motivation") == 0.04 for pid in home)
    assert all(eng._fx(p.player_id, "motivation") == 0.0 for p in demo.away.squad)


def test_ctx_001_effects_move_their_targets_the_right_way(demo):
    starters = [s.player_id for s in sorted(demo.home.sheet.starters, key=lambda s: s.slot)]
    a, b, c = starters[9], starters[5], starters[3]
    effects = [fx("e1", a, "card_risk", 0.10), fx("e2", a, "aggression", 0.05), fx("e3", a, "composure", -0.05),
               fx("e4", a, "injury_risk", 0.15, "fatigue"), fx("e5", b, "motivation", 0.08, "form"),
               fx("e6", b, "fitness", -0.10, "fatigue"), fx("e7", c, "stamina_decay", 0.09)]
    on = Engine(with_extra(demo, *effects), context_effects=True)
    off = Engine(with_extra(demo, *effects))
    for target, up in (("card_risk", True), ("aggression", True), ("injury_risk", True), ("composure", False)):
        assert (on._times(0.2, a, target) > 0.2) is up and off._times(0.2, a, target) == 0.2
    i_b, i_c = starters.index(b), starters.index(c)
    assert on._physique()[0][0, i_b] > off._physique()[0][0, i_b]          # motivation: runs faster
    assert on.fitness[0, i_b] == pytest.approx(0.9) and off.fitness[0, i_b] == 1.0
    assert on._slot_factor("stamina_decay")[0, i_c] == pytest.approx(1.09)  # legs go sooner


def test_ctx_001_chemistry_belongs_to_the_pair(demo):
    rel = next(r for r in demo.context.relationships
               if r.kind == "former_teammate" and r.sentiment > 0 and r.person_id[0] == r.other_id[0])
    eng = Engine(demo, context_effects=True)
    assert eng.chem[rel.person_id, rel.other_id] > 0 and eng.chem[rel.other_id, rel.person_id] > 0
    pairs = {frozenset((r.person_id, r.other_id)) for r in demo.context.relationships}
    assert all(frozenset(key) in pairs for key in eng.chem)          # only between the two who played together
    assert not any("chemistry" in totals for totals in eng.fx.values())   # no team-wide chemistry on a dry day


def test_b14_on_changes_the_match_and_records_the_effects(demo):
    plants = list(DEMO_1021.plants)
    off = simulate(demo, plants=plants)
    on = simulate(demo, plants=plants, context_effects=True)
    assert on.events != off.events
    assert on.match.context.effects and not off.match.context.effects
    totals = defaultdict(float)
    for e in on.match.context.effects:
        totals[e.subject_id, e.target] += e.delta
    assert totals["a04", "card_risk"] > 0                 # the 38' story: targeted by the home fans
