#!/usr/bin/env python3
"""Sync Pivot's schedule (milestones + whole-team tasks) into the Plane project "Pivot".

Dev tasks stay on GitHub; Plane only holds the schedule. Dry run by default.

  python3 scripts/plane_sync.py            # preview
  python3 scripts/plane_sync.py --apply    # create or update items in Plane

Reads the API key from ~/.config/pivot/plane.env (PLANE_API_KEY=...). Items are matched by
their ID prefix (M0, T01, ...), so re-running updates dates and descriptions instead of duplicating.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
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
CYCLE = ("Hackathon 10/23–10/27", "2026-10-23", "2026-10-27")
LABELS = {"里程碑": "#B60205", "全员事项": "#5319E7"}
# Plane sits behind Cloudflare, which rejects the default Python user agent.
UA = "pivot-plane-sync/0.1"


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
            (path if path.startswith("http") else BASE + path), method=method,
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


def github_issue_urls() -> dict[str, str]:
    out = subprocess.run(["gh", "issue", "list", "-R", REPO, "--state", "all", "--limit", "200", "--json", "title,url"],
                         capture_output=True, text=True)
    if out.returncode:
        return {}
    return {i["title"].split(" · ")[0]: i["url"] for i in json.loads(out.stdout)}


def schedule_items() -> list[dict]:
    gh_urls = github_issue_urls()
    ms_url = f"https://github.com/{REPO}/milestones"
    items = []
    for key, (title, due, desc) in MILESTONES.items():
        day, clock, what = desc.split(" ", 2)
        items.append({"id": key, "name": f"{key} {what}（{day} {clock}）",
                      "date": due, "label": "里程碑", "priority": "high",
                      "desc": f"<p>{html.escape(desc)}</p><p>GitHub 里程碑：<a href=\"{ms_url}\">{html.escape(title)}</a></p>"})
    tasks = csv.DictReader((ROOT / "docs" / "plan" / "tasks.csv").open(encoding="utf-8"))
    for t in tasks:
        if t["priority"] != "Team":
            continue
        link = gh_urls.get(t["id"])
        items.append({"id": t["id"], "name": f"{t['id']} {t['title_zh']}", "date": MILESTONES[t["milestone"]][1],
                      "label": "全员事项", "priority": "medium",
                      "desc": (f"<p>负责：{html.escape(t['owner'])} · 预估 {t['estimate_h']} 小时 · 里程碑 {t['milestone']}</p>"
                               f"<p>验收：{html.escape(t['acceptance'])}</p>"
                               + (f"<p>GitHub：<a href=\"{link}\">{link}</a></p>" if link else ""))})
    return items


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
    cycles = {c["name"]: c["id"] for c in p.list(f"/projects/{pid}/cycles/")}
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] project {PROJECT} ({proj.get('identifier')}), {len(existing)} existing items")

    for name, color in LABELS.items():
        if name not in labels:
            print(f"  create label {name}")
            if args.apply:
                labels[name] = p.call("POST", f"/projects/{pid}/labels/", {"name": name, "color": color})["id"]

    cycle_id = cycles.get(CYCLE[0])
    if not cycle_id:
        print(f"  create cycle {CYCLE[0]}")
        if args.apply:
            me = p.call("GET", "https://plane.in-stacks.com/api/v1/users/me/")["id"]
            cycle_id = p.call("POST", f"/projects/{pid}/cycles/", {"name": CYCLE[0], "start_date": CYCLE[1], "end_date": CYCLE[2],
                                                                 "project_id": pid, "owned_by": me})["id"]

    item_ids = []
    for it in schedule_items():
        body = {"name": it["name"], "description_html": it["desc"], "target_date": it["date"],
                "priority": it["priority"], "labels": [labels.get(it["label"])] if labels.get(it["label"]) else []}
        if it["id"] in existing:
            print(f"  update {it['name']}  (due {it['date']})")
            if args.apply:
                p.call("PATCH", f"/projects/{pid}/issues/{existing[it['id']]['id']}/", body)
            item_ids.append(existing[it["id"]]["id"])
        else:
            print(f"  create {it['name']}  (due {it['date']})")
            if args.apply:
                body["state"] = states.get("Todo")
                item_ids.append(p.call("POST", f"/projects/{pid}/issues/", body)["id"])

    if args.apply and cycle_id and item_ids:
        p.call("POST", f"/projects/{pid}/cycles/{cycle_id}/cycle-issues/", {"issues": item_ids})
        print(f"  added {len(item_ids)} items to cycle {CYCLE[0]}")
    print("done" if args.apply else "dry run only; re-run with --apply")


if __name__ == "__main__":
    main()
