"""TEMPORARY (Bx7 #190, do not merge): find the first step where the simulator differs between machines.

  python scratch_trace.py ref OUTDIR               # Windows: per-second fingerprints -> scratch_ref.json
  python scratch_trace.py mac OUTDIR               # CI: maths check, first differing second vs the ref, trace to it
  python scratch_trace.py trace SEED UNTIL OUTDIR  # a call trace of SEED up to second UNTIL (to diff with CI's)
"""
from __future__ import annotations

import inspect
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

from pivot_core.sim import build_demo_match
from pivot_core.sim import engine as E
from pivot_core.sim import movement as M

SEEDS = list(range(1, 21))
if "--v3" in sys.argv:                      # run with scratch_fix's V3 replacements already swapped in
    sys.argv.remove("--v3")
    sys.path.insert(0, str(Path(__file__).parent))
    import scratch_fix
    scratch_fix.install(3)
    SEEDS = [4, 6, 17]
    REF = "scratch_ref_v3.json"
else:
    REF = "scratch_ref.json"


def canon(x, depth=0) -> bytes:
    if isinstance(x, np.ndarray):
        return str(x.dtype).encode() + str(x.shape).encode() + np.ascontiguousarray(x).tobytes()
    if isinstance(x, (float, np.floating)):
        return b"f" + struct.pack("<d", float(x))
    if isinstance(x, (bool, int, str, type(None), np.integer, np.bool_)):
        return repr(x).encode()
    if isinstance(x, (list, tuple)):
        return b"[" + b",".join(canon(v, depth) for v in x) + b"]"
    if isinstance(x, (set, frozenset)):
        return b"{" + b",".join(sorted(canon(v, depth) for v in x)) + b"}"
    if isinstance(x, dict):
        return b"{" + b",".join(canon(k, depth) + b":" + canon(v, depth) for k, v in x.items()) + b"}"
    if depth < 1 and hasattr(x, "__dict__"):
        return type(x).__name__.encode() + canon({k: v for k, v in vars(x).items() if not k.startswith("_")}, depth + 1)
    return type(x).__name__.encode()


def crc(x) -> int:
    return zlib.crc32(canon(x))


def state_crc(obj) -> int:
    return crc([v for v in vars(obj).values() if isinstance(v, np.ndarray)])


def frame_crcs(eng: E.Engine) -> list[int]:
    f = eng.frames
    return [crc([f["ball"][s], f["pos"][s], f["speed"][s], f["fit"][s]]) for s in range(len(f["pos"]))]


def match_of(seed: int):
    return build_demo_match(seed)


def per_second(seed: int) -> dict:
    match = match_of(seed)
    eng = E.Engine(match, seed)
    start = crc([match.model_dump_json(), state_crc(eng)])
    eng.play()
    return {"start": start, "frames": frame_crcs(eng)}


def maths(out: Path) -> None:
    rng = np.random.default_rng(123)
    n = 100_000
    a, b = rng.uniform(-110, 110, n), rng.uniform(-70, 70, n)
    e = rng.uniform(-30, 5, n)
    pos = rng.uniform(1e-3, 200, n)
    small = rng.uniform(-1, 1, n)
    res = {
        "np.hypot": np.hypot(a, b), "np.exp": np.exp(e), "np.log": np.log(pos), "np.sin": np.sin(a),
        "np.cos": np.cos(a), "np.arctan2": np.arctan2(a, b), "np.tanh": np.tanh(small * 5), "np.sqrt": np.sqrt(pos),
        "np.power": np.power(pos, small), "np.arccos": np.arccos(small), "np.expm1": np.expm1(small),
        "math.hypot": np.array([math.hypot(x, y) for x, y in zip(a, b)]),
        "math.exp": np.array([math.exp(x) for x in e]), "math.log": np.array([math.log(x) for x in pos]),
        "math.atan2": np.array([math.atan2(x, y) for x, y in zip(a, b)]),
        "math.sin": np.array([math.sin(x) for x in a]), "math.cos": np.array([math.cos(x) for x in a]),
        "math.tanh": np.array([math.tanh(x * 5) for x in small]), "math.sqrt": np.array([math.sqrt(x) for x in pos]),
        "pow**": np.array([x ** y for x, y in zip(pos.tolist(), small.tolist())]),
        "np.hypot scalar": np.array([np.hypot(np.float64(x), np.float64(y)) for x, y in zip(a[:5000], b[:5000])]),
        "np.exp scalar": np.array([np.exp(np.float64(x)) for x in e[:5000]]),
        "np.hypot 2x11": np.concatenate([np.hypot(*(rng.uniform(0, 105, (11, 2)) - rng.uniform(0, 105, 2)).T)
                                         for _ in range(5000)]),
        "rng.standard_normal": np.random.default_rng(7).standard_normal(n),
        "rng.random": np.random.default_rng(7).random(n),
        "rng.normal": np.random.default_rng(7).normal(0, [1.8, 1.5], (n // 2, 2)).ravel(),
        "rng.beta": np.random.default_rng(7).beta(2, 5, n),
        "rng.gamma": np.random.default_rng(7).gamma(2.0, 1.0, n),
        "rng.poisson": np.random.default_rng(7).poisson(3.0, n).astype(float),
    }
    np.savez(out / "maths.npz", **res)
    for k, v in res.items():
        print(f"maths {k:22} {zlib.crc32(v.tobytes()):08x}")


class Tracer:
    def __init__(self, path: Path, until: int):
        self.f = path.open("w", encoding="utf-8")
        self.depth = 0
        self.n = 0
        self.until = until
        self.eng = None

    def wrap(self, owner, name, fn, static=False):
        tr = self

        def wrapper(*args, **kwargs):
            body = args if static or not args else args[1:]
            st = state_crc(args[0]) if (not static and args and hasattr(args[0], "__dict__")) else 0
            tr.depth += 1
            try:
                result = fn(*args, **kwargs)
            finally:
                tr.depth -= 1
            st_after = state_crc(args[0]) if (not static and args and hasattr(args[0], "__dict__")) else 0
            t = tr.eng.t if tr.eng is not None and hasattr(tr.eng, "t") else -1
            tr.n += 1
            tr.f.write(f"{tr.n} t={t} {'.' * tr.depth}{owner}.{name} in={crc([body, kwargs]):08x} "
                       f"self={st:08x}->{st_after:08x} out={crc(result):08x}\n")
            return result
        return staticmethod(wrapper) if static else wrapper

    def install(self):
        for cls in (E.Engine, M.MovementModel, M.TeamShape):
            for name, attr in list(vars(cls).items()):
                if isinstance(attr, staticmethod):
                    setattr(cls, name, self.wrap(cls.__name__, name, attr.__func__, static=True))
                elif inspect.isfunction(attr) and name not in ("__init__", "__repr__", "__eq__"):
                    setattr(cls, name, self.wrap(cls.__name__, name, attr))
        for mod in (E, M):
            for name, attr in list(vars(mod).items()):
                if inspect.isfunction(attr) and attr.__module__ == mod.__name__:
                    setattr(mod, name, self.wrap(mod.__name__.rsplit(".", 1)[1], name, attr, static=True))


def trace(seed: int, until: int, out: Path) -> None:
    tr = Tracer(out / f"trace-{seed}.txt", until)
    tr.install()
    match = match_of(seed)
    eng = E.Engine.__new__(E.Engine)
    tr.eng = eng
    E.Engine.__init__(eng, match, seed)
    eng.play(until)
    tr.f.write(f"END t={eng.t} frames={frame_crcs(eng)[-3:]}\n")
    tr.f.close()
    print(f"trace seed {seed} to {until}: {tr.n} calls -> {out / f'trace-{seed}.txt'}")


def main() -> None:
    mode = sys.argv[1]
    out = Path(sys.argv[-1])
    out.mkdir(parents=True, exist_ok=True)
    if mode == "ref":
        ref = {s: per_second(s) for s in SEEDS}
        Path(REF).write_text(json.dumps(ref))
        print("wrote", REF)
    elif mode == "mac":
        if REF == "scratch_ref.json":
            maths(out)
        ref = json.loads(Path(REF).read_text())
        first = []
        for s in SEEDS:
            got = per_second(s)
            want = ref[str(s)]
            if got["start"] != want["start"]:
                print(f"seed {s}: differs BEFORE kick-off (match build / engine setup)")
                first.append((-1, s))
                continue
            diff = next((i for i, (a, b) in enumerate(zip(got["frames"], want["frames"])) if a != b), None)
            if diff is None and len(got["frames"]) == len(want["frames"]):
                print(f"seed {s}: identical")
            else:
                print(f"seed {s}: first differing second {diff} of {len(want['frames'])}")
                first.append((diff if diff is not None else len(want["frames"]), s))
        (out / "first.json").write_text(json.dumps(first))
        if first:
            sec, s = min(first)
            print(f"EARLIEST: seed {s} second {sec}")
            trace(s, max(sec, 0) + 2, out)
    elif mode == "trace":
        trace(int(sys.argv[2]), int(sys.argv[3]), out)


if __name__ == "__main__":
    main()
