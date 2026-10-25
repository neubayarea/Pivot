"""TEMPORARY (Bx7 #190, do not merge): which replacements make a seed play the same on every machine?

Swaps functions in at runtime (no simulator code is edited) and prints one fingerprint per match:
  V0  as is
  V1  distances as sqrt(x*x + y*y): np.hypot, math.hypot, np.linalg.norm, np.vecdot
  V2  V1 + rng.uniform(a, b) -> a + (b - a) * rng.random(), rng.normal(m, s) -> m + s * rng.standard_normal()
  V3  V2 + exp, atan2, sin, cos, tanh worked out with the decimal module (same answer everywhere)

  uv run scripts/scratch_fix.py
"""
from __future__ import annotations

import json
import math
import sys
import types
import zlib

import numpy as np
from decimal import Decimal, localcontext

import pivot_core.sim as S
from pivot_core.sim import DEMO_1021, build_demo_match
from pivot_core.sim import effects, engine, movement, season, squads, whatif, world

MODULES = [engine, movement, squads, world, effects, season, whatif]
REAL_NP = np
REAL_MATH = math


class DetRng:
    def __init__(self, g):
        self.g = g

    def __getattr__(self, name):
        return getattr(self.g, name)

    def uniform(self, low=0.0, high=1.0, size=None):
        u = self.g.random(size)
        if size is None and not (np.ndim(low) or np.ndim(high)):
            return float(low) + (float(high) - float(low)) * u
        low, high = np.asarray(low, float), np.asarray(high, float)
        return low + (high - low) * u

    def normal(self, loc=0.0, scale=1.0, size=None):
        if size is None and (np.ndim(loc) or np.ndim(scale)):
            size = np.broadcast(np.asarray(loc), np.asarray(scale)).shape
        z = self.g.standard_normal(size)
        if size is None:
            return float(loc) + float(scale) * z
        return np.asarray(loc, float) + np.asarray(scale, float) * z


def _hypot_np(x, y, *a, **k):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return np.sqrt(x * x + y * y)


def _norm(v, *a, **k):
    v = np.asarray(v, float)
    return np.sqrt(np.sum(v * v))


def _vecdot(a, b, *x, **k):
    p = np.asarray(a, float) * np.asarray(b, float)
    out = p[..., 0].copy()
    for j in range(1, p.shape[-1]):
        out = out + p[..., j]
    return out


_PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494459")


def d_exp(x: float) -> float:
    with localcontext() as c:
        c.prec = 40
        return float(Decimal(x).exp())


def d_tanh(x: float) -> float:
    with localcontext() as c:
        c.prec = 40
        e = (2 * Decimal(x)).exp()
        return float((e - 1) / (e + 1))


def _sin_cos(x: float) -> tuple[float, float]:
    with localcontext() as c:
        c.prec = 40
        d = Decimal(x)
        d = d - 2 * _PI * (d / (2 * _PI)).to_integral_value()
        s, cs, term_s, term_c, n = Decimal(0), Decimal(0), d, Decimal(1), 0
        while True:
            s, cs = s + term_s, cs + term_c
            n += 2
            term_s = -term_s * d * d / (n * (n + 1))
            term_c = -term_c * d * d / ((n - 1) * n)
            if abs(term_s) < Decimal("1e-38") and abs(term_c) < Decimal("1e-38"):
                return float(s), float(cs)


def _atan(z: Decimal) -> Decimal:
    k = 0
    while abs(z) > Decimal("0.1"):
        z = z / (1 + (1 + z * z).sqrt())
        k += 1
    total, term, n = Decimal(0), z, 1
    while abs(term) > Decimal("1e-40"):
        total += term / n
        term = -term * z * z
        n += 2
    return total * (2 ** k)


def d_atan2(y: float, x: float) -> float:
    with localcontext() as c:
        c.prec = 40
        Y, X = Decimal(y), Decimal(x)
        if X == 0:
            return float(_PI / 2 if Y > 0 else -_PI / 2 if Y < 0 else 0)
        a = _atan(Y / X)
        if X < 0:
            a = a + _PI if Y >= 0 else a - _PI
        return float(a)


def _vec(fn):
    def f(x, *a, **k):
        if np.ndim(x) == 0:
            return np.float64(fn(float(x))) if isinstance(x, np.generic) else fn(float(x))
        arr = np.asarray(x, float)
        return np.array([fn(float(v)) for v in arr.ravel()]).reshape(arr.shape)
    return f


def proxies(variant: int):
    npx = types.ModuleType("np_det")
    npx.__dict__.update(REAL_NP.__dict__)
    mx = types.ModuleType("math_det")
    mx.__dict__.update(REAL_MATH.__dict__)
    if variant >= 1:
        npx.hypot = _hypot_np
        npx.linalg = types.SimpleNamespace(**{**REAL_NP.linalg.__dict__, "norm": _norm})
        npx.vecdot = _vecdot
        mx.hypot = lambda *xs: REAL_MATH.sqrt(sum(float(v) * float(v) for v in xs))
    if variant >= 2:
        rnd = types.SimpleNamespace(**REAL_NP.random.__dict__)
        rnd.default_rng = lambda *a, **k: DetRng(REAL_NP.random.default_rng(*a, **k))
        npx.random = rnd
    if variant >= 3:
        npx.exp, npx.tanh = _vec(d_exp), _vec(d_tanh)
        npx.sin, npx.cos = _vec(lambda v: _sin_cos(v)[0]), _vec(lambda v: _sin_cos(v)[1])
        mx.exp, mx.tanh, mx.atan2 = d_exp, d_tanh, d_atan2
        mx.sin, mx.cos = (lambda v: _sin_cos(v)[0]), (lambda v: _sin_cos(v)[1])
    return npx, mx


def install(variant: int) -> None:
    npx, mx = proxies(variant)
    for mod in MODULES:
        if hasattr(mod, "np"):
            mod.np = npx
        if hasattr(mod, "math"):
            mod.math = mx


def fingerprint(out) -> str:
    ev = zlib.crc32(json.dumps(out.events, sort_keys=True, default=str).encode())
    fr = zlib.crc32(b"".join(np.ascontiguousarray(a).tobytes() for a in (out.frames_ball, out.frames_pos)))
    s = out.match.score
    return f"{s.home}-{s.away} events={len(out.events)} ev:{ev:08x} frames:{fr:08x}"


def self_check() -> None:
    xs = np.linspace(-30, 5, 997)
    worst = {}
    for name, mine, ref, args in (("exp", d_exp, math.exp, [(x,) for x in xs]),
                                  ("tanh", d_tanh, math.tanh, [(x / 6,) for x in xs]),
                                  ("sin", lambda v: _sin_cos(v)[0], math.sin, [(x * 3,) for x in xs]),
                                  ("cos", lambda v: _sin_cos(v)[1], math.cos, [(x * 3,) for x in xs]),
                                  ("atan2", d_atan2, math.atan2, [(x, 7 - x / 3) for x in xs])):
        worst[name] = max(abs(mine(*a) - ref(*a)) / math.ulp(ref(*a)) for a in args)
    print("self-check, worst ulps vs math:", {k: round(v, 1) for k, v in worst.items()}, file=sys.stderr)


def count_calls() -> None:
    install(3)
    calls: dict[str, int] = {}
    for mod in (engine, movement):
        for owner in [o for o in (getattr(mod, "np", None), getattr(mod, "math", None)) if o] + [mod.np.linalg]:
            for name in ("hypot", "exp", "tanh", "atan2", "sin", "cos", "norm", "vecdot"):
                fn = owner.__dict__.get(name)
                if fn is None or getattr(fn, "_counted", False):
                    continue

                def wrapped(*a, _fn=fn, _key=f"{mod.__name__.rsplit('.', 1)[1]}.{getattr(owner, '__name__', 'linalg')}.{name}", **k):
                    calls[_key] = calls.get(_key, 0) + 1
                    return _fn(*a, **k)
                wrapped._counted = True
                setattr(owner, name, wrapped)
    out = engine.Engine(build_demo_match(1), 1).run()
    print(calls, fingerprint(out))


def main() -> None:
    if sys.argv[1:] == ["count"]:
        return count_calls()
    self_check()
    seeds = list(range(1, 21))
    for variant in (0, 1, 2, 3):
        install(variant)
        for seed in (seeds[:3] if variant == 0 else seeds):
            out = engine.Engine(build_demo_match(seed), seed).run()
            print(f"V{variant} seed {seed:3} {fingerprint(out)}", flush=True)
        if variant == 3:
            out = engine.Engine(DEMO_1021.build(DEMO_1021.seed), DEMO_1021.seed,
                                plants=list(DEMO_1021.plants)).run()
            print(f"V3 demo {DEMO_1021.seed} {fingerprint(out)}", flush=True)
    print("done", S.__name__, file=sys.stderr)


if __name__ == "__main__":
    main()
