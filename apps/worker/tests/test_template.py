from pivot_core.domain import PivotCandidate, ViewerPrefs
from pivot_worker.template import format_value, template_explain
from pivot_worker.testing import FakeStats
from pivot_worker.verifier import NO_EVIDENCE, verify


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
    assert format_value(8.26, "ratio") == "8.3"


def test_template_never_invents_evidence_ids(events, stats):
    quiet = {"m063-s00100": events["m063-s00100"]}             # minute 20, far from the pivot
    for evs in (quiet, events):
        narrative = template_explain(candidate(key=()), events=evs, stats=stats)
        cited = {e for sent in narrative.sentences for e in sent.evidence_ids}
        assert cited <= set(evs) | {NO_EVIDENCE}, cited


def test_template_passes_with_digits_in_a_team_name(events, stats):
    names = {"home": "FC 1899", "away": "Harbour"}
    narrative = template_explain(candidate(), events=events, stats=stats, team_names=names)
    assert any("FC 1899" in sent.text for sent in narrative.sentences)
    verdict = verify(narrative, pivot_minute=63, events=events, stats=stats, team_names=names)
    assert verdict.passed, verdict.issues


def test_a_pivot_set_off_by_an_earlier_event_says_whose_minutes_the_numbers_are():
    """#396: S2026-27-TES-VAN pivot at 88' set off by the 82' substitution. "Made a substitution at 82'" then
    "in the next five minutes" read as 82'-87', but the numbers are measured after 88'."""
    from pivot_core.domain import Substitution
    from pivot_worker.testing import event

    sub = event("m082-s01700", 81, "substitution",
                substitution=Substitution(player_off_id="h10", player_on_id="h17", slot=10, reason="fatigue"))
    events = {sub.event_id: sub}
    stats = FakeStats({("shots", "home", (82, 87)): 1, ("shots", "home", (87, 92)): 4})
    for lang, window in (("en", "in the five minutes after the game turned"), ("zh", "比赛转折后五分钟"),
                         ("es", "En los cinco minutos tras el giro del partido")):
        narrative = template_explain(candidate(minute=87, key=(sub.event_id,)), events=events, stats=stats,
                                     team_names={"home": "Tessmouth"}, prefs=ViewerPrefs(language=lang))
        assert "82'" in narrative.sentences[0].text and window in narrative.sentences[1].text
        assert verify(narrative, pivot_minute=87, events=events, stats=stats,
                      team_names={"home": "Tessmouth", "away": "Away"}).passed
    same_minute = template_explain(candidate(minute=82, key=(sub.event_id,)), events=events,
                                   stats=FakeStats({("shots", "home", (77, 82)): 1, ("shots", "home", (82, 87)): 4}))
    assert "in the next five minutes" in same_minute.sentences[1].text
