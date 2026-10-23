#!/usr/bin/env python3
"""Create Pivot's GitHub labels, milestones and issues from docs/plan/tasks.csv.

Dry run by default: it only reads from GitHub and prints what it would create.

  python3 scripts/github_setup.py                       # preview
  python3 scripts/github_setup.py --apply               # create labels, milestones, issues
  python3 scripts/github_setup.py --asana-csv out.csv   # export schedule items for Asana

Needs the gh CLI logged in with access to the repo. Re-running is safe: labels are
updated in place, and milestones and issues whose titles already exist are skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "neubayarea/Pivot"
TASKS = ROOT / "docs" / "plan" / "tasks.csv"
OWNERS = ROOT / "docs" / "plan" / "owners.json"

# Due dates are set to noon UTC so the date reads the same in PT and ET; the time is in the description.
MILESTONES = {
    "M0": ("M0 Contracts frozen", "2026-10-23", "10/23 20:00 契约冻结"),
    "M1": ("M1 Local detect + explain", "2026-10-24", "10/24 22:00 本地发现与解释跑通"),
    "M2": ("M2 What-if go/no-go", "2026-10-25", "10/25 18:00 推演去留决策"),
    "M3": ("M3 Cloud end-to-end", "2026-10-25", "10/25 23:00 云端端到端"),
    "M4": ("M4 Feature freeze", "2026-10-26", "10/26 14:00 功能冻结"),
    "M5": ("M5 Submitted", "2026-10-26", "10/26 20:00 提交"),
}

LABELS = {
    "must": ("B60205", "本轮必须完成"),
    "should": ("D93F0B", "公共池：有余力时按顺序拉取"),
    "could": ("FBCA04", "可选"),
    "team": ("5319E7", "全员任务"),
    "area:platform": ("1D76DB", "A 平台与编排"),
    "area:sim": ("0E8A16", "B 模拟与分析"),
    "area:web": ("0075CA", "C 前端"),
    "area:ai": ("6F42C1", "D AI 内容与质量"),
    "blocked": ("000000", "被卡住，站会处理"),
    "contract": ("F9D0C4", "改动共享契约，需要全员知晓"),
    "demo-critical": ("E99695", "Demo 主线依赖"),
    "bug": ("D73A4A", "缺陷"),
}
AREA = {"A": "area:platform", "B": "area:sim", "C": "area:web", "D": "area:ai"}
ROLE = {"A": "A 后台与上云", "B": "B 模拟比赛与数据", "C": "C 网页界面", "D": "D AI 内容与质量", "ALL": "全员"}
DEMO_CRITICAL = {"B03", "B04", "B06", "C02", "C04", "C05", "D04", "D05", "D06", "B08", "A09", "D10"}


def gh(*args: str) -> str:
    res = subprocess.run(["gh", *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} … failed:\n{res.stderr.strip()}")
    return res.stdout


def load_tasks() -> list[dict]:
    with TASKS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def owners_of(task: dict) -> list[str]:
    return ["A", "B", "C", "D"] if task["owner"] == "ALL" else task["owner"].split("+")


def labels_for(task: dict) -> list[str]:
    prio = task["priority"].lower()
    labels = ["team"] if prio == "team" else [prio]
    labels += [AREA[o] for o in owners_of(task) if o in AREA and task["owner"] != "ALL"]
    if task["id"] in DEMO_CRITICAL:
        labels.append("demo-critical")
    return labels


def body_for(task: dict, assignees: list[str]) -> str:
    who = "、".join(ROLE.get(o, o) for o in ([task["owner"]] if task["owner"] == "ALL" else owners_of(task)))
    names = {t["id"]: t["title_zh"] for t in load_tasks()}
    deps = "；".join(f"{d} {names.get(d, '')}".strip() for d in task["depends"].split()) or "无，可以直接开始"
    milestone = MILESTONES[task["milestone"]][2] if task["milestone"] else "不设截止时间"
    lines = [
        "### 这是在做什么",
        task.get("plain") or task["title_zh"],
        "",
        "### 做完是什么样",
        f"- [ ] {task['acceptance'] or '由负责人补充'}",
        "",
        "### 基本信息",
        f"- 谁来做：{who}" + (f"（@{'、@'.join(assignees)}）" if assignees else "（待认领）"),
        f"- 截止：{milestone}",
        f"- 大约要花：{task['estimate_h']} 小时",
        f"- 要先等这些任务做完：{deps}",
        "",
        "<details><summary>给写代码的同学</summary>",
        "",
        f"- 技术名称：{task['title_en']}",
    ]
    if task["refs"]:
        lines.append(f"- 参考：{task['refs']}（见 docs/architecture.md 和 docs/adr/）")
    lines += ["- 完成定义：符合冻结的契约；确定性逻辑有单元测试；本地形态（PIVOT_PROFILE=local）跑通；"
              "PR 描述里写了 `Closes #本 issue`", "", "</details>"]
    return "\n".join(lines)


def issue_title(task: dict) -> str:
    return f"{task['id']} · {task['title_zh']}"


def export_asana(tasks: list[dict], out: Path) -> None:
    # Asana only gets schedule items: milestones and whole-team tasks. Dev tasks stay on GitHub.
    rows = [[title, "里程碑", "", due, desc] for title, due, desc in MILESTONES.values()]
    for t in tasks:
        if t["priority"] == "Team":
            due = MILESTONES[t["milestone"]][1] if t["milestone"] else ""
            rows.append([f"{t['id']} {t['title_zh']}", "全员事项", "", due, t["acceptance"]])
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name", "Section/Column", "Assignee", "Due Date", "Description"])
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually create things on GitHub")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--asana-csv", type=Path, help="write an Asana import CSV and exit")
    args = ap.parse_args()

    tasks = load_tasks()
    if args.asana_csv:
        export_asana(tasks, args.asana_csv)
        return

    owners = {k: v for k, v in json.loads(OWNERS.read_text(encoding="utf-8")).items() if k in "ABCD" and v}
    existing_ms = {m["title"]: m["number"] for m in json.loads(gh("api", f"repos/{args.repo}/milestones?state=all&per_page=100"))}
    existing_issues = json.loads(gh("issue", "list", "-R", args.repo, "--state", "all", "--limit", "500", "--json", "title,number"))
    by_id = {i["title"].split(" · ")[0]: i["number"] for i in existing_issues}
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] repo={args.repo} tasks={len(tasks)} existing milestones={len(existing_ms)} issues={len(existing_issues)}")

    for name, (color, desc) in LABELS.items():
        print(f"  label   {name}")
        if args.apply:
            gh("label", "create", name, "-R", args.repo, "--color", color, "--description", desc, "--force")

    for key, (title, due, desc) in MILESTONES.items():
        if title in existing_ms:
            print(f"  skip    milestone {title}")
            continue
        print(f"  create  milestone {title} (due {due})")
        if args.apply:
            gh("api", f"repos/{args.repo}/milestones", "-f", f"title={title}", "-f", f"due_on={due}T12:00:00Z", "-f", f"description={desc}")

    created = updated = 0
    for t in tasks:
        title = issue_title(t)
        assignees = [owners[o] for o in owners_of(t) if o in owners] if t["owner"] != "ALL" else []
        if t["id"] in by_id:
            # Already exists: refresh title and body so wording changes in tasks.csv reach GitHub.
            num = by_id[t["id"]]
            print(f"  update  #{num} {title}")
            if args.apply:
                gh("issue", "edit", str(num), "-R", args.repo, "--title", title, "--body", body_for(t, assignees))
                updated += 1
            continue
        cmd = ["issue", "create", "-R", args.repo, "--title", title, "--body", body_for(t, assignees)]
        for label in labels_for(t):
            cmd += ["--label", label]
        if t["milestone"]:
            cmd += ["--milestone", MILESTONES[t["milestone"]][0]]
        for a in assignees:
            cmd += ["--assignee", a]
        print(f"  create  {title}  [{', '.join(labels_for(t))}]" + (f" → {', '.join(assignees)}" if assignees else ""))
        if args.apply:
            gh(*cmd)
            created += 1
    print(f"done: {created} created, {updated} updated" if args.apply else "dry run only; re-run with --apply")
    if args.apply:
        print("看板：https://github.com/orgs/neubayarea/projects/1（新 issue 需要在看板设置里开启 Auto-add 才会自动加入）")


if __name__ == "__main__":
    sys.exit(main())
