"""The pre-match page's sentences in the page's language (Bx19, #355).

GET /api/matches/{id}/prematch/text?lang=zh|es

The news headlines and the context-effect notes on the pre-match tab are written in English by the
simulator and the season (`pivot_core.sim.season`, `pivot_core.sim.effects`), from a few fixed
templates. This module recognises each template, takes out its names and numbers, and writes the same
sentence in Chinese or Spanish. The simulator is not touched: the English stays what it is, and the
page asks for the translations beside it.

- Templates first: deterministic, free, tested. Names and numbers are copied exactly as they are
  (club and player names are never translated, the #344 rule), and the few words chosen from a fixed
  list (the stakes, the weather, how a player left a club) have their own fixed translations.
- A sentence no template knows (a new one, or one cut at 120 characters) is translated by the model,
  as the pivot cards are (#222), and kept only if every name and number of the English is still there,
  no club name is translated, and it is in the right script. Kept translations are cached for the life
  of the process; a failed one is asked again after FAILED_RETRY_S.
- Without a model (`PIVOT_PIPELINE=fake`) such a sentence is left out of `texts`, so the page shows the
  English with its EN tag.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from pivot_core.domain import Match
from pivot_core.domain.common import Model
from pivot_worker.languages import club_name_forms, has_cjk, wrong_script
from pivot_worker.models import ModelClient, ModelUnavailable, model_client_from_env

log = logging.getLogger("pivot_api.pretext")

router = APIRouter(prefix="/api")

Lang = Literal["zh", "es"]
LANGS: tuple[Lang, ...] = ("zh", "es")
TIMEOUT_S = 30.0
FAILED_RETRY_S = 120.0


class PrematchText(Model):
    """`texts`: each English sentence of the pre-match tab that has a translation, and that translation.
    A sentence missing here is shown in English. `untranslated` lists those sentences."""
    match_id: str
    lang: str
    texts: dict[str, str]
    untranslated: list[str]


CONTRACT_MODELS = (PrematchText,)


# --- the templates ----------------------------------------------------------------------------------------

# Words a template picks from a fixed list (`sim.effects`): (zh, es) for each.
WORDS: dict[str, dict[str, tuple[str, str]]] = {
    "stakes": {"a knockout tie": ("淘汰赛", "una eliminatoria"),
               "a relegation fight": ("保级战", "la lucha por la permanencia"),
               "a title race": ("争冠战", "la pelea por el título"),
               "a race for a continental place": ("洲际赛席位之争", "la pelea por un puesto continental")},
    "what": {"a contract dispute": ("合同纠纷", "un conflicto de contrato"),
             "public criticism": ("外界批评", "las críticas públicas")},
    "how": {"released by them": ("当年被他们放走", "allí le dieron la baja"),
            "left on bad terms": ("当年不欢而散", "salió en malos términos"),
            "hardly played there": ("在那里很少出场", "apenas jugó allí"),
            "left on good terms": ("当年好聚好散", "salió en buenos términos")},
    "weather": {"clear": ("晴天", "Cielo despejado"), "rain": ("雨天", "Lluvia"), "wind": ("大风", "Viento"),
                "heat": ("高温", "Calor"), "snow": ("雪天", "Nieve")},
    "pitch": {"good": ("场地良好", "campo en buen estado"), "worn": ("场地磨损", "campo desgastado"),
              "heavy": ("场地泥泞", "campo pesado"), "artificial": ("人造草场地", "césped artificial")},
}
NUMBERS = {"n", "x", "year", "a", "c", "i"}      # copied as written: 41,250 stays 41,250


@dataclass(frozen=True)
class Template:
    key: str
    en: str                                       # {name} a name, {n} a number, {stakes} a word from WORDS
    zh: str
    es: str

    @property
    def pattern(self) -> re.Pattern[str]:
        out, pos = [], 0
        for m in re.finditer(r"\{(\w+)\}", self.en):
            out.append(re.escape(self.en[pos:m.start()]).replace("'s", "'s?"))   # Rovers' as well as City's
            field = m.group(1)
            if field in WORDS:
                out.append(f"(?P<{field}>" + "|".join(map(re.escape, WORDS[field])) + ")")
            elif field in NUMBERS:
                out.append(rf"(?P<{field}>\d[\d,.]*)")
            else:
                out.append(rf"(?P<{field}>\S.*?)")
            pos = m.end()
        out.append(re.escape(self.en[pos:]).replace("'s", "'s?"))
        return re.compile("^" + "".join(out) + "$")


TEMPLATES = (
    # news (`sim.season`: `_demo_news`, `_returner`, `_milestone`, `derived_news`, `_HEADLINES`)
    Template("news.hostile_for", "{team} fans plan a hostile welcome for {name}, who left the club for {other} on bad terms in {year}",
             "{team}球迷准备给{name}一个不友好的“欢迎”：他{year}年与球队闹翻后转投{other}",
             "La afición de {team} prepara un recibimiento hostil a {name}, que se fue al {other} en malos términos en {year}"),
    Template("news.hostile", "{team} fans plan a hostile welcome for {name}, who left the club on bad terms in {year}",
             "{team}球迷准备给{name}一个不友好的“欢迎”：他{year}年与球队不欢而散",
             "La afición de {team} prepara un recibimiento hostil a {name}, que salió del club en malos términos en {year}"),
    Template("news.faces", "{name} faces {team} for the first time since leaving the club in {year}",
             "{name}自{year}年离队后首次面对{team}",
             "{name} se enfrenta a {team} por primera vez desde que dejó el club en {year}"),
    Template("news.milestone", "{name} is one game away from {n} appearances for {team}",
             "{name}再出场一次，就将为{team}出场{n}次",
             "A {name} le falta un partido para llegar a {n} partidos con {team}"),
    Template("news.pressure", "{coach} under pressure after {n} defeats in {team}'s last five league games",
             "{team}近五轮联赛输了{n}场，{coach}帅位承压",
             "{coach}, bajo presión tras {n} derrotas en los últimos cinco partidos de liga de {team}"),
    Template("news.leads", "{coach} criticised after {team} dropped {n} points from winning positions this season",
             "{team}本赛季在领先时丢了{n}分，{coach}受到批评",
             "Críticas a {coach}: {team} ha dejado escapar {n} puntos estando por delante esta temporada"),
    Template("news.won", "{coach}'s {team} have won {n} of their last five",
             "{coach}执教的{team}近五场赢了{n}场",
             "El {team} de {coach} ha ganado {n} de sus últimos cinco partidos"),
    Template("news.top_scorer", "{name} is {team}'s top scorer in the league this season",
             "{name}是{team}本赛季联赛的头号射手",
             "{name} es el máximo goleador de {team} en la liga esta temporada"),
    # the recorded demo's (eval/fixtures/demo-1021), written before the count was dropped
    Template("news.top_scorer_count", "{name} has {n} league goals this season, the most at {team}",
             "{name}本赛季联赛已进{n}球，是{team}队内最多",
             "{name} lleva {n} goles en liga esta temporada, el máximo de {team}"),
    Template("news.contract_dispute", "{name} and {team} are still apart on a new contract",
             "{name}和{team}在续约问题上仍有分歧",
             "{name} y {team} siguen sin ponerse de acuerdo para renovar"),
    Template("news.transfer_rumour", "{name} is linked with a move away from {team} in the winter window",
             "有传闻称{name}将在冬窗离开{team}",
             "Vinculan a {name} con una salida de {team} en el mercado de invierno"),
    Template("news.new_contract", "{name} signs a new contract with {team} until {year}",
             "{name}与{team}续约至{year}年",
             "{name} renueva con {team} hasta {year}"),
    Template("news.nightlife", "{name} of {team} was seen at a nightclub two nights before the game",
             "{team}的{name}在赛前两晚被人看到出现在夜店",
             "{name}, de {team}, fue visto en una discoteca dos noches antes del partido"),
    # context-effect notes (`sim.effects`)
    Template("effect.away_former_club", "away at former club {club}, {how}",
             "客场挑战老东家{club}，{how}", "Visita a su exequipo, {club}: {how}"),
    Template("effect.home_former_club", "at home to former club {club}, {how}",
             "主场迎战老东家{club}，{how}", "Recibe a su exequipo, {club}: {how}"),
    Template("effect.rivalry", "bad blood with {other} on the other side",
             "和对面的{other}有过节", "Mala relación con {other}, que juega en el otro equipo"),
    Template("effect.teammate", "played together before with {other}",
             "以前和{other}做过队友", "Ya jugó antes junto a {other}"),
    Template("effect.late_night_legs", "a late night before the game: legs may go sooner",
             "赛前熬夜：体能可能更早下滑", "Trasnochó antes del partido: las piernas pueden fallar antes"),
    Template("effect.late_night", "a late night before the game",
             "赛前熬夜", "Trasnochó antes del partido"),
    Template("effect.distracted", "distracted by {what}",
             "因{what}分心", "Distraído por {what}"),
    Template("effect.fans_composure", "targeted by the home fans: may lose composure",
             "被主队球迷针对：可能失去冷静", "En el punto de mira de la afición local: puede perder la calma"),
    Template("effect.fans_booked", "targeted by the home fans: more likely to be booked",
             "被主队球迷针对：更容易吃牌", "En el punto de mira de la afición local: más riesgo de tarjeta"),
    Template("effect.form", "average rating {x} over the last {n} games",
             "近{n}场平均评分{x}", "Nota media de {x} en los últimos {n} partidos"),
    Template("effect.fatigue", "{n} days since the last game",
             "距上一场比赛只有{n}天", "{n} días desde el último partido"),
    Template("effect.stakes", "{stakes} lifts the side",
             "{stakes}让全队更有斗志", "{stakes} motiva al equipo"),
    Template("effect.stakes_pressure", "pressure rating {n} in {stakes}",
             "抗压评分{n}，面对{stakes}", "Resistencia a la presión {n} en {stakes}"),
    Template("effect.home_crowd", "home crowd of {a} in a ground for {c}",
             "主场{a}名观众，球场可容纳{c}人", "{a} aficionados locales en un estadio para {c}"),
    Template("effect.away_crowd", "away crowd of {a} in a ground for {c}, pressure rating {n}",
             "客场面对{a}名观众，球场可容纳{c}人，抗压评分{n}",
             "Juega fuera ante {a} aficionados en un estadio para {c}, resistencia a la presión {n}"),
    Template("effect.big_match", "big-match rating {n}, match importance {i} of 5",
             "大赛表现评分{n}，比赛重要性{i}级（满级5级）",
             "Rendimiento en partidos grandes {n}, importancia del partido {i} de 5"),
    Template("effect.weather", "{weather} weather, {pitch} pitch: ground passes less reliable",
             "{weather}，{pitch}：地面传球没那么稳", "{weather}, {pitch}: los pases a ras de suelo son menos fiables"),
)
_COMPILED = [(t, t.pattern) for t in TEMPLATES]


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def from_template(text: str, lang: Lang) -> str | None:
    """`text` in `lang` by the first template it fits, or None when none does."""
    for t, pattern in _COMPILED:
        m = pattern.match(text)
        if m is None:
            continue
        params = {k: WORDS[k][v][LANGS.index(lang)] if k in WORDS else v for k, v in m.groupdict().items()}
        out = getattr(t, lang).format(**params)
        return _upper_first(out) if lang == "es" else out
    return None


# --- what the page shows ------------------------------------------------------------------------------

def sentences(match: Match) -> list[str]:
    """Every English sentence of the pre-match tab that comes from the context: news headlines and effect notes."""
    ctx = match.context
    seen = dict.fromkeys([*(n.headline for n in ctx.news), *(e.note for e in ctx.effects)])
    return [s for s in seen if s]


def names_of(match: Match) -> list[str]:
    """The names a translation must keep exactly: clubs, players and coaches of both sides."""
    people = [p.name for t in (match.home, match.away) for p in t.squad] + [t.coach.name for t in (match.home, match.away)]
    return sorted({match.home.name, match.away.name, *people}, key=len, reverse=True)


_NUMBER = re.compile(r"\d[\d,.]*\d|\d")


def kept(source: str, out: str, lang: Lang, names: list[str], clubs: list[str]) -> bool:
    """A model translation is kept only with the same names and numbers as the English, no club name
    translated (#344) and written in the right script."""
    if not out.strip() or wrong_script(out, lang) or (lang == "zh" and not has_cjk(out)):
        return False
    if sorted(_NUMBER.findall(source)) != sorted(_NUMBER.findall(out)):
        return False
    if any(n in source and n not in out for n in names):
        return False
    return not any(f in out for club in clubs for f in club_name_forms(club, lang))


TRANSLATE_PROMPT = """You translate short football pre-match notes from English into {language}.
Return JSON only: {{"texts": ["...", ...]}}, one translation per input text, in the same order.
Translate the meaning faithfully and naturally; add nothing and drop nothing.
Keep every number exactly as written, with the same digits (no number words).
Keep team and player names exactly as given, in their original Latin spelling: never translate or
transliterate a club or player name (Harbour City stays Harbour City, never 海港城 or Ciudad Puerto)."""
LANGUAGE_NAMES = {"zh": "Simplified Chinese (简体中文)", "es": "Spanish (español neutro)"}


class PreText:
    """Translations of the pre-match sentences, by template and else by the model; kept ones cached."""

    def __init__(self, models: ModelClient | None = None):
        self.models = models
        self._cache: dict[tuple[str, str], str] = {}
        self._failed: dict[tuple[str, str], float] = {}

    async def translate(self, match: Match, lang: Lang) -> PrematchText:
        texts: dict[str, str] = {}
        ask: list[str] = []
        for s in sentences(match):
            done = from_template(s, lang) or self._cache.get((lang, s))
            if done:
                texts[s] = done
            elif time.monotonic() >= self._failed.get((lang, s), 0.0):
                ask.append(s)
        if ask and self.models is not None:
            texts.update(await self._ask(match, ask, lang))
        return PrematchText(match_id=match.match_id, lang=lang, texts=texts,
                            untranslated=[s for s in sentences(match) if s not in texts])

    async def _ask(self, match: Match, texts: list[str], lang: Lang) -> dict[str, str]:
        messages = [{"role": "system", "content": TRANSLATE_PROMPT.format(language=LANGUAGE_NAMES[lang])},
                    {"role": "user", "content": json.dumps({"texts": texts}, ensure_ascii=False)}]
        out: dict[str, str] = {}
        try:
            reply = json.loads((await self.models.complete_json("standard", messages, timeout=TIMEOUT_S)).text)
            got = reply["texts"] if isinstance(reply, dict) else None
            if not isinstance(got, list) or len(got) != len(texts):
                raise ValueError(f"expected {len(texts)} texts")
        except (ModelUnavailable, ValueError, KeyError, TypeError) as e:
            log.info("pre-match text not translated (%s)", e)
            got = [None] * len(texts)
        names, clubs = names_of(match), [match.home.name, match.away.name]
        for source, t in zip(texts, got):
            if isinstance(t, str) and kept(source, t.strip(), lang, names, clubs):
                out[source] = self._cache[lang, source] = t.strip()
            else:
                self._failed[lang, source] = time.monotonic() + FAILED_RETRY_S
        return out


def pretext_from_env() -> PreText:
    """The model only with `PIVOT_PIPELINE=detect`, as for the pivot cards; else templates only."""
    return PreText(model_client_from_env() if os.getenv("PIVOT_PIPELINE", "fake") == "detect" else None)


@router.get("/matches/{match_id}/prematch/text", response_model=PrematchText)
async def get_prematch_text(match_id: str, request: Request,
                            lang: Lang = Query(..., description="the page's language")) -> PrematchText:
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    return await request.app.state.pretext.translate(match, lang)


__all__ = ["CONTRACT_MODELS", "PreText", "PrematchText", "from_template", "pretext_from_env", "router", "sentences"]
