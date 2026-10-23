#!/usr/bin/env python3
"""Fill docs/plan/handbook.template.html with the tasks in docs/plan/tasks.csv.

Usage: python3 scripts/build_handbook.py   → writes docs/site/handbook.html
"""
from __future__ import annotations

import csv
import html
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "plan"
CAPACITY_H = 33  # focused hours per person, 10/23 17:00 → 10/26 20:00
SCALE_H = 40     # bar width represents this many hours
MILESTONES = [
    ("M0", "M0 契约冻结", "10/23 20:00"),
    ("M1", "M1 本地发现与解释跑通", "10/24 22:00"),
    ("M2", "M2 推演去留", "10/25 18:00"),
    ("M3", "M3 云端端到端", "10/25 23:00"),
    ("M4", "M4 功能冻结", "10/26 14:00"),
    ("M5", "M5 提交", "10/26 20:00"),
]
LINE_NAME = {"A": "A 平台", "B": "B 模拟", "C": "C 前端", "D": "D AI 内容", "ALL": "全员"}


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def owner_chips(owner: str) -> str:
    if owner == "ALL":
        return '<span class="ln ln-T">全员</span>'
    return " ".join(f'<span class="ln ln-{o}">{o}</span>' for o in owner.split("+"))


def row_class(task: dict) -> str:
    return "row-T" if task["owner"] == "ALL" else f"row-{task['owner'][0]}"


def task_row(t: dict, with_prio: bool = False) -> str:
    prio = ""
    if with_prio:
        cls = "t-should" if t["priority"] == "Should" else "t-could"
        prio = f'<td><span class="tag {cls}">{t["priority"]}</span></td>'
    deps = "、".join(t["depends"].split()) or "—"
    return (f'<tr class="{row_class(t)}"><td class="id">{t["id"]}</td>'
            f'<td>{esc(t["title_zh"])}<br><span class="small muted">{esc(t["title_en"])}</span></td>'
            f'<td>{owner_chips(t["owner"])}</td>{prio}<td class="n">{t["estimate_h"]} h</td>'
            f'<td class="dep">{deps}</td><td>{esc(t["acceptance"]) or "—"}</td></tr>')


def main() -> None:
    tasks = list(csv.DictReader((PLAN / "tasks.csv").open(encoding="utf-8")))
    head = "<thead><tr><th>ID</th><th>任务</th><th>负责</th><th>预估</th><th>依赖</th><th>验收标准</th></tr></thead>"
    blocks = []
    for key, name, when in MILESTONES:
        rows = [t for t in tasks if t["milestone"] == key and t["priority"] in ("Must", "Team")]
        hours = sum(float(t["estimate_h"]) for t in rows)
        blocks.append(
            f'<div class="sub"><div class="ms-head"><h3>{name}</h3><span class="when">{when}</span>'
            f'<span class="small muted">{len(rows)} 个任务 · {hours:g} 小时</span></div>'
            f'<div class="scroll"><table>{head}<tbody>{"".join(task_row(t) for t in rows)}</tbody></table></div></div>')
    pool = [t for t in tasks if t["priority"] in ("Should", "Could")]
    pool_html = ('<div class="scroll"><table><thead><tr><th>ID</th><th>任务</th><th>负责</th><th>优先级</th><th>预估</th>'
                 f'<th>依赖</th><th>验收标准</th></tr></thead><tbody>{"".join(task_row(t, True) for t in pool)}</tbody></table></div>')

    load = defaultdict(float)
    for t in tasks:
        if t["priority"] in ("Must", "Team"):
            for o in (["A", "B", "C", "D"] if t["owner"] == "ALL" else t["owner"].split("+")):
                load[o] += float(t["estimate_h"])
    color = {"A": "var(--ln-a)", "B": "var(--ln-b)", "C": "var(--ln-c)", "D": "var(--ln-d)"}
    loads = "\n".join(
        f'      <div class="load"><b>{LINE_NAME[o]}</b><div class="bar">'
        f'<span style="width:{min(load[o] / SCALE_H, 1) * 100:.1f}%;background:{color[o]}"></span>'
        f'<i style="left:{CAPACITY_H / SCALE_H * 100:.1f}%"></i></div>'
        f'<span class="small">{load[o]:g} / {CAPACITY_H} h</span></div>'
        for o in "ABCD")

    page = (PLAN / "handbook.template.html").read_text(encoding="utf-8")
    page = page.replace("<!--TASK_TABLES-->", "\n".join(blocks)).replace("<!--POOL-->", pool_html).replace("<!--LOADS-->", loads)
    out = ROOT / "docs" / "site" / "handbook.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: {sum(1 for t in tasks if t['priority'] in ('Must', 'Team'))} must/team tasks, "
          f"{len(pool)} in pool, load {dict((k, load[k]) for k in 'ABCD')}")


if __name__ == "__main__":
    main()
