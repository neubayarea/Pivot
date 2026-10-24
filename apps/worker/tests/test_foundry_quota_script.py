import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts" / "foundry_quota_test.py"
spec = importlib.util.spec_from_file_location("foundry_quota_test", SCRIPT)
quota = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quota                # dataclasses look the module up while it loads
spec.loader.exec_module(quota)


def test_summary_passes_only_when_every_request_is_ok():
    ok = [quota.Result("std", "ok", ms) for ms in (100, 200, 300)] + [quota.Result("mini", "ok", 50)]
    report, passed = quota.summarise(ok)
    assert passed and "std: 3/3 ok, 0 throttled (429)" in report and "p50 200 ms" in report

    report, passed = quota.summarise(ok + [quota.Result("mini", "throttled", 10, "429 Too Many Requests")])
    assert not passed and "mini: 1/2 ok, 1 throttled (429)" in report and "429 Too Many Requests" in report
