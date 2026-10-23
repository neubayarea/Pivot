#!/usr/bin/env python3
"""Sync Pivot's schedule into the Plane project "Pivot", organised as four phases.

Each phase is a Plane cycle holding: its milestone (the gate), the whole-team tasks, and one
"this phase's goal" item per line listing that line's GitHub tasks. Dev task status stays on GitHub.

  python3 scripts/plane_sync.py            # preview
  python3 scripts/plane_sync.py --apply    # create or update items in Plane

Reads the API key from ~/.config/pivot/plane.env (PLANE_API_KEY=...). Items are matched by their
ID prefix (M0, T01, P1-B, ...), so re-running updates instead of duplicating.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from github_setup import MILESTONES, REPO  # noqa: E402

BASE = "https://plane.in-stacks.com/api/v1/workspaces/pivot"
PROJECT = "Pivot"
UA = "pivot-plane-sync/0.1"  # Plane sits behind Cloudflare, which rejects the default Python user agent.
LABELS = {"里程碑": "#B60205", "全员事项": "#5319E7", "阶段目标": "#1D76DB"}
LINES = {"A": "A 后台与上云", "B": "B 模拟比赛与数据", "C": "C 网页界面", "D": "D AI 内容与质量"}
OLD_CYCLES = ["Hackathon 10/23–10/27"]

# Plane does not allow overlapping cycles, so phases are whole days; exact times are in the text.
PHASES = [
    {"key": "P0", "name": "阶段 0 · 打地基", "start": "2026-10-23", "end": "2026-10-23", "milestones": ["M0"],
     "when": "10/23 下午 → 10/23 20:00",
     "start_if": "开工会开完，四条线都有人认领。",
     "goal": "定好大家共用的数据格式，手写一份演示比赛数据，搭好代码骨架和自动检查，开通 AI 模型。",
     "unlocks": "四个人可以同时开工，谁也不用等谁。"},
    {"key": "P1", "name": "阶段 1 · 找到并讲清转折点", "start": "2026-10-24", "end": "2026-10-24", "milestones": ["M1"],
     "when": "10/23 20:00 → 10/24 22:00",
     "start_if": "阶段 0 完成：数据格式已冻结，演示数据已交给做网页的同学。",
     "goal": "在一台电脑上跑通：模拟比赛 → 势头计报警 → AI 判定、写稿、核对 → 看板上出现转折点。",
     "unlocks": "核心功能成立，可以开始做「假如」和上云。"},
    {"key": "P2", "name": "阶段 2 · 「假如」与上云", "start": "2026-10-25", "end": "2026-10-25", "milestones": ["M2", "M3"],
     "when": "10/24 22:00 → 10/25 23:00",
     "start_if": "阶段 1 完成：本地能自动出现一个已核对的转折点。",
     "goal": "做出「假如」重踢 1000 次和结果对比；把整套系统搬到微软云上，用公网网址能访问。"
             "10/25 18:00 时如果「假如」还没跑通，就从演示里拿掉。",
     "unlocks": "完整的演示可以在公网上走通，可以开始录视频。"},
    {"key": "P3", "name": "阶段 3 · 打磨与提交", "start": "2026-10-26", "end": "2026-10-27", "milestones": ["M4", "M5"],
     "when": "10/25 23:00 → 10/26 20:00（10/27 只做缓冲）",
     "start_if": "阶段 2 完成：公网上能把演示从头到尾走一遍。",
     "goal": "处理出错和降级的情况，美化界面，写 Pitch 和说明文档，录 2 分钟视频，提交。10/26 14:00 之后不再加功能。",
     "unlocks": "作品提交。"},
]
PHASE_OF_MILESTONE = {m: p["key"] for p in PHASES for m in p["milestones"]}


def api_key() -> str:
    for line in (Path.home() / ".config" / "pivot" / "plane.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("PLANE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("PLANE_API_KEY not found in ~/.config/pivot/plane.env")


class Plane:
    def __init__(self, key: str):
        self.key = key

    def call(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            path if path.startswith("http") else BASE + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-API-Key": self.key, "Accept": "application/json", "Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}")

    def list(self, path: str) -> list[dict]:
        d = self.call("GET", path)
        return d.get("results", d) if isinstance(d, dict) else d


def github_issues() -> dict[str, tuple[int, str]]:
    out = subprocess.run(["gh", "issue", "list", "-R", REPO, "--state", "all", "--limit", "200", "--json", "title,number,url"],
                         capture_output=True, text=True)
    return {} if out.returncode else {i["title"].split(" · ")[0]: (i["number"], i["url"]) for i in json.loads(out.stdout)}


def li_task(t: dict, gh: dict) -> str:
    num, url = gh.get(t["id"], (None, None))
    ref = f' <a href="{url}">#{num}</a>' if url else ""
    deps = f"（要先等 {html.escape('、'.join(t['depends'].split()))}）" if t["depends"] else ""
    return f"<li>{t['id']} {html.escape(t['title_zh'])}{ref}{deps}</li>"


def schedule_items() -> list[dict]:
    gh = github_issues()
    tasks = list(csv.DictReader((ROOT / "docs" / "plan" / "tasks.csv").open(encoding="utf-8")))
    ms_url = f"https://github.com/{REPO}/milestones"
    phase = {p["key"]: p for p in PHASES}
    items = []
    for key, (title, due, desc) in MILESTONES.items():
        day, clock, what = desc.split(" ", 2)
        p = phase[PHASE_OF_MILESTONE[key]]
        items.append({"id": key, "phase": p["key"], "name": f"{key} {what}（{day} {clock}）", "date": due,
                      "label": "里程碑", "priority": "high",
                      "desc": f"<p><b>{html.escape(p['name'])} 的关口。</b>{html.escape(p['goal'])}</p>"
                              f"<p>过了这个关口：{html.escape(p['unlocks'])}</p>"
                              f"<p>GitHub 里程碑：<a href=\"{ms_url}\">{html.escape(title)}</a></p>"})
    for t in tasks:
        if t["priority"] != "Team":
            continue
        num, url = gh.get(t["id"], (None, None))
        items.append({"id": t["id"], "phase": PHASE_OF_MILESTONE[t["milestone"]], "name": f"{t['id']} {t['title_zh']}",
                      "date": MILESTONES[t["milestone"]][1], "label": "全员事项", "priority": "medium",
                      "desc": f"<p>{html.escape(t.get('plain', ''))}</p><p>做完的样子：{html.escape(t['acceptance'])}</p>"
                              + (f"<p>GitHub：<a href=\"{url}\">#{num}</a></p>" if url else "")})
    for p in PHASES:
        for line, line_name in LINES.items():
            mine = [t for t in tasks if t["priority"] == "Must" and t["owner"] == line
                    and PHASE_OF_MILESTONE.get(t["milestone"]) == p["key"]]
            if not mine:
                continue
            hours = sum(float(t["estimate_h"]) for t in mine)
            items.append({"id": f"{p['key']}-{line}", "phase": p["key"],
                          "name": f"{p['key']}-{line} {line_name}：本阶段 {len(mine)} 个任务",
                          "date": MILESTONES[p["milestones"][-1]][1], "label": "阶段目标", "priority": "medium",
                          "desc": f"<p>{html.escape(p['name'])}里 {html.escape(line_name)} 要做的事，约 {hours:g} 小时。"
                                  f"进度看 GitHub，这里只列清单。</p><ul>{''.join(li_task(t, gh) for t in mine)}</ul>"})
        if p["key"] == "P3":
            pool = [t for t in tasks if t["priority"] in ("Should", "Could")]
            items.append({"id": "P3-POOL", "phase": "P3", "name": "P3-POOL 有余力再做：公共池",
                          "date": MILESTONES["M4"][1], "label": "阶段目标", "priority": "low",
                          "desc": "<p>谁先做完自己的必做任务，就按顺序从上往下拉。10/26 14:00 之后不再拉。</p>"
                                  f"<ul>{''.join(li_task(t, gh) for t in pool)}</ul>"})
    return items


def cycle_desc(p: dict) -> str:
    return (f"时间：{p['when']}\n开始条件：{p['start_if']}\n本阶段目标：{p['goal']}\n完成后解锁：{p['unlocks']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    p = Plane(api_key())

    proj = next(x for x in p.list("/projects/") if x["name"] == PROJECT)
    pid = proj["id"]
    states = {s["name"]: s["id"] for s in p.list(f"/projects/{pid}/states/")}
    labels = {l["name"]: l["id"] for l in p.list(f"/projects/{pid}/labels/")}
    existing = {i["name"].split(" ", 1)[0]: i for i in p.list(f"/projects/{pid}/issues/")}
    cycles = {c["name"]: c for c in p.list(f"/projects/{pid}/cycles/")}
    print(f"[{'APPLY' if args.apply else 'DRY RUN'}] project {PROJECT}, {len(existing)} items, cycles {list(cycles)}")

    for name in OLD_CYCLES:
        if name in cycles:
            print(f"  delete old cycle {name}")
            if args.apply:
                p.call("DELETE", f"/projects/{pid}/cycles/{cycles[name]['id']}/")

    for name, color in LABELS.items():
        if name not in labels:
            print(f"  create label {name}")
            if args.apply:
                labels[name] = p.call("POST", f"/projects/{pid}/labels/", {"name": name, "color": color})["id"]

    me = p.call("GET", "https://plane.in-stacks.com/api/v1/users/me/")["id"] if args.apply else None
    cycle_ids = {}
    for ph in PHASES:
        body = {"name": ph["name"], "description": cycle_desc(ph), "start_date": ph["start"], "end_date": ph["end"]}
        if ph["name"] in cycles:
            print(f"  update cycle {ph['name']}")
            cycle_ids[ph["key"]] = cycles[ph["name"]]["id"]
            if args.apply:
                p.call("PATCH", f"/projects/{pid}/cycles/{cycle_ids[ph['key']]}/", body)
        else:
            print(f"  create cycle {ph['name']} ({ph['start']} → {ph['end']})")
            if args.apply:
                cycle_ids[ph["key"]] = p.call("POST", f"/projects/{pid}/cycles/", {**body, "project_id": pid, "owned_by": me})["id"]

    per_cycle: dict[str, list[str]] = {ph["key"]: [] for ph in PHASES}
    for it in schedule_items():
        body = {"name": it["name"], "description_html": it["desc"], "target_date": it["date"],
                "priority": it["priority"], "labels": [labels[it["label"]]] if it["label"] in labels else []}
        if it["id"] in existing:
            print(f"  update {it['name']}")
            if args.apply:
                p.call("PATCH", f"/projects/{pid}/issues/{existing[it['id']]['id']}/", body)
            per_cycle[it["phase"]].append(existing[it["id"]]["id"])
        else:
            print(f"  create {it['name']}")
            if args.apply:
                per_cycle[it["phase"]].append(p.call("POST", f"/projects/{pid}/issues/", {**body, "state": states.get("Todo")})["id"])

    if args.apply:
        for key, ids in per_cycle.items():
            if ids and key in cycle_ids:
                p.call("POST", f"/projects/{pid}/cycles/{cycle_ids[key]}/cycle-issues/", {"issues": ids})
                print(f"  cycle {key}: {len(ids)} items")
    print("done" if args.apply else "dry run only; re-run with --apply")


if __name__ == "__main__":
    main()
