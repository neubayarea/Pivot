#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["openai>=1.50", "azure-identity>=1.17"]
# ///
"""D01: check that both Foundry model deployments answer, and that 10 requests at once are not throttled.

Signs in with your `az login` identity (Entra ID); no API keys. Your account needs the
"Cognitive Services OpenAI User" role (or Azure AI User) on the Foundry resource.

Usage:
  export PIVOT_FOUNDRY_ENDPOINT=https://<resource>.openai.azure.com/
  export PIVOT_MODEL_STANDARD=<standard deployment name>
  export PIVOT_MODEL_MINI=<mini deployment name>
  uv run scripts/foundry_quota_test.py                 # 10 concurrent requests per deployment
  uv run scripts/foundry_quota_test.py --dry-run       # print what would be sent

Exit code 0 when every request succeeded with valid JSON, 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass

SCOPE = "https://cognitiveservices.azure.com/.default"
PROMPT = [
    {"role": "system", "content": 'Reply with a JSON object {"ok": true, "n": <the number you were given>}.'},
    {"role": "user", "content": "n = {n}"},
]


@dataclass
class Result:
    deployment: str
    status: str                 # "ok", "throttled", "bad_json" or "error"
    latency_ms: int
    detail: str = ""


def summarise(results: list[Result]) -> tuple[str, bool]:
    """A table per deployment and whether everything passed."""
    lines, passed = [], True
    for name in dict.fromkeys(r.deployment for r in results):
        rs = [r for r in results if r.deployment == name]
        counts = {s: sum(r.status == s for r in rs) for s in ("ok", "throttled", "bad_json", "error")}
        latencies = sorted(r.latency_ms for r in rs if r.status == "ok")
        p50 = int(statistics.median(latencies)) if latencies else 0
        p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0
        lines.append(f"{name}: {counts['ok']}/{len(rs)} ok, {counts['throttled']} throttled (429), "
                     f"{counts['bad_json']} bad JSON, {counts['error']} errors; p50 {p50} ms, p95 {p95} ms")
        lines += [f"  - {r.status}: {r.detail}" for r in rs if r.status != "ok" and r.detail][:3]
        passed &= counts["ok"] == len(rs)
    return "\n".join(lines), passed


async def call(client, deployment: str, n: int) -> Result:
    from openai import APIStatusError, RateLimitError

    messages = [PROMPT[0], {"role": "user", "content": PROMPT[1]["content"].format(n=n)}]
    start = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=deployment, messages=messages, response_format={"type": "json_object"},
            max_tokens=30, temperature=0,
        )
        ms = int((time.perf_counter() - start) * 1000)
        body = json.loads(response.choices[0].message.content or "")
        ok = body.get("ok") is True and body.get("n") == n
        return Result(deployment, "ok" if ok else "bad_json", ms, "" if ok else str(body)[:120])
    except RateLimitError as e:
        return Result(deployment, "throttled", int((time.perf_counter() - start) * 1000), str(e)[:120])
    except (APIStatusError, json.JSONDecodeError) as e:
        return Result(deployment, "error", int((time.perf_counter() - start) * 1000), str(e)[:120])


async def run(endpoint: str, deployments: list[str], concurrency: int, api_version: str) -> list[Result]:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AsyncAzureOpenAI

    token = get_bearer_token_provider(DefaultAzureCredential(), SCOPE)
    # max_retries=0 so a 429 shows up instead of being retried away.
    client = AsyncAzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=token, api_version=api_version,
                              max_retries=0, timeout=30)
    tasks = [call(client, d, n) for d in deployments for n in range(concurrency)]
    return list(await asyncio.gather(*tasks))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", default=os.environ.get("PIVOT_FOUNDRY_ENDPOINT"))
    parser.add_argument("--deployments", nargs="+",
                        default=[d for d in (os.environ.get("PIVOT_MODEL_STANDARD"),
                                             os.environ.get("PIVOT_MODEL_MINI")) if d])
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--api-version", default=os.environ.get("PIVOT_FOUNDRY_API_VERSION", "2024-10-21"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.endpoint or not args.deployments:
        print("Set PIVOT_FOUNDRY_ENDPOINT, PIVOT_MODEL_STANDARD and PIVOT_MODEL_MINI (or pass --endpoint and "
              "--deployments).", file=sys.stderr)
        return 2
    print(f"{args.endpoint}: {args.concurrency} concurrent requests to each of {', '.join(args.deployments)}")
    if args.dry_run:
        print(json.dumps(PROMPT, indent=1))
        return 0
    report, passed = summarise(asyncio.run(run(args.endpoint, args.deployments, args.concurrency, args.api_version)))
    print(report)
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
