#!/usr/bin/env python3
"""Where Premier League players stand at corners and free kicks, from StatsBomb open data (Ax44, #245).

  uv run scripts/setpiece_reference.py <statsbomb dir>            # print the numbers
  uv run scripts/setpiece_reference.py <statsbomb dir> --write    # and keep them in reference.json

<statsbomb dir> holds matches.json and events/<match_id>.json for one competition season (the
Premier League 2015/16 is competition 2, season 27 in github.com/statsbomb/open-data). The raw
files are never committed (docs/match-data.md).

StatsBomb has no tracking data for that season, but every shot carries a freeze frame: where
everybody the camera saw stood when the shot was struck. So:

- corners: every shot taken within CORNER_S seconds of a corner, by the corner team, in the same
  possession (most are the first contact from the delivery); the freeze frame is a second or two
  after the kick, when the box is still full;
- free-kick crosses: the same for a free kick played from the final third;
- direct free kicks: the shot is the kick, so its freeze frame is the setup itself: the wall, its
  distance from the ball, the keeper and the box.

The results go to eval/realism/reference.json under "set_pieces"; docs/set-pieces.md reads them.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "eval" / "realism" / "reference.json"
SX, SY = 105 / 120, 68 / 80                   # StatsBomb yards (120 x 80) to metres (105 x 68)
CORNER_S = 6.0                                # a shot this soon after the kick still counts as "from the corner"
POSTS = (30.34, 37.66)                        # goal posts, metres from the right touchline (7.32 m goal)
WALL_NEAR, WALL_FAR, WALL_DEG = 1.5, 12.0, 25.0   # the same wall test as the match page (setpieces.ts)
FK_BINS = ((0, 20), (20, 25), (25, 30), (30, 99))


def _m(loc: list[float]) -> tuple[float, float]:
    """StatsBomb location (attacking left to right) to metres from the goal line attacked and from y = 0."""
    return (120 - loc[0]) * SX, loc[1] * SY


def _in_box(d: float, y: float) -> bool:
    return d <= 16.5 and 13.84 <= y <= 54.16


def _in_six(d: float, y: float) -> bool:
    return d <= 5.5 and 24.84 <= y <= 43.16


def _at_post(d: float, y: float, post: float) -> bool:
    """On the line by that post: within 2 m of the line and 2.5 m of the post (inside or outside it)."""
    return d <= 2.0 and abs(y - post) <= 2.5


def _clock(e: dict) -> float:
    h, mi, s = e["timestamp"].split(":")
    return int(h) * 3600 + int(mi) * 60 + float(s)


def _stats(vals: list[float]) -> dict:
    a = np.asarray(vals, dtype=float)
    if not len(a):
        return {"n": 0}
    return {"mean": round(float(a.mean()), 2), "median": round(float(np.median(a)), 2),
            "p10": round(float(np.percentile(a, 10)), 2), "p90": round(float(np.percentile(a, 90)), 2), "n": int(len(a))}


def _share(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


def box_setup(shot: dict, near_post: float | None) -> dict:
    """Counts from one freeze frame around a delivery into the box (corner or free-kick cross)."""
    ff = shot["shot"]["freeze_frame"]
    sd, sy = _m(shot["location"])
    att = [_m(p["location"]) for p in ff if p["teammate"]] + [(sd, sy)]
    keeper = [_m(p["location"]) for p in ff if not p["teammate"] and p["position"]["name"] == "Goalkeeper"]
    dfn = [_m(p["location"]) for p in ff if not p["teammate"] and p["position"]["name"] != "Goalkeeper"]
    row = {
        "att_box": sum(_in_box(d, y) for d, y in att),
        "def_box": sum(_in_box(d, y) for d, y in dfn),
        "att_six": sum(_in_six(d, y) for d, y in att),
        "def_six": sum(_in_six(d, y) for d, y in dfn),
        "att_edge": sum(16.5 < d <= 25 and abs(y - 34) <= 16 for d, y in att),     # the "second ball" area
        "def_upfield": sum(d > 30 for d, y in dfn),                                 # left up for the counter
        "att_back": sum(d > 52.5 for d, y in att),                                  # in their own half
        "seen": len(ff) + 1,
    }
    if keeper:
        row["keeper_m"] = keeper[0][0]
    if near_post is not None:
        far_post = POSTS[1] if near_post == POSTS[0] else POSTS[0]
        row["near_post"] = any(_at_post(d, y, near_post) for d, y in dfn)
        row["far_post"] = any(_at_post(d, y, far_post) for d, y in dfn)
    return row


def wall_setup(shot: dict) -> dict:
    """The wall and the box at a direct free kick (the freeze frame is the moment of the kick)."""
    ff = shot["shot"]["freeze_frame"]
    bd, by = _m(shot["location"])
    gx, gy = -bd, 34.0 - by                      # ball to goal centre, in (towards goal, sideways) metres
    glen = math.hypot(gx, gy)
    wall, dists = 0, []
    for p in ff:
        if p["teammate"] or p["position"]["name"] == "Goalkeeper":
            continue
        d, y = _m(p["location"])
        vx, vy = d - bd, y - by
        dist = math.hypot(vx, vy)
        if not WALL_NEAR <= dist <= WALL_FAR:
            continue
        cos = (vx * gx + vy * gy) / (dist * glen)
        if math.degrees(math.acos(max(-1.0, min(1.0, cos)))) <= WALL_DEG:
            wall += 1
            dists.append(dist)
    keeper = [_m(p["location"]) for p in ff if not p["teammate"] and p["position"]["name"] == "Goalkeeper"]
    dfn = [_m(p["location"]) for p in ff if not p["teammate"] and p["position"]["name"] != "Goalkeeper"]
    att = [_m(p["location"]) for p in ff if p["teammate"]]
    # the wall proper: the line nearest the ball, everybody in the cone within a stride of the closest
    line = [x for x in dists if x <= min(dists) + 1.5] if dists else []
    row = {"dist": math.hypot(bd, by - 34), "wall": wall, "wall_line": len(line), "def_box": sum(_in_box(d, y) for d, y in dfn),
           "att_box": sum(_in_box(d, y) for d, y in att),
           "nearest_def_m": min((math.hypot(d - bd, y - by) for d, y in dfn), default=None)}
    if line:
        row["wall_m"] = float(np.mean(line))
    if keeper:
        row["keeper_m"] = keeper[0][0]
        row["keeper_side_m"] = keeper[0][1] - 34          # + towards the ball's side is worked out below
        row["keeper_side_m"] *= 1 if by > 34 else -1
    return row


def scan(sb_dir: Path) -> dict:
    corners, fk_cross, fk_direct = [], [], []
    matches = json.loads((sb_dir / "matches.json").read_text(encoding="utf-8"))
    for m in matches:
        ev = json.loads((sb_dir / "events" / f"{m['match_id']}.json").read_text(encoding="utf-8"))
        last_kick: dict[tuple[int, int], tuple[str, float, dict]] = {}   # (period, possession) -> kind, clock, pass
        for e in ev:
            if e["period"] > 2:
                continue
            kind = e["type"]["name"]
            if kind == "Pass" and e["pass"].get("type", {}).get("name") in ("Corner", "Free Kick"):
                last_kick[(e["period"], e["possession"])] = (e["pass"]["type"]["name"], _clock(e), e)
            if kind != "Shot" or "freeze_frame" not in e["shot"]:
                continue
            if e["shot"]["type"]["name"] == "Free Kick":
                fk_direct.append(wall_setup(e))
                continue
            k = last_kick.get((e["period"], e["possession"]))
            if not k or k[2]["team"]["id"] != e["team"]["id"] or _clock(e) - k[1] > CORNER_S:
                continue
            p = k[2]
            if k[0] == "Corner":
                near = POSTS[0] if p["location"][1] < 40 else POSTS[1]
                corners.append(box_setup(e, near))
            elif p["location"][0] >= 80:            # a free kick from the final third, played into the box
                fk_cross.append(box_setup(e, None))
    return {"matches": len(matches), "corners": corners, "fk_cross": fk_cross, "fk_direct": fk_direct}


def summarise(raw: dict) -> dict:
    def box(rows: list[dict]) -> dict:
        out = {key: _stats([r[key] for r in rows if key in r])
               for key in ("att_box", "def_box", "att_six", "def_six", "att_edge", "def_upfield", "att_back",
                           "keeper_m", "seen")}
        if rows and "near_post" in rows[0]:
            out["near_post_share"] = _share([r["near_post"] for r in rows])
            out["far_post_share"] = _share([r["far_post"] for r in rows])
            out["both_posts_share"] = _share([r["near_post"] and r["far_post"] for r in rows])
        full = [r for r in rows if r["seen"] >= 20]     # the camera saw (nearly) everybody
        out["att_back_full_frames"] = _stats([r["att_back"] for r in full])
        out["def_upfield_full_frames"] = _stats([r["def_upfield"] for r in full])
        return out

    fk = raw["fk_direct"]
    bins = {}
    for lo, hi in FK_BINS:
        rows = [r for r in fk if lo <= r["dist"] < hi]
        bins[f"{lo}-{hi}m" if hi < 99 else f"{lo}m+"] = {
            "wall": _stats([r["wall"] for r in rows]),
            "wall_line": _stats([r["wall_line"] for r in rows]),
            "wall_m": _stats([r["wall_m"] for r in rows if "wall_m" in r]),
            "def_box": _stats([r["def_box"] for r in rows]),
            "att_box": _stats([r["att_box"] for r in rows]),
            "keeper_m": _stats([r["keeper_m"] for r in rows if "keeper_m" in r]),
            "keeper_side_m": _stats([r["keeper_side_m"] for r in rows if "keeper_side_m" in r]),
        }
    return {
        "corners": box(raw["corners"]),
        "free_kick_crosses": box(raw["fk_cross"]),
        "direct_free_kicks": {"all": {"wall": _stats([r["wall"] for r in fk]),
                                      "wall_line": _stats([r["wall_line"] for r in fk]),
                                      "wall_m": _stats([r["wall_m"] for r in fk if "wall_m" in r]),
                                      "nearest_def_m": _stats([r["nearest_def_m"] for r in fk
                                                               if r["nearest_def_m"] is not None]),
                                      "dist": _stats([r["dist"] for r in fk])},
                              "by_distance": bins},
        "matches": raw["matches"],
        "source": ("StatsBomb open data, Premier League 2015/16, shot freeze frames (regular time): corners and "
                   f"free-kick crosses = shots within {CORNER_S:.0f} s of the kick in the same possession; direct "
                   "free kicks = the free-kick shot itself. Built by scripts/setpiece_reference.py."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("statsbomb_dir", type=Path)
    ap.add_argument("--write", action="store_true", help="keep the numbers in eval/realism/reference.json")
    args = ap.parse_args()
    out = summarise(scan(args.statsbomb_dir))
    print(json.dumps(out, indent=1))
    if args.write:
        ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
        ref["set_pieces_pl1516"] = out
        REFERENCE.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {REFERENCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
