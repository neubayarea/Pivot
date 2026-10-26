"""What-if scenario catalog: UI copy, when each scenario applies, and its default spec (D07).

The rules follow prototype section B5. `options_for` turns the catalog into the S3 chips for
one pivot: each option is either ready to run, or disabled with the reason shown on hover.
`ScenarioOption.to_spec` turns a chosen chip into the ScenarioSpec the simulator runs.
`list_scenario_types` is the Translator's tool (architecture §6.2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from pivot_core.domain import MatchEvent, Pivot, ScenarioSpec, TeamTactics, label_at, period_starts

PRIME = "′"
MOVE_MIN, MOVE_MAX = 46, 85                   # a moved substitution must land in this range
DEFAULT_MOVE_TO = 74                          # new_minute, shown as 75′ (the sim plants it at 75′ on the clock)
LEAD_UP = 15                                  # minutes before a pivot in which an event can have caused it
PRESS_LEVELS = ("low", "mid", "high")


@dataclass(frozen=True)
class CatalogEntry:
    type: str
    label: str                                # with {minute} filled from the target event
    description: str
    applies_when: str
    params: tuple[str, ...]
    resume_from: str
    priority: str
    unavailable: str                          # disabled-chip reason when nothing in the match fits


CATALOG: dict[str, CatalogEntry] = {e.type: e for e in (
    CatalogEntry("cancel_substitution", "Cancel {minute} substitution",
                 "Replay from the substitution with both players kept as they were.",
                 "A substitution that already happened.", ("target_event_id",),
                 "The minute of the substitution.", "Must", "No substitution in this match yet"),
    CatalogEntry("remove_red_card", "Remove {minute} red card",
                 "Replay from the red card with the player staying on the pitch.",
                 "A red card that already happened.", ("target_event_id",),
                 "The minute of the red card.", "Must", "No red card in this match"),
    CatalogEntry("move_substitution", "Move substitution to {new_minute}",
                 "Make the same substitution at a different minute.",
                 f"A substitution that already happened; the new minute is between {MOVE_MIN}{PRIME} and "
                 f"{MOVE_MAX}{PRIME}.", ("target_event_id", "new_minute"),
                 "The earlier of the original and the new minute.", "Should", "No substitution in this match yet"),
    CatalogEntry("remove_goal", "Disallow {minute} goal",
                 "Replay from the goal as if it had been ruled out.",
                 "A goal that already happened.", ("target_event_id",),
                 "The minute of the goal.", "Should", "No goal in this match yet"),
    CatalogEntry("change_press", "Press {direction} from {minute}",
                 "One team presses one step higher (or lower, if already high) from the pivot onwards.",
                 "Any pivot.", ("team", "tactics"),
                 "The pivot minute.", "Could", ""),
)}


@dataclass(frozen=True)
class ScenarioOption:
    """One chip in the What-if Lab."""

    type: str
    label: str
    enabled: bool
    disabled_reason: str | None = None
    target_event_id: str | None = None
    at_minute: int | None = None
    team: str | None = None
    params: dict[str, int | str] = field(default_factory=dict)
    tactics: TeamTactics | None = None        # change_press: the team's tactics with the new press

    def to_spec(self, pivot_id: str, *, seed_base: int, n_runs: Literal[200, 500, 1000] = 500) -> ScenarioSpec:
        if not self.enabled or self.at_minute is None:
            raise ValueError(f"{self.type} is not available: {self.disabled_reason}")
        return ScenarioSpec(type=self.type, pivot_id=pivot_id, target_event_id=self.target_event_id,
                            at_minute=self.at_minute, team=self.team, tactics=self.tactics, params=dict(self.params),
                            n_runs=n_runs, seed_base=seed_base)


def card_colour(e: MatchEvent) -> str | None:
    """"yellow", "second_yellow" or "red" for a card event, else None. The simulator and feeds put the
    colour in `foul.card`; hand-made events may still use `meta`."""
    if e.type != "card":
        return None
    return (e.foul.card if e.foul else None) or e.meta.get("card") or e.meta.get("colour") or e.meta.get("color")


def is_red_card(e: MatchEvent) -> bool:
    return card_colour(e) in ("red", "second_yellow")


def is_goal(e: MatchEvent) -> bool:
    return e.type == "shot" and e.shot_outcome == "goal" and e.period != 5


def _minute(m: int) -> str:
    """A move's new minute: the sim plants it when the clock shows new_minute + 1 (whatif._apply)."""
    return f"{m + 1}{PRIME}"


def _clock(label: str) -> str:
    """A clock label ("63'", "45+2'") with the prime the chips use, so a chip reads like the event list."""
    return label.rstrip("'") + PRIME


def _closest(events: list[MatchEvent], pivot: Pivot) -> MatchEvent | None:
    """The event a chip is about, best first by:

    1. one of the pivot's own triggers;
    2. in the `LEAD_UP` minutes up to the pivot, so a later event is picked only when none of these
       could have caused it (the prototype offers "Disallow 71′ goal" from the 63′ pivot);
    3. a tactical substitution over one for fatigue or injury: that is the one that changes a match;
    4. the nearest to the pivot minute, the earlier one on a tie.
    """
    def rank(e: MatchEvent) -> tuple[bool, bool, bool, int, int]:
        lead_up = 0 <= pivot.minute - e.minute <= LEAD_UP
        tactical = e.substitution is not None and e.substitution.reason == "tactical"
        return (e.event_id not in pivot.trigger_event_ids, not lead_up, not tactical,
                abs(e.minute - pivot.minute), e.minute)
    return min(events, key=rank, default=None)


def options_for(pivot: Pivot, events: Iterable[MatchEvent],
                tactics: Mapping[str, TeamTactics] | None = None) -> list[ScenarioOption]:
    """The five catalog chips for a pivot, most relevant target first, unavailable ones disabled.

    `events` is everything played so far, so a chip can target an event after the pivot
    (the prototype offers "Disallow 71′ goal" from the 63′ pivot). `tactics` is each side's
    tactics at the pivot (defaults if unknown), so change_press can move the press one step.
    """
    played = list(events)
    subs = [e for e in played if e.type == "substitution"]
    reds = [e for e in played if is_red_card(e)]
    goals = [e for e in played if is_goal(e)]
    options = []

    def target_option(type_: str, pool: list[MatchEvent]) -> ScenarioOption:
        entry = CATALOG[type_]
        target = _closest(pool, pivot)
        if target is None:
            label = entry.label.replace(" {minute}", "").format(new_minute=_minute(DEFAULT_MOVE_TO))
            return ScenarioOption(type_, label, enabled=False, disabled_reason=entry.unavailable)
        if type_ == "move_substitution":
            new = DEFAULT_MOVE_TO if target.minute != DEFAULT_MOVE_TO else DEFAULT_MOVE_TO - 10   # elapsed minute
            return ScenarioOption(type_, entry.label.format(new_minute=_minute(new)), True,
                                  target_event_id=target.event_id, at_minute=min(target.minute, new),
                                  team=target.team, params={"new_minute": new})
        return ScenarioOption(type_, entry.label.format(minute=_clock(target.clock_label)), True,
                              target_event_id=target.event_id, at_minute=target.minute, team=target.team)

    options.append(target_option("cancel_substitution", subs))
    options.append(target_option("remove_red_card", reds))
    options.append(target_option("move_substitution", subs))
    options.append(target_option("remove_goal", goals))
    # The side the match turned against is the one a coach would ask to press higher.
    losing = "away" if pivot.direction == "home" else "home"
    current = (tactics or {}).get(losing) or TeamTactics()
    level = PRESS_LEVELS.index(current.press)
    higher = level < len(PRESS_LEVELS) - 1
    press = PRESS_LEVELS[level + 1 if higher else level - 1]
    label = CATALOG["change_press"].label.format(direction="higher" if higher else "lower",
                                                 minute=_clock(label_at(period_starts(played), pivot.minute * 60)))
    options.append(ScenarioOption("change_press", label, True, at_minute=pivot.minute, team=losing,
                                  tactics=current.model_copy(update={"press": press})))
    # Chips for the pivot's own trigger come first, then the rest in catalog order.
    return sorted(options, key=lambda o: (not o.enabled, o.target_event_id not in pivot.trigger_event_ids))


def move_minute_valid(new_minute: int) -> bool:
    """`new_minute` is an elapsed minute (0-based), like every Minute in the contract."""
    return MOVE_MIN <= new_minute + 1 <= MOVE_MAX


def list_scenario_types() -> list[dict[str, object]]:
    """Translator tool: what each scenario does and which parameters it needs."""
    return [{"type": e.type, "description": e.description, "applies_when": e.applies_when,
             "params": list(e.params), "resume_from": e.resume_from} for e in CATALOG.values()]
