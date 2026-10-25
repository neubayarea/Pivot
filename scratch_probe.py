import sys, numpy as np
sys.path.insert(0, "packages/pivot_core/tests")
from test_realism import _targets
roles, t = _targets("4-3-3", 55.0, False)
lw = next(t[i, 0] for i, r in roles.items() if r == "LW")
cms = [round(float(t[i, 0]), 4) for i, r in roles.items() if r == "CM"]
print("lw", round(float(lw), 4), "cms", cms, "gap", round(float(min(abs(lw - x) for x in cms)), 4), "sum", float(np.round(t.sum(), 6)))
