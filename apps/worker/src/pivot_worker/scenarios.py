"""What-if scenario catalog: UI copy, when each scenario applies, and its default spec (D07).

The rules follow prototype section B5. `options_for` turns the catalog into the S3 chips for
one pivot: each option is either ready to run, or disabled with the reason shown on hover.
`list_scenario_types` is the Translator's tool (architecture §6.2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from pivot_core.domain import MatchEvent, Pivot

PRIME = "′"
MOVE_MIN, MOVE_MAX = 46, 85                   # a moved substitution must land in this range
DEFAULT_MOVE_TO = 74                          # elapsed minute, shown as 75′


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
    CatalogEntry("change_press", "Press higher from {minute}",
                 "One team presses one step higher (or lower) from the pivot onwards.",
                 "Any pivot.", ("team", "delta", "from_minute"),
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


def is_red_card(e: MatchEvent) -> bool:
    colour = e.meta.get("card") or e.meta.get("colour") or e.meta.get("color")
    return e.type == "card" and colour in ("red", "second_yellow")


def is_goal(e: MatchEvent) -> bool:
    return e.type == "shot" and e.shot_outcome == "goal" and e.period != 5


def _minute(m: int) -> str:
    return f"{m + 1}{PRIME}"                   # event minutes are 0-based, the clock is 1-based


def _closest(events: list[MatchEvent], pivot: Pivot) -> MatchEvent | None:
    """Prefer the pivot's own trigger, then the event nearest the pivot minute."""
    if not events:
        return None
    triggers = [e for e in events if e.event_id in pivot.trigger_event_ids]
    return (triggers or sorted(events, key=lambda e: abs(e.minute - pivot.minute)))[0]


def options_for(pivot: Pivot, events: Iterable[MatchEvent]) -> list[ScenarioOption]:
    """The five catalog chips for a pivot, most relevant target first, unavailable ones disabled.

    `events` is everything played so far, so a chip can target an event after the pivot
    (the prototype offers "Disallow 71′ goal" from the 63′ pivot).
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
        return ScenarioOption(type_, entry.label.format(minute=_minute(target.minute)), True,
                              target_event_id=target.event_id, at_minute=target.minute, team=target.team)

    options.append(target_option("cancel_substitution", subs))
    options.append(target_option("remove_red_card", reds))
    options.append(target_option("move_substitution", subs))
    options.append(target_option("remove_goal", goals))
    # The side the match turned against is the one a coach would ask to press higher.
    losing = "away" if pivot.direction == "home" else "home"
    options.append(ScenarioOption("change_press", CATALOG["change_press"].label.format(minute=_minute(pivot.minute)),
                                  True, at_minute=pivot.minute, team=losing,
                                  params={"delta": 1, "from_minute": pivot.minute}))
    # Chips for the pivot's own trigger come first, then the rest in catalog order.
    return sorted(options, key=lambda o: (not o.enabled, o.target_event_id not in pivot.trigger_event_ids))


def move_minute_valid(new_minute: int) -> bool:
    """`new_minute` is an elapsed minute (0-based), like every Minute in the contract."""
    return MOVE_MIN <= new_minute + 1 <= MOVE_MAX


def list_scenario_types() -> list[dict[str, object]]:
    """Translator tool: what each scenario does and which parameters it needs."""
    return [{"type": e.type, "description": e.description, "applies_when": e.applies_when,
             "params": list(e.params), "resume_from": e.resume_from} for e in CATALOG.values()]
