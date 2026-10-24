"""Off-pitch context the writers may cite (D13, ADR-0015, FR-32).

The match context (B14 fills `effects` at kick-off) becomes a short list of citable items,
each with the id a sentence puts in `context_ids`. The Verifier only accepts ids from this
list, so an invented "back at his former club" is caught: it only accepts items the writer was
shown, about someone in the sentence, and a sentence that tells an off-pitch story must cite one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pivot_core.domain import CareerStint, Match, MatchContext, MatchEvent

MAX_ITEMS = 8
# Effects every player gets from the match itself (B14). They are listed after the stories, so a
# long list of them does not push news, ties and reunions out of the few items a writer sees.
BACKGROUND_SOURCES = {"competition", "stakes", "crowd", "weather", "referee"}


@dataclass(frozen=True)
class ContextItem:
    context_id: str                           # effect_id, news_id, relationship_id or stint_id
    kind: str                                 # "effect", "news", "relationship", "former_club"
    subject_ids: tuple[str, ...]              # people it is about
    text: str                                 # plain English, shown to the writer
    subject_names: tuple[str, ...] = ()       # how a sentence may name them, matched by the Verifier


def context_items(
    context: MatchContext,
    *,
    names: Mapping[str, str] | None = None,
    reunions: Iterable[tuple[str, CareerStint]] = (),
) -> list[ContextItem]:
    """Everything citable: applied effects, public news, relationships and reunions with a former club,
    with the effects that come from the match itself (crowd, stakes, ...) last."""
    names = names or {}

    def who(person_id: str) -> str:
        return names.get(person_id, person_id)

    def item(context_id: str, kind: str, subjects: tuple[str, ...], text: str) -> ContextItem:
        return ContextItem(context_id, kind, subjects, text, tuple(who(s) for s in subjects))

    def effects(background: bool) -> list[ContextItem]:
        return [item(e.effect_id, "effect", (e.subject_id,), f"{who(e.subject_id)}: {e.note}")
                for e in context.effects if (e.source in BACKGROUND_SOURCES) == background]

    items = effects(background=False)
    items += [item(n.news_id, "news", (n.subject_id,), f"{who(n.subject_id)}: {n.headline}")
              for n in context.news if n.public]
    items += [item(r.relationship_id, "relationship", (r.person_id, r.other_id),
                   f"{who(r.person_id)} and {who(r.other_id)}: {r.kind.replace('_', ' ')}")
              for r in context.relationships]
    for person_id, stint in reunions:
        role = "coached" if stint.as_coach else "played for"
        items.append(item(stint.stint_id, "former_club", (person_id,),
                          f"{who(person_id)} {role} {stint.club_name} before"))
    return items + effects(background=True)


def from_match(match: Match) -> list[ContextItem]:
    """Context items for a match, with names and reunions (a person facing a club they left)."""
    names, reunions = {}, []
    for team, opponent in ((match.home, match.away), (match.away, match.home)):
        people = [(p.player_id, p.name, p.career) for p in team.squad]
        people.append((team.coach.coach_id, team.coach.name, team.coach.career))
        for person_id, name, career in people:
            names[person_id] = name
            reunions += [(person_id, s) for s in career if s.club_id == opponent.club_id and s.to_year is not None]
    return context_items(match.context, names=names, reunions=reunions)


def relevant(items: Sequence[ContextItem], events: Iterable[MatchEvent], limit: int = MAX_ITEMS) -> list[ContextItem]:
    """Items about people in the window's events first, then the rest, capped."""
    events = list(events)
    involved = set().union(*(involved_in(e) for e in events))
    return sorted(items, key=lambda i: not involved & set(i.subject_ids))[:limit]


def involved_in(event: MatchEvent) -> set[str]:
    ids = {event.player_id, event.receiver_id}
    if event.substitution:
        ids |= {event.substitution.player_off_id, event.substitution.player_on_id}
    return {i for i in ids if i}


def known_ids(items: Iterable[ContextItem]) -> frozenset[str]:
    return frozenset(i.context_id for i in items)


def mentions(item: ContextItem, text: str, people: set[str]) -> bool:
    """True if the item is about someone the sentence is about: in its evidence, or named in its text.

    A name counts in full or by surname ("Okafor" for "R. Okafor"), not inside a longer Latin word.
    """
    if people & set(item.subject_ids):
        return True
    lowered = text.lower()
    forms = {f for name in item.subject_names for f in (name, *name.split()[-1:]) if len(f) >= 3}
    return any(re.search(rf"(?<![a-z]){re.escape(f.lower())}(?![a-z])", lowered) for f in forms)
