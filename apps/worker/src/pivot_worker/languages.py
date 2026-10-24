"""What changes per output language (D12, FR-25): writing instructions, word lists, length
limits, how numbers and minutes are written, and the template phrases.

Evidence and claims never change with the language, so the Verifier recomputes the same
numbers for every version; only the wording rules below are language-specific.
"""

from __future__ import annotations

import re
import unicodedata

from .vocabulary import BANNED_TERMS, DOWN_WORDS, SIGNIFICANCE_WORDS, UP_WORDS

INSTRUCTIONS = {
    "en": "Write in English.",
    "zh": ("Write in Simplified Chinese (简体中文). Keep team and player names exactly as given. Write numbers "
           "with Arabic digits exactly as in the claims, and match minutes as 61'."),
    "es": ("Write in Spanish (español neutro). Keep team and player names exactly as given. Write numbers "
           "with a decimal point exactly as in the claims, and match minutes as 61'."),
}

# Sentence and headline limits. Chinese is counted in characters, since it has no spaces.
MAX_SENTENCE = {"en": 30, "es": 35, "zh": 60}
MAX_HEADLINE = {"en": 8, "es": 10, "zh": 16}

# The English lists apply to every language (names and loanwords stay English); these are added.
UP = {"zh": ("上升", "增加", "提高", "升至", "翻倍", "更有可能", "可能性更大"),
      "es": ("subió", "aumentó", "creció", "se duplicó", "más probable")}
DOWN = {"zh": ("下降", "减少", "降低", "降至", "减半", "可能性更小", "更不可能"),
        "es": ("bajó", "cayó", "disminuyó", "descendió", "menos probable")}
SIGNIFICANCE = {"zh": ("显著", "明显", "决定性"),
                "es": ("significativo", "significativa", "significativamente", "claramente", "decisivo")}
BANNED = {"zh": ("赌", "赔率", "投注", "下注", "博彩", "一定", "肯定", "绝对", "必然", "毫无疑问", "永远", "从不"),
          "es": ("apuesta", "apuestas", "cuotas", "siempre", "nunca", "garantizado", "sin duda", "definitivamente")}

# Numbers written as words, which a headline may not carry any more than digits. "one", "un"
# and "一" are left out: they double as articles ("one more push", "un cambio", "一张牌").
NUMBER_WORDS = ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
                "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "dozen")
NUMBER = {"es": ("dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
                 "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
                 "treinta", "cuarenta", "cincuenta", "cien", "ciento", "mil", "docena")}
# Chinese numerals only count before a measure word ("两球", "三分钟"), so "前场三区" and "十分" ("very") pass.
_ZH_NUMBER = re.compile(r"[二两三四五六七八九十百千][〇零一二两三四五六七八九十百千]*\s*(?:个|球|粒|次|脚|张|名|人|记|场|分钟|比)")


def up_words(lang: str) -> tuple[str, ...]:
    return UP_WORDS + UP.get(lang, ())


def down_words(lang: str) -> tuple[str, ...]:
    return DOWN_WORDS + DOWN.get(lang, ())


def significance_words(lang: str) -> tuple[str, ...]:
    return SIGNIFICANCE_WORDS + SIGNIFICANCE.get(lang, ())


def banned_terms(lang: str) -> tuple[str, ...]:
    return BANNED_TERMS + BANNED.get(lang, ())


def number_words(text: str, lang: str) -> list[str]:
    """Numbers written out in words ("Two goals", "dos goles", "两球")."""
    words = NUMBER_WORDS + NUMBER.get(lang, ())
    found = [w for w in words if re.search(rf"\b{w}\b", text, re.I)]
    return found + (_ZH_NUMBER.findall(text) if lang == "zh" else [])


_CJK = re.compile(r"[㐀-鿿豈-﫿]")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def length(text: str, lang: str) -> int:
    """Words for English and Spanish; CJK characters plus any Latin words for Chinese."""
    if lang == "zh":
        return len(_CJK.findall(text)) + len(_CJK.sub(" ", text).split())
    return len(text.split())


def normalise(text: str, lang: str) -> str:
    """Full-width digits and punctuation to ASCII, and a Spanish decimal comma to a point."""
    text = unicodedata.normalize("NFKC", text)
    if lang == "es":
        text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return text


# Ways of writing a match minute that are not claims.
MINUTES = re.compile(r"(?<![A-Za-z\d.])\d{1,3}(?:\+\d{1,2})?['’′]|第\s*\d{1,3}\s*分钟|\bminuto\s+\d{1,3}\b")

# Template wording. Labels are only needed for the metrics the template may pick.
PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "goal": "{team} scored at {at}.", "goal_h": "{team} goal swings the match",
        "card": "{team} were shown a card at {at}.", "card_h": "A card changes the game",
        "substitution": "{team} made a substitution at {at}.", "substitution_h": "{team} change shifts the balance",
        "tactical_shift": "{team} changed their shape at {at}.", "tactical_shift_h": "{team} switch shifts the balance",
        "injury": "{team} lost a player to injury at {at}.", "injury_h": "An injury changes the game",
        "stat": "{owner} {label} {verb} from {a} to {b} in the next five minutes.",
        "rose": "rose", "fell": "fell",
        "momentum": "From there the momentum swung towards {team}.", "momentum_h": "Momentum swings to {team}",
        "fallback": "The match turned around this point.", "fallback_h": "Momentum swings",
    },
    "zh": {
        "goal": "{team}在{at}进球。", "goal_h": "{team}进球扭转局势",
        "card": "{team}在{at}吃到一张牌。", "card_h": "一张牌改变比赛",
        "substitution": "{team}在{at}换人。", "substitution_h": "{team}换人改变平衡",
        "tactical_shift": "{team}在{at}调整了阵型。", "tactical_shift_h": "{team}变阵改变平衡",
        "injury": "{team}在{at}有球员受伤离场。", "injury_h": "伤病改变比赛",
        "stat": "此后五分钟，{team}的{label}从{a}{verb}到{b}。",
        "rose": "上升", "fell": "下降",
        "momentum": "此后比赛势头倒向{team}。", "momentum_h": "势头倒向{team}",
        "fallback": "比赛在这一刻发生了转折。", "fallback_h": "比赛势头逆转",
    },
    "es": {
        "goal": "{team} marcó en el {at}.", "goal_h": "El gol de {team} cambia el partido",
        "card": "{team} vio una tarjeta en el {at}.", "card_h": "Una tarjeta cambia el partido",
        "substitution": "{team} hizo un cambio en el {at}.", "substitution_h": "El cambio de {team} inclina la balanza",
        "tactical_shift": "{team} cambió su dibujo en el {at}.", "tactical_shift_h": "El ajuste de {team} inclina la balanza",
        "injury": "{team} perdió a un jugador por lesión en el {at}.", "injury_h": "Una lesión cambia el partido",
        "stat": "En los cinco minutos siguientes, {label} de {team} {verb} de {a} a {b}.",
        "rose": "subió", "fell": "bajó",
        "momentum": "A partir de ahí el impulso pasó a {team}.", "momentum_h": "El impulso pasa a {team}",
        "fallback": "El partido cambió en este momento.", "fallback_h": "El partido da un giro",
    },
}

LABELS = {
    "zh": {"threat_total": "威胁值", "passes_final_third": "进入前场三区的传球", "box_entries": "进入禁区次数",
           "shots": "射门", "pressures": "逼抢次数", "xg": "预期进球"},
    "es": {"threat_total": "la amenaza creada", "passes_final_third": "los pases al último tercio",
           "box_entries": "las llegadas al área", "shots": "los remates", "pressures": "las presiones",
           "xg": "los goles esperados"},
}
