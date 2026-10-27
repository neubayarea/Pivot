#!/usr/bin/env python3
"""Export the shared data models to JSON Schema for the frontend and other services.

Usage:
  uv run scripts/export_contracts.py           # write packages/contracts/schema/pivot.schema.json
  uv run scripts/export_contracts.py --check   # exit 1 if the committed schema is out of date (CI)

Then regenerate the TypeScript types: pnpm --filter @pivot/contracts gen:types
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from pivot_api.prematch import CONTRACT_MODELS as PREMATCH_MODELS
from pivot_api.pretext import CONTRACT_MODELS as PRETEXT_MODELS
from pivot_core.domain import CONTRACT_MODELS as DOMAIN_MODELS

# The domain models, then the API's own responses that are not domain models (the pre-match page, Bx15,
# and its sentences in the page's language, Bx19).
CONTRACT_MODELS = (*DOMAIN_MODELS, *PREMATCH_MODELS, *PRETEXT_MODELS)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packages" / "contracts" / "schema" / "pivot.schema.json"


def tidy(node: object) -> object:
    """Make Pydantic's output friendlier to json-schema-to-typescript.

    - drop per-field titles, otherwise every field becomes its own TS type alias;
    - write tuples in the draft-07 form (`items` as a list), which json2ts understands.
    """
    if isinstance(node, list):
        return [tidy(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: tidy(v) for k, v in node.items()}
    if "prefixItems" in out:
        out["items"] = out.pop("prefixItems")
        out["additionalItems"] = False
    if isinstance(out.get("properties"), dict):
        for prop in out["properties"].values():
            if isinstance(prop, dict):
                prop.pop("title", None)
    return out


def build() -> str:
    _, schema = models_json_schema(
        [(m, "serialization") for m in CONTRACT_MODELS], ref_template="#/$defs/{model}"
    )
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://github.com/neubayarea/Pivot/packages/contracts/schema/pivot.schema.json",
        "title": "Pivot",
        "description": "Generated from packages/pivot_core/src/pivot_core/domain and apps/api/src/pivot_api/prematch.py. "
                       "Do not edit by hand.",
        **tidy(schema),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed schema differs")
    args = ap.parse_args()

    text = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is out of date: run uv run scripts/export_contracts.py")
            sys.exit(1)
        print("contracts up to date")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(CONTRACT_MODELS)} models)")


if __name__ == "__main__":
    main()
