"""What-if behind the S3 buttons (A09): the chips of a pivot, replays in the background, results cached.

    GET  /api/pivots/{pivot_id}/scenarios   chips from the D07 catalog, disabled ones with the reason
    POST /api/scenarios                     {pivot_id, type, n_runs?: 200|500|1000, params?} -> 202 Scenario
    GET  /api/scenarios/{scenario_id}       the Scenario: status, done, and the result once completed
                                            (`?lang=zh|es`: the comparison in that language, Ax31)

A POST builds the `ScenarioSpec` from the chip and puts it on a queue; one scenario runs at a time and
the rest wait (`WhatIf`). A run replays the match it was asked about with the seed and plants it was
simulated with (`sims.Replay`), then plays both arms `n_runs` times in a process pool that lives as
long as the API (`run_whatif`, ADR-0009). `done` counts the replays finished in both arms, out of
2 × `spec.n_runs`. Then the Comparator ⇄ Verifier writes why the two groups differ (the template
without a model) into `result.narrative`. Each step is an AgentTrace in chain `whatif:{scenario_id}:…`
with `input_ref` = the scenario id, so the S4 trace page shows it with the match's other chains.
Progress and the end go out on the match's live channel as `scenario.progress` and
`scenario.completed` envelopes, whose payload is the Scenario plus `total`.

A finished scenario is cached by (match version, pivot, type, target event, params, n_runs, seed_base), with a
`seed_base` derived from the pivot and type, so the same question twice gets the same answer at once.
The cache goes through the result store (files or Cosmos DB, Ax10/Ax11), so it survives a restart; a
comparison that came from the template is written again on the first request after one.

Runs write the comparison in English. A GET with `?lang=` for another language gets a translation of
that English comparison (Ax39, as Ax35 does for pivot cards): the model translates only the headline and
sentence texts, evidence ids and claims are copied over, and the Verifier checks it; one rewrite, then
the template in that language. An English template comparison gets the template in that language. A
translation that passed is stored with the scenario (under `{cache key}.{lang}`), so it survives a
restart; switching the page's language never replays the match. At startup the recorded demo's finished
scenarios are translated into `PIVOT_PREWARM_LANGS` once its warm-up has run.

200 replays per arm take ~45 s from the 38' red card on a 10-core laptop and several minutes on a
2-core VM. So every chip of the recorded demo is run ahead of time on a bigger machine
(scripts/make_whatif_fixture.py, Bx11) into `demo-1021.whatif.json` next to it, which is read at
startup and used like the result store, by cache key; a file made for another version of the demo is
ignored. A stored result is not replayed, only its comparison is asked of the model again, as for a
template comparison in the store. At startup the warm-up asks for the comparison of each pivot's chips
in that file, and runs the first `PIVOT_WHATIF_WARM` chips of each pivot that are not in it, in the
background, after anything a viewer asks for.

Environment:
- `PIVOT_WHATIF_WORKERS`: replay processes; default one less than the cores, at least 1, so a core
  stays free for the API and the live replay. 0 plays them in a thread of the API process (tests).
- `PIVOT_WHATIF_WARM`: chips per pivot of the recorded demo, not in its file, to run at startup (default 2,
  0 off, which also leaves the file's comparisons to the first viewer).
- `PIVOT_WHATIF_MAX_QUEUED`: scenarios waiting at most; a POST beyond that is a 503 (default 20).
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import multiprocessing
import os
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pivot_adapters import Adapters
from pivot_core.domain import (
    AgentTrace,
    Envelope,
    Match,
    Narrative,
    Pivot,
    Scenario,
    ScenarioSpec,
    SimResult,
    Verdict,
    VerifierIssue,
    ViewerPrefs,
)
from pivot_core.domain.narrative import Language
from pivot_core.domain.scenarios import ScenarioType
from pivot_core.sim.whatif import run_whatif
from pivot_worker.comparator import compare, template_comparison, verify_comparison
from pivot_worker.detect import EXPLAINER_TIMEOUT
from pivot_worker.languages import wrong_script
from pivot_worker.models import ModelClient, ModelUnavailable
from pivot_worker.pipeline import Step
from pivot_worker.scenarios import CATALOG, PRIME, ScenarioOption, move_minute_valid, options_for

from .personalize import MAX_CHECKS as MAX_TRANSLATIONS
from .personalize import translated_narrative, translation_messages
from .sims import FIXTURE, Replay

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api")

NRuns = Literal[200, 500, 1000]
DEFAULT_RUNS: NRuns = 200
DEFAULT_WARM = 2
DEFAULT_MAX_QUEUED = 20
NOT_REPLAYABLE = "This match cannot be replayed"
USER, WARM = 0, 1                             # queue priority: what a viewer asked for goes first
LANG_SEP = "."                                # "{cache key}.zh": a stored translation of that scenario

Runner = Callable[..., SimResult]             # `run_whatif`'s signature; tests pass a fake


class ScenarioRequest(BaseModel):
    pivot_id: str
    type: ScenarioType
    n_runs: NRuns = DEFAULT_RUNS
    params: dict[str, int | str] = {}


def chip(option: ScenarioOption) -> dict[str, Any]:
    """A chip as the web reads it."""
    return {"type": option.type, "label": option.label, "enabled": option.enabled,
            "disabled_reason": option.disabled_reason, "target_event_id": option.target_event_id,
            "at_minute": option.at_minute, "team": option.team, "params": dict(option.params)}


def seed_base(pivot_id: str, type_: str) -> int:
    """Same pivot and type, same replays: the first seed comes from them, not from the clock."""
    return int(hashlib.sha256(f"{pivot_id}|{type_}".encode()).hexdigest()[:7], 16)


def cache_key(version: str, spec: ScenarioSpec) -> str:
    """The target is in the key: when the catalog picks another event for a chip (Ax13), the replays
    against the old one are not served for it."""
    raw = json.dumps([version, spec.pivot_id, spec.type, spec.target_event_id, spec.params, spec.n_runs,
                      spec.seed_base], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def with_params(option: ScenarioOption, params: dict[str, int | str], target_minute: int) -> ScenarioOption:
    """The chip with the viewer's parameters; only a moved substitution has one (`new_minute`, elapsed).

    `target_minute` is the minute of the substitution being moved: replays start from the earlier one.
    """
    if not params or params == option.params:
        return option
    if option.type != "move_substitution" or set(params) != {"new_minute"}:
        raise ValueError(f"{option.type} takes no params {sorted(params)}"
                         + (" (only new_minute)" if option.type == "move_substitution" else ""))
    try:
        new = int(params["new_minute"])
    except ValueError:
        raise ValueError("new_minute must be a whole minute") from None
    if not move_minute_valid(new):
        raise ValueError(f"new_minute {new} is out of range: the substitution must land between 46{PRIME} and "
                         f"85{PRIME} (new_minute 45-84)")
    label = CATALOG["move_substitution"].label.format(new_minute=f"{new + 1}{PRIME}")
    return ScenarioOption(option.type, label, True, target_event_id=option.target_event_id,
                          at_minute=min(target_minute, new), team=option.team, params={"new_minute": new})


def precomputed_path(fixture: Path) -> Path:
    """`demo-1021.json` -> `demo-1021.whatif.json`: the chips of a recorded match run ahead of time."""
    return fixture.with_name(fixture.name.removesuffix(".json") + ".whatif.json")


# The site's simulated matches (Bx14): one file per match, keyed by the version its results belong to.
SEED_PRECOMPUTED_DIR = FIXTURE.parent / "whatif"


def seed_precomputed_path(match_id: str) -> Path:
    """`M-seed-101` -> `eval/fixtures/whatif/M-seed-101.whatif.json`."""
    return SEED_PRECOMPUTED_DIR / f"{match_id}.whatif.json"


def portable_sim_version() -> str:
    """`sims.SIM_VERSION` as a checkout with LF line endings (the Linux server, CI) works it out. On a
    Windows checkout (CRLF) `SIM_VERSION` hashes other bytes, so a file computed there would carry a
    version the server never matches; scripts/make_whatif_fixture.py writes this one instead."""
    import pivot_core.analytics as analytics_pkg
    import pivot_core.sim as sim_pkg

    h = hashlib.sha256()
    for pkg in (sim_pkg, analytics_pkg):
        for path in sorted(Path(pkg.__file__).parent.glob("*.py")):
            h.update(path.name.encode())
            h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def load_precomputed(path: Path, version: str) -> dict[str, Scenario]:
    """The scenarios in a file from scripts/make_whatif_fixture.py, by cache key; none when there is no
    file or it was made for another version of the match."""
    try:
        data = json.loads(path.read_bytes())
    except FileNotFoundError:
        return {}
    if data.get("version") != version:
        log.warning("%s is for match version %s, not %s: not used", path.name, data.get("version"), version)
        return {}
    return {key: Scenario.model_validate(s) for key, s in data["scenarios"].items()}


def write_precomputed(path: Path, match_id: str, version: str, scenarios: dict[str, Scenario]) -> None:
    """One scenario a line, in key order, so a re-run only changes the lines that changed."""
    lines = [f"{json.dumps(k)}: {s.model_dump_json()}" for k, s in sorted(scenarios.items())]
    head = json.dumps({"match_id": match_id, "version": version, "made_by": "scripts/make_whatif_fixture.py"})
    tmp = path.with_suffix(".tmp")
    body = ",\n".join(lines)
    tmp.write_text(f'{head[:-1]}, "scenarios": {{\n{body}\n}}}}\n', encoding="utf-8", newline="\n")
    tmp.replace(path)


@dataclass(order=True)
class Job:
    priority: int
    order: int
    scenario_id: str = field(compare=False)
    key: str = field(compare=False)
    label: str = field(compare=False)
    replay: Replay = field(compare=False)
    result: SimResult | None = field(compare=False, default=None)   # set: only the comparison is missing


class WhatIf:
    """Scenarios by id, the queue they wait in and the one task that runs them."""

    def __init__(self, adapters: Adapters, replays: dict[str, Replay], models: ModelClient, *,
                 runner: Runner = run_whatif, workers: int | None = None, max_queued: int = DEFAULT_MAX_QUEUED,
                 runs_override: int | None = None) -> None:
        self.adapters = adapters
        self.replays = replays
        self.models = models
        self.runner = runner
        self.workers = max(1, (os.cpu_count() or 2) - 1) if workers is None else workers
        self.max_queued = max_queued
        self.runs_override = runs_override        # tests: fewer replays than spec.n_runs
        self.scenarios: dict[str, Scenario] = {}
        self.precomputed: dict[str, dict[str, Scenario]] = {}   # match id -> cache key -> scenario run ahead (Bx11)
        self._keys: dict[str, str] = {}           # cache key -> scenario id
        self._queue: asyncio.PriorityQueue[Job] = asyncio.PriorityQueue()
        self._order = itertools.count()
        self._pool: Executor | None = None
        self._task: asyncio.Task | None = None
        self._pushes: set[asyncio.Future] = set()  # progress pushes in flight
        # (scenario id, language, chain of the English comparison) -> comparison in that language
        self._written: dict[tuple[str, Language, str | None], Narrative] = {}
        self._writing: defaultdict[tuple[str, Language, str | None], asyncio.Lock] = defaultdict(asyncio.Lock)

    @classmethod
    def from_env(cls, adapters: Adapters, replays: dict[str, Replay], models: ModelClient) -> WhatIf:
        workers = os.getenv("PIVOT_WHATIF_WORKERS")
        return cls(adapters, replays, models, workers=int(workers) if workers else None,
                   max_queued=int(os.getenv("PIVOT_WHATIF_MAX_QUEUED") or DEFAULT_MAX_QUEUED))

    def start(self) -> None:
        self._task = asyncio.create_task(self._serve(), name="whatif")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)

    # --- chips and requests ------------------------------------------------------------

    async def pivot(self, pivot_id: str) -> tuple[Pivot, Match]:
        match_id, sep, _ = pivot_id.rpartition(":p")
        repo = self.adapters.matches
        pivot = await repo.get_pivot(match_id, pivot_id) if sep else None
        match = await repo.get_match(match_id) if pivot else None
        if pivot is None or match is None:
            raise LookupError(f"pivot {pivot_id!r} not found")
        return pivot, match

    async def options(self, pivot: Pivot, match: Match) -> list[ScenarioOption]:
        replay = self.replays.get(match.match_id)
        before = await asyncio.to_thread(replay.build) if replay else match   # tactics at kick-off
        options = options_for(pivot, await self.adapters.matches.list_events(match.match_id),
                              {"home": before.home.tactics, "away": before.away.tactics})
        if replay is None:
            return [ScenarioOption(o.type, o.label, False, NOT_REPLAYABLE) for o in options]
        return options

    async def submit(self, pivot_id: str, type_: str, n_runs: NRuns = DEFAULT_RUNS,
                     params: dict[str, int | str] | None = None, priority: int = USER) -> Scenario:
        """The scenario for this question: a cached or running one if there is one, else a new one queued.

        Raises LookupError for an unknown pivot, ValueError for a chip that cannot run.
        """
        pivot, match = await self.pivot(pivot_id)
        option = next((o for o in await self.options(pivot, match) if o.type == type_), None)
        if option is None or not option.enabled:
            raise ValueError(f"{type_} is not available for this pivot"
                             + (f": {option.disabled_reason}" if option else ""))
        if params and params != option.params:
            target = next((e for e in await self.adapters.matches.list_events(match.match_id)
                           if e.event_id == option.target_event_id), None)
            option = with_params(option, params, target.minute if target else option.at_minute or 0)
        spec = option.to_spec(pivot_id, seed_base=seed_base(pivot_id, type_), n_runs=n_runs)
        replay = self.replays[match.match_id]
        key = cache_key(replay.version, spec)
        if (known := self._keys.get(key)) and self.scenarios[known].status != "failed":
            return self.scenarios[known]
        stored = self._stored(match.match_id).get(key)
        if stored is not None and stored.result is not None:
            self._keep(key, stored)
            if stored.result.narrative is not None and stored.result.narrative.source == "llm":
                return stored
            # The replays are kept; the comparison came from the template, so ask the model again.
            return self._enqueue(stored.model_copy(update={"status": "running"}), key, option.label, replay,
                                 priority, stored.result)
        if self._queue.qsize() >= self.max_queued:
            raise OverflowError("too many what-if scenarios are waiting; try again in a minute")
        scenario = Scenario(scenario_id=f"{match.match_id}:s{uuid.uuid4().hex[:12]}", match_id=match.match_id,
                            spec=spec, status="queued")
        return self._enqueue(scenario, key, option.label, replay, priority)

    def get(self, scenario_id: str) -> Scenario | None:
        if (scenario := self.scenarios.get(scenario_id)) is not None:
            return scenario
        match_id, sep, _ = scenario_id.rpartition(":s")       # finished before a restart: read back
        for key, stored in self._stored(match_id).items() if sep else ():
            if stored.scenario_id == scenario_id and LANG_SEP not in key:     # not one of its translations
                self._keep(key, stored)
                return stored
        return None

    async def in_language(self, scenario: Scenario, lang: Language) -> Scenario:
        """The scenario with its comparison in `lang`: read back, or translated on first request, then kept."""
        result = scenario.result
        if scenario.status != "completed" or result is None or result.narrative is None \
                or result.narrative.prefs.language == lang:
            return scenario
        english = result.narrative
        key = (scenario.scenario_id, lang, english.chain_id)   # the English one rewritten: translate it again
        async with self._writing[key]:       # two polls at once: write it once
            if (narrative := self._written.get(key)) is None:
                narrative = self._read_back(scenario, lang)
                if narrative is None:
                    narrative = await self._translate(scenario, result, lang)
                    if narrative.source == "llm":
                        await self._store_translation(scenario, lang, narrative)
                self._written[key] = narrative
        return scenario.model_copy(update={"result": result.model_copy(update={"narrative": narrative})})

    def _read_back(self, scenario: Scenario, lang: Language) -> Narrative | None:
        """A stored translation of the scenario's model-written comparison, if it is in `lang`'s script."""
        key = self._key_of(scenario.scenario_id)
        if key is None or scenario.result is None or scenario.result.narrative is None \
                or scenario.result.narrative.source != "llm":
            return None
        stored = self._stored(scenario.match_id).get(f"{key}{LANG_SEP}{lang}")
        narrative = stored.result.narrative if stored is not None and stored.result is not None else None
        if narrative is None or narrative.prefs.language != lang \
                or any(wrong_script(t, lang) for t in [narrative.headline, *(s.text for s in narrative.sentences)]):
            return None
        return narrative

    async def _store_translation(self, scenario: Scenario, lang: Language, narrative: Narrative) -> None:
        key, results = self._key_of(scenario.scenario_id), self.adapters.results
        if key is None or results is None or scenario.result is None:
            return
        translated = scenario.model_copy(update={"result": scenario.result.model_copy(update={"narrative": narrative})})
        await results.store_scenario(scenario.match_id, f"{key}{LANG_SEP}{lang}", translated)

    def _key_of(self, scenario_id: str) -> str | None:
        return next((k for k, v in self._keys.items() if v == scenario_id), None)

    async def _translate(self, scenario: Scenario, result: SimResult, lang: Language) -> Narrative:
        """The English comparison translated into `lang` and checked; else the template in `lang`. Never raises."""
        english = result.narrative
        assert english is not None
        spec, prefs = scenario.spec, english.prefs.model_copy(update={"language": lang})
        chain = f"whatif:{scenario.scenario_id}:{lang}-{uuid.uuid4().hex[:6]}"
        steps = _ChainTraces(self, chain, scenario)
        match = await self.adapters.matches.get_match(scenario.match_id)
        events = {e.event_id: e for e in await self.adapters.matches.list_events(scenario.match_id)}
        team_names = _team_names(match)
        messages, checks = translation_messages(english, prefs), 0
        while english.source == "llm" and checks < MAX_TRANSLATIONS:
            try:
                reply = await self.models.complete_json("standard", messages, timeout=EXPLAINER_TIMEOUT)
            except ModelUnavailable as e:
                await steps.record(Step("translator", f"unavailable: {e}"[:200], "error"))
                break
            except Exception as e:            # a viewer is waiting: the template, not a 500
                log.warning("what-if %s: translator failed", scenario.scenario_id, exc_info=True)
                await steps.record(Step("translator", f"error: {e!r}"[:200], "error"))
                break
            checks += 1
            messages = messages[:2] + [{"role": "assistant", "content": reply.text}]
            try:
                draft = translated_narrative(english, reply.text, prefs, checks, chain)
            except (ValueError, TypeError, KeyError) as e:
                await steps.record(Step("translator", "invalid output", "retried" if checks > 1 else "ok",
                                        reply.model, tokens=reply.tokens))
                messages.append({"role": "user", "content": f"That reply was not usable ({e}). Try again."})
                continue
            verdict = verify_comparison(draft, result, at_minute=spec.at_minute, events=events,
                                        team_names=team_names, target_event_id=spec.target_event_id)
            # Spanish left in English passes the script check (both Latin), so an unchanged sentence is sent back.
            if untranslated := [i for i, (s, d) in enumerate(zip(english.sentences, draft.sentences)) if s.text == d.text]:
                verdict = Verdict(passed=False, issues=[*verdict.issues, VerifierIssue(
                    code="schema_invalid", sentence_index=untranslated[0],
                    message=f"Sentence {untranslated[0] + 1} was left in English; translate it.")])
            await steps.record(Step("translator", draft.headline, "retried" if checks > 1 else "ok", reply.model,
                                    tokens=reply.tokens))
            await steps.record(Step("verifier", "pass" if verdict.passed else "; ".join(i.code for i in verdict.issues),
                                    "ok" if verdict.passed else "rejected", verdict=verdict))
            if verdict.passed:
                return draft
            fixes = "\n".join(f"- {i.code}: {i.message}" for i in verdict.issues)
            messages.append({"role": "user", "content": f"The Verifier rejected that translation:\n{fixes}\n"
                                                        "Fix it and return the whole card again."})
        evidence = next((i for s in english.sentences for i in s.evidence_ids), None) or spec.target_event_id or "none"
        narrative = template_comparison(result, evidence_id=evidence, team_names=team_names, prefs=prefs,
                                        chain_id=chain, verifier_attempts=checks)
        await steps.record(Step("template", narrative.headline, "degraded"))
        return narrative

    async def _label(self, spec: ScenarioSpec) -> str:
        """The chip's English label, as the run was given it (the Comparator names the change with it)."""
        try:
            pivot, match = await self.pivot(spec.pivot_id)
            option = next(o for o in await self.options(pivot, match) if o.type == spec.type)
        except (LookupError, StopIteration):
            return spec.type.replace("_", " ")
        if spec.type == "move_substitution" and "new_minute" in spec.params:
            return CATALOG["move_substitution"].label.format(new_minute=f"{int(spec.params['new_minute']) + 1}{PRIME}")
        return option.label

    async def _compare(self, scenario: Scenario, result: SimResult, label: str, steps: _ChainTraces, chain: str,
                       prefs: ViewerPrefs | None = None) -> Narrative:
        spec, match_id = scenario.spec, scenario.match_id
        match = await self.adapters.matches.get_match(match_id)
        events = {e.event_id: e for e in await self.adapters.matches.list_events(match_id)}
        return await compare(result, scenario_label=label, target_event_id=spec.target_event_id,
                             at_minute=spec.at_minute, events=events, team_names=_team_names(match),
                             models=self.models, record=steps.record, prefs=prefs, chain_id=chain)

    def _stored(self, match_id: str) -> dict[str, Scenario]:
        """Scenarios finished earlier: the result store's over the ones run ahead of time."""
        results = self.adapters.results
        stored = results.scenarios(match_id) if results is not None else {}
        return {**ahead, **stored} if (ahead := self.precomputed.get(match_id)) else stored

    def _keep(self, key: str, scenario: Scenario) -> None:
        self.scenarios[scenario.scenario_id] = scenario
        self._keys[key] = scenario.scenario_id

    def _enqueue(self, scenario: Scenario, key: str, label: str, replay: Replay, priority: int,
                 result: SimResult | None = None) -> Scenario:
        self._keep(key, scenario)
        self._queue.put_nowait(Job(priority, next(self._order), scenario.scenario_id, key, label, replay, result))
        return scenario

    async def warm(self, match_id: str, per_pivot: int, wait: float = 600.0) -> None:
        """Queue the first `per_pivot` chips of every pivot of a match behind what viewers ask for, not
        counting the chips run ahead of time: those are queued too, for their comparison only.

        Pivots come from the worker, so this waits (up to `wait` seconds) for the candidates to settle.
        """
        repo, deadline = self.adapters.matches, time.monotonic() + wait
        while time.monotonic() < deadline:
            pivots = await repo.list_pivots(match_id)
            if pivots and all(p.status != "pending" for p in pivots):
                break
            await asyncio.sleep(10)
        ahead = {(s.spec.pivot_id, s.spec.type) for s in self.precomputed.get(match_id, {}).values()
                 if s.spec.n_runs == DEFAULT_RUNS}
        queued = replays = 0
        for pivot in await repo.list_pivots(match_id):
            if pivot.status == "rejected":
                continue
            match = await repo.get_match(match_id)
            assert match is not None
            fresh = 0
            for option in [o for o in await self.options(pivot, match) if o.enabled]:
                if (pivot.pivot_id, option.type) not in ahead:
                    if fresh >= per_pivot:
                        continue
                    fresh += 1
                try:
                    scenario = await self.submit(pivot.pivot_id, option.type, priority=WARM)
                except (LookupError, ValueError, OverflowError) as exc:
                    log.warning("what-if warm-up skipped %s %s: %s", pivot.pivot_id, option.type, exc)
                    continue
                if scenario.status != "completed":
                    queued += 1
                    replays += scenario.result is None
        log.info("what-if warm-up for %s: %d scenarios queued, %d of them to replay", match_id, queued, replays)

    async def prewarm(self, match_id: str, languages: list[Language], wait: float = 3600.0) -> int:
        """Translate every finished scenario of a match into `languages` ahead of the viewers (Ax39).

        Waits (up to `wait` seconds) for the match's queued and running scenarios to finish first, so it
        goes after the warm-up. Never replays anything. Returns how many translations the model wrote.
        """
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and any(
                s.match_id == match_id and s.status in ("queued", "running") for s in self.scenarios.values()):
            await asyncio.sleep(10)
        ids = {s.scenario_id for k, s in self._stored(match_id).items() if LANG_SEP not in k}
        ids |= {s.scenario_id for s in self.scenarios.values() if s.match_id == match_id}
        written = 0
        for scenario_id in sorted(ids):
            scenario = self.get(scenario_id)
            if scenario is None or scenario.status != "completed":
                continue
            for lang in languages:
                try:
                    translated = await self.in_language(scenario, lang)
                except Exception:
                    log.warning("what-if %s: prewarm in %s failed", scenario_id, lang, exc_info=True)
                    continue
                narrative = translated.result.narrative if translated.result else None
                written += narrative is not None and narrative.source == "llm" and narrative.prefs.language == lang
        return written

    # --- running -----------------------------------------------------------------------

    def _executor(self) -> Executor | None:
        if self.workers <= 0:
            return None
        if self._pool is None:
            # spawn, not fork: the API process runs threads (uvicorn, to_thread).
            self._pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=multiprocessing.get_context("spawn"))
        return self._pool

    async def _serve(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._run(job)
            except asyncio.CancelledError:
                raise
            except Exception:                 # one bad scenario must not stop the queue
                log.exception("what-if %s failed", job.scenario_id)
                await self._update(job.scenario_id, "scenario.progress", status="failed")

    async def _run(self, job: Job) -> None:
        scenario = self.scenarios[job.scenario_id]
        spec, match_id = scenario.spec, scenario.match_id
        runs = self.runs_override or spec.n_runs
        total = 2 * runs
        chain = f"whatif:{scenario.scenario_id}:{uuid.uuid4().hex[:6]}"
        steps = _ChainTraces(self, chain, scenario)
        result = job.result
        if result is None:
            await self._update(job.scenario_id, "scenario.progress", status="running", done=0)
            loop = asyncio.get_running_loop()

            def progress(done: int, _total: int) -> None:
                loop.call_soon_threadsafe(self._progress, job.scenario_id, done, total)

            replay = job.replay
            t0 = time.perf_counter()
            try:
                match = await asyncio.to_thread(replay.build)
                result = await asyncio.to_thread(
                    self.runner, match, spec, seed=replay.seed, plants=replay.plants, progress=progress,
                    pool=self._executor(), workers=max(self.workers, 1), scenario_id=scenario.scenario_id, n_runs=runs)
            except Exception as exc:
                log.warning("what-if %s could not run: %r", scenario.scenario_id, exc)
                await steps.record(Step("executor", f"error: {exc}"[:500], "error"))
                await self._update(job.scenario_id, "scenario.progress", status="failed")
                return
            await steps.record(Step("executor", f"{runs} replays per arm from {spec.at_minute + 1}' in "
                                                f"{time.perf_counter() - t0:.1f}s"))
        narrative = await self._compare(scenario, result, job.label, steps, chain)
        done = await self._update(job.scenario_id, "scenario.completed", status="completed", done=total,
                                  result=result.model_copy(update={"narrative": narrative}))
        if self.adapters.results is not None:
            await self.adapters.results.store_scenario(match_id, job.key, done)
        log.info("what-if %s done: %s, narrative %s", scenario.scenario_id, spec.type, narrative.source)

    def _progress(self, scenario_id: str, done: int, total: int) -> None:
        scenario = self.scenarios.get(scenario_id)
        if scenario is not None and scenario.status == "running" and done > scenario.done:
            scenario = self._set(scenario_id, done=min(done, total))
            task = asyncio.ensure_future(self._push("scenario.progress", scenario))
            self._pushes.add(task)
            task.add_done_callback(self._pushes.discard)

    def _set(self, scenario_id: str, **changes: Any) -> Scenario:
        scenario = self.scenarios[scenario_id] = self.scenarios[scenario_id].model_copy(update=changes)
        return scenario

    async def _update(self, scenario_id: str, type_: str, **changes: Any) -> Scenario:
        scenario = self._set(scenario_id, **changes)
        await self._push(type_, scenario)
        return scenario

    async def _push(self, type_: str, scenario: Scenario) -> None:
        total = 2 * (self.runs_override or scenario.spec.n_runs)
        await self.publish(type_, scenario.match_id, {**scenario.model_dump(mode="json"), "total": total})

    async def publish(self, type_: str, match_id: str, payload: dict[str, Any]) -> None:
        try:
            # The local publisher numbers envelopes itself; seq here is a placeholder.
            await self.adapters.live.publish(Envelope(type=type_, match_id=match_id, seq=0,
                                                      ts=datetime.now(UTC).isoformat(), payload=payload))
        except Exception:                     # push is a nice-to-have: the web polls GET anyway
            log.warning("could not push %s for %s", type_, match_id, exc_info=True)


def _team_names(match: Match | None) -> dict[str, str]:
    return {"home": match.home.name, "away": match.away.name} if match else {"home": "Home", "away": "Away"}


class _ChainTraces:
    """Steps of one what-if chain as numbered AgentTraces, like the worker's Detect chains."""

    def __init__(self, whatif: WhatIf, chain_id: str, scenario: Scenario) -> None:
        self.whatif, self.chain_id, self.scenario = whatif, chain_id, scenario
        self.step = 0
        self._t = time.monotonic()

    async def record(self, step: Step) -> None:
        now = time.monotonic()
        trace = AgentTrace(
            trace_id=f"{self.chain_id}:{self.step}", chain_id=self.chain_id, step=self.step,
            match_id=self.scenario.match_id, agent=step.agent, model=step.model, prompt_hash=step.prompt_hash,
            input_ref=self.scenario.scenario_id, output_summary=step.output_summary,
            latency_ms=int((now - self._t) * 1000), tokens=step.tokens, status=step.status, verdict=step.verdict)
        self.step += 1
        self._t = now
        await self.whatif.adapters.traces.append_trace(trace)
        await self.whatif.publish("trace.appended", trace.match_id, trace.model_dump(mode="json"))


# --- routes ------------------------------------------------------------------------------

def _whatif(request: Request) -> WhatIf:
    return request.app.state.whatif


@router.get("/pivots/{pivot_id}/scenarios")
async def list_scenarios(request: Request, pivot_id: str) -> list[dict[str, Any]]:
    """The What-if chips of a pivot ("{match_id}:p{minute}"), pivot's own trigger first.

    Each is `{type, label, enabled, disabled_reason, target_event_id, at_minute, team, params}`;
    a disabled one says why in `disabled_reason`.
    """
    whatif = _whatif(request)
    try:
        pivot, match = await whatif.pivot(pivot_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    return [chip(o) for o in await whatif.options(pivot, match)]


@router.post("/scenarios", status_code=202)
async def create_scenario(request: Request, body: ScenarioRequest) -> Scenario:
    """Run one chip: 202 with the Scenario, `queued` (or `completed` at once when it was asked before).

    404 for an unknown pivot, 422 for a disabled chip or bad params, 503 when too many are waiting.
    """
    try:
        return await _whatif(request).submit(body.pivot_id, body.type, body.n_runs, body.params)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except OverflowError as e:
        raise HTTPException(503, str(e)) from None


@router.get("/scenarios/{scenario_id}")
async def get_scenario(request: Request, scenario_id: str, lang: Language = "en") -> Scenario:
    """Status, `done` (replays finished in both arms, out of 2 × spec.n_runs) and, once completed, the result.

    `lang` (en/zh/es) asks for the comparison in that language; the first such request writes it.
    """
    whatif = _whatif(request)
    scenario = whatif.get(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"scenario {scenario_id!r} not found")
    return await whatif.in_language(scenario, lang)


__all__ = ["WhatIf", "chip", "cache_key", "load_precomputed", "portable_sim_version", "precomputed_path", "router",
           "seed_base", "seed_precomputed_path",
           "with_params", "write_precomputed"]
