#!/usr/bin/env python3
"""Open an extra task on the board and claim it, before doing work that has no issue yet.

Creates an issue titled "<line>x<n> · <title>" (e.g. "Bx3 · 给模拟器加日志"), assigns it to you,
adds it to the board and sets 负责线, 阶段 and Status. Dry run by default.

  python3 scripts/new_task.py --line B --phase 1 --title "给模拟器加日志" \
      --why "调试 B03 时看不到每一步发生了什么" --done "开 PIVOT_LOG=debug 能看到每秒的事件" --from B03
  python3 scripts/new_task.py ... --apply            # actually create it
  python3 scripts/new_task.py ... --apply --start    # create and move straight to In progress
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

REPO = "neubayarea/Pivot"
ORG, PROJECT_NUMBER = "neubayarea", 1
LINES = {"A": "A 后台与上云", "B": "B 模拟比赛与数据", "C": "C 网页界面", "D": "D AI 内容与质量"}
AREA = {"A": "area:platform", "B": "area:sim", "C": "area:web", "D": "area:ai"}
PHASES = ["阶段 0 · 打地基", "阶段 1 · 找到并讲清转折点", "阶段 2 · 「假如」与上云", "阶段 3 · 打磨与提交"]
EXTRA_LABEL = ("extra", "C5DEF5", "开发中发现的额外任务，不在原始清单里")


def gh(*args: str) -> str:
    res = subprocess.run(["gh", *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} … failed:\n{res.stderr.strip()}")
    return res.stdout


def graphql(query: str, **variables: str) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        args += ["-f", f"{k}={v}"]
    return json.loads(gh(*args))["data"]


def next_id(line: str) -> str:
    titles = json.loads(gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "500", "--json", "title"))
    used = [int(m.group(1)) for t in titles if (m := re.match(rf"{line}x(\d+) · ", t["title"]))]
    return f"{line}x{max(used, default=0) + 1}"


def board() -> tuple[str, dict[str, tuple[str, dict[str, str]]]]:
    # Field names are Chinese; read them over GraphQL because gh's project commands garble them.
    d = graphql("""query($org:String!){organization(login:$org){projectV2(number:%d){id
      fields(first:50){nodes{... on ProjectV2Field{id name} ... on ProjectV2SingleSelectField{id name options{id name}}}}}}}""" % PROJECT_NUMBER, org=ORG)
    p = d["organization"]["projectV2"]
    fields = {f["name"]: (f["id"], {o["name"]: o["id"] for o in f.get("options", [])}) for f in p["fields"]["nodes"] if f}
    return p["id"], fields


def body(a: argparse.Namespace, me: str) -> str:
    lines = ["### 这是在做什么", a.why, "", "### 做完是什么样", f"- [ ] {a.done}", "", "### 基本信息",
             f"- 谁来做：{LINES[a.line]}（@{me}）", f"- 阶段：{PHASES[a.phase]}"]
    if a.estimate:
        lines.append(f"- 大约要花：{a.estimate:g} 小时")
    if a.from_task:
        lines.append(f"- 从哪个任务里冒出来的：{a.from_task}")
    lines += ["", "> 这是开发中新增的额外任务，用 `scripts/new_task.py` 创建。"]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--line", required=True, choices=LINES, help="归到哪条线：A/B/C/D")
    ap.add_argument("--phase", required=True, type=int, choices=range(4), help="属于哪个阶段：0-3")
    ap.add_argument("--title", required=True, help="一句话中文标题")
    ap.add_argument("--why", required=True, help="这是在做什么、为什么要做（写给没有计算机背景的同学看）")
    ap.add_argument("--done", required=True, help="做完是什么样（能检查的结果）")
    ap.add_argument("--from", dest="from_task", default="", help="从哪个任务里冒出来的，例如 B03")
    ap.add_argument("--estimate", type=float, default=0, help="预估小时")
    ap.add_argument("--start", action="store_true", help="创建后直接放到 In progress")
    ap.add_argument("--apply", action="store_true", help="真的创建；不加只预览")
    a = ap.parse_args()

    me = gh("api", "user", "--jq", ".login").strip()
    title = f"{next_id(a.line)} · {a.title}"
    status = "In progress" if a.start else "Ready"
    print(f"[{'APPLY' if a.apply else 'DRY RUN'}] {title}\n  负责线={LINES[a.line]}  阶段={PHASES[a.phase]}  "
          f"Status={status}  指派=@{me}\n\n{body(a, me)}")
    if not a.apply:
        print("\n只是预览；确认无误后加 --apply")
        return

    name, color, desc = EXTRA_LABEL
    gh("label", "create", name, "-R", REPO, "--color", color, "--description", desc, "--force")
    url = gh("issue", "create", "-R", REPO, "--title", title, "--body", body(a, me), "--assignee", "@me",
             "--label", name, "--label", AREA[a.line]).strip()
    project_id, fields = board()
    item = json.loads(gh("project", "item-add", str(PROJECT_NUMBER), "--owner", ORG, "--url", url, "--format", "json"))["id"]
    for field, value in (("负责线", LINES[a.line]), ("阶段", PHASES[a.phase]), ("Status", status)):
        fid, options = fields[field]
        graphql("""mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,
          itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}""",
                p=project_id, i=item, f=fid, o=options[value])
    if a.estimate and "预估小时" in fields:
        gh("api", "graphql", "-F", f"n={a.estimate}", "-f", f"p={project_id}", "-f", f"i={item}", "-f", f"f={fields['预估小时'][0]}",
           "-f", "query=mutation($p:ID!,$i:ID!,$f:ID!,$n:Float!){updateProjectV2ItemFieldValue(input:{projectId:$p,"
                 "itemId:$i,fieldId:$f,value:{number:$n}}){projectV2Item{id}}}")
    print(f"\n已创建并认领：{url}")


if __name__ == "__main__":
    sys.exit(main())
