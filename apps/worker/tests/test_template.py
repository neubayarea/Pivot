from pivot_core.domain import PivotCandidate
from pivot_worker.template import format_value, template_explain
from pivot_worker.testing import FakeStats
from pivot_worker.verifier import verify


def candidate(minute=63, key=("m063-s01042",), direction="home"):
    return PivotCandidate(match_id="M-test", minute=minute, direction=direction, cusum_stat=4.2, swing=0.3,
                          key_event_ids=list(key), window=(minute - 5, minute + 5))


def test_template_card_passes_the_verifier(events, stats):
    narrative = template_explain(candidate(), events=events, stats=stats, team_names={"home": "Rovers"})
    assert narrative.source == "template"
    assert narrative.headline == "Rovers change shifts the balance"
    assert len(narrative.sentences) == 3
    assert "threat created rose from 0.21 to 0.57" in narrative.sentences[1].text
    verdict = verify(narrative, pivot_minute=63, events=events, stats=stats)
    assert verdict.passed, verdict.issues


def test_template_without_key_events_or_stat_changes_still_passes(events):
    narrative = template_explain(candidate(key=()), events=events, stats=FakeStats({}))
    assert len(narrative.sentences) == 1
    assert verify(narrative, pivot_minute=63, events=events, stats=FakeStats({})).passed


def test_template_never_raises():
    class Broken:
        def compute(self, ref):
            raise RuntimeError("stat store down")

    narrative = template_explain(candidate(), events={}, stats=Broken())
    assert narrative.source == "template" and narrative.sentences

    narrative = template_explain(candidate(), events=None, stats=Broken())   # type: ignore[arg-type]
    assert narrative.headline == "Momentum swings"


def test_goal_trigger_names_the_scoring_side(events, stats):
    narrative = template_explain(candidate(minute=65, key=("m063-s01201",), direction="away"), events=events,
                                 stats=stats, team_names={"away": "Harbour"})
    assert narrative.headline == "Harbour goal swings the match"
    assert narrative.sentences[0].text.startswith("Harbour scored at 66'")


def test_format_value():
    assert format_value(68.44, "pct") == "68%"
    assert format_value(0.844, "xg") == "0.84 xG"
    assert format_value(11.23, "km") == "11.2 km"
    assert format_value(9, "count") == "9"
