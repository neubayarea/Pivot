import pytest

from pivot_core.domain import AgentTrace, Envelope, MatchEvent, Pivot


@pytest.fixture
def make_event():
    def make(seq: int, match_id: str = "m1") -> MatchEvent:
        return MatchEvent(
            match_id=match_id, seq=seq, event_id=f"{match_id}-s{seq:05d}",
            t=seq, period=1, period_t=seq, type="pass", team="home",
        )
    return make


@pytest.fixture
def make_pivot():
    def make(minute: int, status: str = "pending", match_id: str = "m1") -> Pivot:
        return Pivot(
            pivot_id=f"{match_id}:p{minute}", match_id=match_id, minute=minute, direction="home",
            severity=2, status=status, trigger_event_ids=[], chain_id=f"c{minute}",
        )
    return make


@pytest.fixture
def make_trace():
    def make(chain_id: str, step: int, match_id: str = "m1") -> AgentTrace:
        return AgentTrace(
            trace_id=f"{chain_id}:{step}", chain_id=chain_id, step=step, match_id=match_id, agent="judge",
            input_ref="p1", output_summary="ok", latency_ms=10, status="ok",
        )
    return make


@pytest.fixture
def make_envelope():
    def make(seq: int, match_id: str = "m1", type: str = "match.status") -> Envelope:
        return Envelope(type=type, match_id=match_id, seq=seq, ts="2026-10-23T20:00:00Z", payload={"seq": seq})
    return make
