import json
import re

import pytest
from pydantic import ValidationError

from pivot_core.domain import STAT_UNITS, MatchEvent, PivotCandidate, Verdict, VerifierIssue, ViewerPrefs
from pivot_worker import explainer as ex
from pivot_worker.prompts import render
from pivot_worker.testing import FakeStats, event
from pivot_worker.verifier import verify

TEAMS = {"home": "Rovers", "away": "Harbour"}


def candidate(key=("m063-s01042",)):
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                          key_event_ids=list(key), window=(58, 68))


def test_system_prompt_fills_every_placeholder():
    prompt, messages = ex.build_messages(candidate(), events={}, stats=FakeStats({}), team_names=TEAMS)
    assert "{{" not in prompt.text
    assert all(f"`{m}`" in prompt.text for m in ("xg", "line_height_m", "distance_covered_km"))
    assert "odds" in prompt.text and "significantly" in prompt.text
    assert messages[0] == {"role": "system", "content": prompt.text}
    assert len(prompt.hash) == 12


def test_prompt_hash_changes_with_the_audience():
    analyst = ex.system_prompt(ViewerPrefs(), TEAMS)
    fan = ex.system_prompt(ViewerPrefs(audience="fan", focus_team="away"), TEAMS)
    assert analyst.hash != fan.hash
    assert "Harbour's point of view" in fan.text and "quality of chances" in fan.text


def test_render_rejects_missing_and_unknown_values():
    with pytest.raises(KeyError):
        render("explainer", audience="x")


def test_request_carries_window_events_and_a_stat_sheet(events, stats):
    _, messages = ex.build_messages(candidate(), events=events, stats=stats, team_names=TEAMS)
    request = json.loads(messages[1]["content"])
    ids = [e["id"] for e in request["events"]]
    assert "m063-s00100" not in ids                      # minute 20 is outside the window
    assert ids[0] == "m063-s01042" and len(ids) == 4
    assert len(request["stat_sheet"]) == len(STAT_UNITS) * 2 * 2      # every metric, both teams, both windows
    sheet = {(c["stat_ref"]["metric"], c["stat_ref"]["team"], tuple(c["stat_ref"]["window"])): c["value"]
             for c in request["stat_sheet"]}
    assert sheet[("threat_total", "home", (58, 63))] == 0.21


def test_pivot_clock_is_the_match_clock_not_elapsed_minutes(stats):
    # The second half kicked off 48 minutes in (three minutes of first-half stoppage), so the
    # pivot at elapsed minute 69 is 67' on the clock, the same clock the events are written in.
    kick = MatchEvent(match_id="M-test", seq=1, event_id="m063-s00001", t=2880, period=2, period_t=0,
                      type="kickoff", team="home")
    sub = MatchEvent(match_id="M-test", seq=2, event_id="m063-s00002", t=2880 + 1030, period=2, period_t=1030,
                     type="pass", team="home")
    c = PivotCandidate(match_id="M-test", minute=69, direction="home", cusum_stat=4.2, swing=0.3,
                       key_event_ids=[sub.event_id], window=(64, 74))
    _, messages = ex.build_messages(c, events={e.event_id: e for e in (kick, sub)}, stats=stats, team_names=TEAMS)
    request = json.loads(messages[1]["content"])
    assert request["pivot"]["clock"] == "67'"
    assert [e["clock"] for e in request["events"]] == ["63'"]


def test_window_events_are_capped_and_key_events_kept():
    many = {f"m063-s{i:05d}": event(f"m063-s{i:05d}", 60) for i in range(100)}
    chosen = ex.window_events(candidate(key=("m063-s00099",)), many)
    assert len(chosen) == ex.MAX_EVENTS
    assert "m063-s00099" in [e.event_id for e in chosen]


def test_feedback_is_appended_on_a_retry(events, stats):
    verdict = Verdict(passed=False, issues=[VerifierIssue(code="number_mismatch", message="xg is 0.84, not 0.9.")])
    _, messages = ex.build_messages(candidate(), events=events, stats=stats, team_names=TEAMS, feedback=verdict)
    assert messages[1]["content"].endswith("- number_mismatch: xg is 0.84, not 0.9.")


def test_a_rewrite_shows_the_rejected_card(events, stats):
    verdict = Verdict(passed=False, issues=[VerifierIssue(code="number_mismatch", message="xg is 0.84, not 0.9.")])
    previous = ex.EXAMPLES[0].model_dump_json()
    _, messages = ex.build_messages(candidate(), events=events, stats=stats, team_names=TEAMS, feedback=verdict,
                                    previous=previous)
    text = messages[1]["content"]
    assert f"Your previous card:\n{previous}" in text and text.index(previous) < text.index("The Verifier rejected")
    _, first = ex.build_messages(candidate(), events=events, stats=stats, team_names=TEAMS, previous=previous)
    assert previous not in first[1]["content"]                      # only on a rewrite


def test_parse_draft_builds_an_llm_narrative():
    raw = ex.EXAMPLES[0].model_dump_json()
    narrative = ex.parse_draft(raw, chain_id="c1", verifier_attempts=1)
    assert narrative.source == "llm" and narrative.chain_id == "c1" and narrative.verifier_attempts == 1


def test_parse_draft_rejects_bad_shapes():
    good = ex.EXAMPLES[0].model_dump()
    with pytest.raises(ValidationError):
        ex.parse_draft({**good, "sentences": good["sentences"] * 4})
    with pytest.raises(ValidationError):
        ex.parse_draft({**good, "sentences": [{"text": "No evidence.", "evidence_ids": []}]})
    with pytest.raises(ValidationError):
        ex.parse_draft('{"headline": "Not JSON enough"')


@pytest.mark.parametrize("draft", ex.EXAMPLES)
def test_few_shot_examples_follow_the_rules(draft):
    minute = int(re.search(r"m(\d{3})", draft.sentences[0].evidence_ids[0]).group(1))
    ids = {i for s in draft.sentences for i in s.evidence_ids}
    events = {i: event(i, minute) for i in ids}
    stats = FakeStats({(c.stat_ref.metric, c.stat_ref.team, c.stat_ref.window): c.value
                       for s in draft.sentences for c in s.claims})
    verdict = verify(ex.parse_draft(draft.model_dump()), pivot_minute=minute, events=events, stats=stats)
    assert verdict.passed, verdict.issues
