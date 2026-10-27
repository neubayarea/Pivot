"""Stat vocabulary and the word lists the writers and the Verifier share (D02, ADR-0005).

`pivot_core.domain.stats.StatMetric` is the list of stats; this module says what each one
means in plain English, so the prompts, the UI and B05's StatCalculator describe the same
thing. The word lists below are the single source for the style guide
(`apps/worker/prompts/style_guide.md`), the prompts and the Verifier's wording rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from pivot_core.domain import STAT_UNITS, StatMetric

Source = Literal["events", "metrics", "tracking"]


@dataclass(frozen=True)
class StatTerm:
    metric: str
    label: str            # analyst wording, e.g. "final-third passes"
    fan_label: str        # no abbreviations or jargon, for the fan audience
    definition: str       # what B05 counts for `team` within the window
    source: Source        # where B05 reads it from
    higher_means: str     # what a rise usually tells the viewer


# One entry per StatMetric, in the same order. Windows are left-closed, right-open minute
# ranges; every stat is for `StatRef.team`, or for one player when `player_id` is set.
STAT_TERMS: dict[str, StatTerm] = {t.metric: t for t in (
    StatTerm("possession_pct", "possession", "share of the ball",
       "Share of on-ball time the team had in the window, 0-100.", "events", "more control of the ball"),
    StatTerm("passes", "passes", "passes",
       "Passes attempted, completed or not.", "events", "more of the ball being moved"),
    StatTerm("pass_accuracy_pct", "pass accuracy", "passes finding a teammate",
       "Completed passes as a share of passes attempted, 0-100.", "events", "cleaner passing"),
    StatTerm("passes_final_third", "final-third passes", "passes into the attacking third",
       "Completed passes that end in the opponent's third.", "events", "more time spent attacking"),
    StatTerm("box_entries", "box entries", "times they got into the box",
       "Completed passes and carries that end in the opponent's penalty box.", "events", "more dangerous attacks"),
    StatTerm("shots", "shots", "shots",
       "Shots of any outcome, blocked ones included.", "events", "more attempts on goal"),
    StatTerm("shots_on_target", "shots on target", "shots on target",
       "Shots that were scored or saved.", "events", "the goalkeeper being tested more"),
    StatTerm("xg", "expected goals (xG)", "quality of chances",
       "Sum of the expected-goals value of every shot.", "events", "better chances created"),
    StatTerm("threat_total", "threat created", "danger created",
       "Sum of the threat-grid value added by the team's passes, carries and dribbles.", "events",
       "the ball moved into more dangerous areas"),
    StatTerm("pressures", "pressures", "times they closed down the ball",
       "Pressure events: a player closing down the opponent on the ball.", "events", "more aggressive pressing"),
    StatTerm("tackles_won", "tackles won", "tackles won",
       "Tackles that won the ball or knocked it loose.", "events", "more ball won in challenges"),
    StatTerm("interceptions", "interceptions", "passes cut out",
       "Opponent passes the team cut out.", "events", "reading the game better"),
    StatTerm("duels_won", "duels won", "one-on-one battles won",
       "Duels (ground and aerial) the team won.", "events", "winning more individual battles"),
    StatTerm("turnovers", "turnovers", "times they gave the ball away",
       "Possessions lost through a failed pass, a failed dribble, a miscontrol or being tackled.", "events",
       "more careless or more pressured on the ball"),
    StatTerm("momentum_avg", "momentum", "who was on top",
       "Mean of the per-minute momentum index over the window, from the team's point of view "
       "(above 0 means the team was on top), -1 to 1. Each minute's index compares the two sides' "
       "most dangerous moments of that minute and the few before it (Opta's match momentum).", "metrics",
       "the team was more on top"),
    StatTerm("line_height_m", "defensive line height", "how high the defence stood",
       "Mean distance of the back line from its own goal, in metres.", "tracking", "a higher, braver defensive line"),
    StatTerm("team_width_m", "team width", "how wide they spread",
       "Mean spread of the outfield players across the pitch, in metres.", "tracking", "a more stretched shape"),
    StatTerm("press_distance_m", "press distance", "how close they got to the ball",
       "Mean distance from the opponent's ball carrier to the nearest player of the team, in metres.", "tracking",
       "looser pressing (a fall means tighter pressing)"),
    StatTerm("distance_covered_km", "distance covered", "ground covered",
       "Total distance run by the team's players (or the player) in the window, in kilometres.", "tracking",
       "more running"),
    StatTerm("progressive_passes", "progressive passes", "passes that moved the ball forward",
             "Completed passes that move the ball clearly closer to the opponent's goal (see the data definitions).",
             "events", "more direct, forward play"),
    StatTerm("ppda", "PPDA", "how quickly they won the ball back",
             "Opponent passes allowed per defensive action in the opponent's build-up zone.", "events",
             "looser pressing (a fall means a more intense press)"),
    StatTerm("xa", "expected assists (xA)", "chances set up",
             "Sum of the expected-goals value of the shots the team's (or the player's) passes set up.", "events",
             "better chances being created for teammates"),
    StatTerm("field_tilt_pct", "field tilt", "share of play in the attacking third",
             "The team's share of both teams' touches in their attacking third, 0-100.", "events",
             "more territorial control"),
)}

# Units as the writers should print them after a number.
UNIT_SUFFIX: dict[str, str] = {"count": "", "pct": "%", "xg": " xG", "index": "", "m": " m", "km": " km", "ratio": ""}

# Direction words. A sentence that uses one must have a claim pair (same metric and team,
# two windows) whose difference has the matching sign; the Verifier checks this.
UP_WORDS = ("rose", "rise", "rising", "increased", "climbed", "jumped", "grew", "doubled", "tripled", "trebled",
            "quadrupled", "surged", "went up", "up from")
DOWN_WORDS = ("fell", "fall", "falling", "dropped", "decreased", "declined", "halved", "slumped", "dipped",
              "went down", "down from")
# Magnitude words: the later value must be about this many times the earlier one.
MAGNITUDE_WORDS = {"doubled": 2.0, "tripled": 3.0, "trebled": 3.0, "quadrupled": 4.0, "halved": 0.5}

# Likelihood words are direction words only in what-if comparisons, where they must match the
# change of the outcome they describe. On pivot cards ("looked more likely to score") they are free.
LIKELY_UP = ("more likely", "likelier")
LIKELY_DOWN = ("less likely",)

# Significance words are only allowed when the what-if confidence intervals do not overlap.
SIGNIFICANCE_WORDS = ("significant", "significantly", "clearly", "decisive", "decisively", "proven", "conclusive")

# Never allowed: betting language, absolutes the numbers cannot support, and blame.
BANNED_TERMS = (
    "bet", "betting", "odds", "wager", "punter", "accumulator", "bookmaker",
    "always", "never", "guaranteed", "certain", "certainly", "definitely", "undoubtedly", "100%",
    "single-handedly", "choked", "disgrace", "pathetic", "useless",
)

# Abbreviations and terms the fan audience should not see, spelled out too (D11 checks fan versions).
JARGON = ("xG", "xA", "xT", "PPDA", "half-space", "low block", "rest defence", "progressive",
          "expected goals", "expected-goals", "expected assists", "expected-assists", "expected threat")

# Off-pitch story words. A sentence that uses one must cite a match-context item (D13).
OFF_PITCH_WORDS = (
    "former club", "old club", "former side", "old side", "former team", "old team", "ex-club",
    "former employer", "old employer", "former boss", "old boss", "former manager", "former coach",
    "former teammate", "old teammate", "the club that sold", "sold him", "sold her", "first game back",
    "returns to face", "back against", "reunion", "feud", "grudge", "bad blood", "nightlife", "night out",
    "out late", "contract dispute", "transfer rumour", "off the pitch", "off-pitch",
    "that let him go", "who let him go", "that let her go", "who let her go", "that released him",
    "that released her", "old ground", "stomping ground", "boyhood club", "old teammates", "former teammates",
    "homecoming",
)


def vocabulary_markdown(audience: Literal["analyst", "fan"] = "analyst") -> str:
    """The vocabulary as a Markdown table, for injection into the system prompts."""
    rows = ["| metric | unit | say | meaning | a rise means |", "|---|---|---|---|---|"]
    for term in STAT_TERMS.values():
        say = term.label if audience == "analyst" else term.fan_label
        rows.append(f"| `{term.metric}` | {STAT_UNITS[term.metric]} | {say} | {term.definition} | {term.higher_means} |")
    return "\n".join(rows)


def metrics() -> tuple[str, ...]:
    return get_args(StatMetric)
