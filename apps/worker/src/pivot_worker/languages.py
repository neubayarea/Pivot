"""What changes per output language (D12, FR-25): writing instructions, word lists, length
limits, how numbers and minutes are written, and the template phrases.

Evidence and claims never change with the language, so the Verifier recomputes the same
numbers for every version; only the wording rules below are language-specific.
"""

from __future__ import annotations

import re
import unicodedata

from .vocabulary import BANNED_TERMS, DOWN_WORDS, LIKELY_DOWN, LIKELY_UP, MAGNITUDE_WORDS, SIGNIFICANCE_WORDS, UP_WORDS

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
UP = {"zh": ("上升", "增加", "增多", "增长", "提高", "提升", "上涨", "回升", "攀升", "升至", "涨到", "涨至", "翻倍",
             "翻番", "翻了一番", "翻了一倍", "翻两番", "翻了两番"),
      "es": ("subió", "subieron", "aumentó", "aumentaron", "creció", "crecieron", "ascendió", "ascendieron",
             "se disparó", "se dispararon", "duplicó", "duplicaron", "triplicó", "triplicaron", "cuadruplicó",
             "cuadruplicaron")}
DOWN = {"zh": ("下降", "减少", "降低", "降至", "降到", "下滑", "下跌", "跌至", "跌到", "跌了", "回落", "减半", "减少一半",
               "少了一半"),
        "es": ("bajó", "bajaron", "cayó", "cayeron", "disminuyó", "disminuyeron", "descendió", "descendieron",
               "se redujo", "se redujeron", "se desplomó", "se desplomaron", "a la mitad")}
MAGNITUDE = {"zh": {"翻倍": 2.0, "翻番": 2.0, "翻了一番": 2.0, "翻了一倍": 2.0, "翻两番": 4.0, "翻了两番": 4.0,
                    "减半": 0.5, "减少一半": 0.5, "少了一半": 0.5},
             "es": {"duplicó": 2.0, "duplicaron": 2.0, "triplicó": 3.0, "triplicaron": 3.0, "cuadruplicó": 4.0,
                    "cuadruplicaron": 4.0, "a la mitad": 0.5}}
LIKELY_MORE = {"zh": ("更有可能", "可能性更大"), "es": ("más probable",)}
LIKELY_LESS = {"zh": ("可能性更小", "更不可能"), "es": ("menos probable",)}
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
_ZH_COUNTED = re.compile(r"[二两三四五六七八九十百千][〇零一二两三四五六七八九十百千]*\s*(?:个|球|粒|次|脚|张|名|人|记|场|分钟|比)")


def up_words(lang: str) -> tuple[str, ...]:
    return UP_WORDS + UP.get(lang, ())


def down_words(lang: str) -> tuple[str, ...]:
    return DOWN_WORDS + DOWN.get(lang, ())


def magnitude_words(lang: str) -> dict[str, float]:
    return {**MAGNITUDE_WORDS, **MAGNITUDE.get(lang, {})}


def likely_up(lang: str) -> tuple[str, ...]:
    return LIKELY_UP + LIKELY_MORE.get(lang, ())


def likely_down(lang: str) -> tuple[str, ...]:
    return LIKELY_DOWN + LIKELY_LESS.get(lang, ())


def significance_words(lang: str) -> tuple[str, ...]:
    return SIGNIFICANCE_WORDS + SIGNIFICANCE.get(lang, ())


def banned_terms(lang: str) -> tuple[str, ...]:
    return BANNED_TERMS + BANNED.get(lang, ())


def number_words(text: str, lang: str) -> list[str]:
    """Numbers written out in words ("Two goals", "dos goles", "两球")."""
    words = NUMBER_WORDS + NUMBER.get(lang, ())
    found = [w for w in words if re.search(rf"\b{w}\b", text, re.I)]
    return found + (_ZH_COUNTED.findall(text) if lang == "zh" else [])


_CJK = re.compile(r"[㐀-鿿豈-﫿]")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def length(text: str, lang: str) -> int:
    """Words for English and Spanish; CJK characters plus any Latin words for Chinese."""
    if lang == "zh":
        return len(_CJK.findall(text)) + len(_CJK.sub(" ", text).split())
    return len(text.split())


def normalise(text: str, lang: str) -> str:
    """Full-width digits and punctuation to ASCII; in Spanish, drop the thousands point ("9.000")
    and turn the decimal comma into a point."""
    text = unicodedata.normalize("NFKC", text)
    if lang == "es":
        text = re.sub(r"(?<![\d.,])[1-9]\d{0,2}(?:\.\d{3})+(?!\d|\.\d)", lambda m: m[0].replace(".", ""), text)
        text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return text


# Ways of writing a match minute that are not claims. A number in quotes ('12' or ‘12’) is not one.
MINUTES = re.compile(r"(?<![A-Za-z\d.])\d{1,3}(?:\+\d{1,2})?(?P<mark>['’′])|第\s*\d{1,3}\s*分钟|\bminuto\s+\d{1,3}\b")
# Lengths of time ("five minutes", "5分钟") are not claims either; checked after number words become digits.
DURATION = re.compile(r"(?<![\d.])\d+\s*(?:minutes?|mins?|minutos?|分钟)", re.IGNORECASE)


def mask_minutes(text: str) -> str:
    def replace(m: re.Match) -> str:
        if m["mark"] in ("'", "’"):
            before = text[:m.start()]
            if before.endswith(("'", "‘")) or before.rfind("‘") > before.rfind("’"):
                return m[0]
        return " "
    return MINUTES.sub(replace, text)


# Numbers written as words. "one"/"uno"/"un"/"una" and a lone 一 are left out: they mostly mean "a".
_EN_UNITS = ("zero", "", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
             "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_EN_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_ES_UNITS = ("cero", "", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
             "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte")
_ES_TENS = ("", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
_ES_VEINTI = ("", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
              "veintiocho", "veintinueve")
_ONES = ("one", "uno", "un", "una")


def _word_values(lang: str) -> dict[str, int]:
    en = lang == "en"
    units, tens = (_EN_UNITS, _EN_TENS) if en else (_ES_UNITS, _ES_TENS)
    values = {w: n for n, w in enumerate(units) if w}
    small = {n: w for n, w in enumerate(units[:10]) if w and n} | {1: "one" if en else "uno"}
    for t, word in enumerate(tens[2 if en else 3:], start=2 if en else 3):
        values[word] = t * 10
        values.update({(f"{word}-{u}" if en else f"{word} y {u}"): t * 10 + n for n, u in small.items()})
    if not en:
        values.update({w: 20 + n for n, w in enumerate(_ES_VEINTI) if w})
    return values


_WORD_VALUES = {lang: _word_values(lang) for lang in ("en", "es")}
_WORD_NUMBER = {lang: re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, v), key=len, reverse=True)) + r")\b",
                                 re.IGNORECASE) for lang, v in _WORD_VALUES.items()}
# A spelled number before these nouns counts things that are not stats ("the two teams").
_NOT_A_STAT = {"en": re.compile(r"\s+(?:teams?|sides?|halves|half)\b", re.IGNORECASE),
               "es": re.compile(r"\s+(?:equipos?|tiempos?)\b", re.IGNORECASE)}

_ZH_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# A Chinese numeral is a number after 从/到/至/为/达/了/是 or before a counter (次, 脚, 个 …), unless a
# word like 张 (a card), 队 (the two teams) or 分 (minutes) follows.
_ZH_NUMBER = re.compile(r"(?P<pre>[从到至为达了是]?)(?P<num>[零〇一二两三四五六七八九十百]+)(?P<post>[次脚粒记个倍%]?)")
_ZH_NOT_A_STAT = "张名位刻队支方场分组"


def _zh_value(numeral: str) -> int:
    total, current = 0, 0
    for ch in numeral:
        if ch in _ZH_DIGITS:
            current = _ZH_DIGITS[ch]
        else:                                     # 十 or 百
            total += (current or 1) * (10 if ch == "十" else 100)
            current = 0
    return total + current


def spell_out(text: str, lang: str) -> str:
    """Numbers written as words become digits, so they are checked like any other number."""
    if lang == "zh":
        def zh(m: re.Match) -> str:
            num, after = m["num"], text[m.end():m.end() + 1]
            counted = bool(m["post"]) or (bool(m["pre"]) and num != "一" and not (after and after in _ZH_NOT_A_STAT))
            return f"{m['pre']} {_zh_value(num)} {m['post']}" if counted else m[0]
        return _ZH_NUMBER.sub(zh, text)
    if lang not in _WORD_NUMBER:
        return text
    values, not_a_stat = _WORD_VALUES[lang], _NOT_A_STAT[lang]

    def word(m: re.Match) -> str:
        if not_a_stat.match(text, m.end()):
            return m[0]
        return str(values[m[0].lower()])
    return _WORD_NUMBER[lang].sub(word, text)


# "from A to B" in each language; A must be the earlier window's value.
_N = r"(-?\d+(?:\.\d+)?)"
FROM_TO = {"en": re.compile(rf"\bfrom\s+{_N}[^\d]{{0,15}}?\bto\s+{_N}", re.IGNORECASE),
           "es": re.compile(rf"\bde\s+{_N}[^\d]{{0,15}}?\ba\s+{_N}", re.IGNORECASE),
           "zh": re.compile(rf"[从由]\s*{_N}[^\d。；，,]{{0,8}}?(?:[到至]|变成|变为|成为)\s*{_N}")}

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

# Stat labels for the template. Fan labels avoid jargon, like `StatTerm.fan_label`.
LABELS = {
    "zh": {"threat_total": "威胁值", "passes_final_third": "进入前场三区的传球", "box_entries": "进入禁区次数",
           "shots": "射门", "pressures": "逼抢次数", "xg": "预期进球"},
    "es": {"threat_total": "la amenaza creada", "passes_final_third": "los pases al último tercio",
           "box_entries": "las llegadas al área", "shots": "los remates", "pressures": "las presiones",
           "xg": "los goles esperados"},
}
FAN_LABELS = {
    "zh": {"threat_total": "制造的威胁", "passes_final_third": "打到对方门前区域的传球", "shots": "射门次数"},
    "es": {"threat_total": "el peligro generado", "passes_final_third": "los pases cerca del área rival",
           "shots": "los disparos"},
}

# Fallback wording for what-if comparisons (comparator.template_comparison).
COMPARISON: dict[str, dict[str, str]] = {
    "en": {
        "win": "a {team} win", "draw": "a draw", "win_h": "{team} win", "draw_h": "draw",
        "first": "With the change, {outcome} became {word} in the replays.", "first_h": "Replays: {outcome} {word}",
        "more": "more likely", "less": "less likely",
        "none": "The replays with the change show no clear difference from the ones without it.",
        "none_h": "Replays show no clear difference",
        "apart": "The intervals do not overlap, so this is more than noise.",
        "noise": "The intervals overlap for every result, so any gap is within noise.",
    },
    "zh": {
        "win": "{team}获胜", "draw": "平局", "win_h": "{team}获胜", "draw_h": "平局",
        "first": "做出这一改变后，{outcome}在模拟中变得{word}。", "first_h": "模拟结果：{outcome}{word}",
        "more": "更有可能", "less": "更不可能",
        "none": "有没有这一改变，模拟结果都看不出差别。", "none_h": "模拟结果看不出差别",
        "apart": "两组结果的区间没有重叠，不只是随机波动。",
        "noise": "每种结果的区间都有重叠，差异在随机波动范围内。",
    },
    "es": {
        "win": "una victoria de {team}", "draw": "un empate", "win_h": "victoria de {team}", "draw_h": "empate",
        "first": "Con el cambio, {outcome} se volvió {word} en las simulaciones.", "first_h": "Simulaciones: {outcome} {word}",
        "more": "más probable", "less": "menos probable",
        "none": "Las simulaciones con el cambio no se distinguen de las que no lo tienen.",
        "none_h": "Las simulaciones no muestran diferencias",
        "apart": "Los intervalos no se solapan, así que es más que ruido.",
        "noise": "Los intervalos se solapan en todos los resultados, así que la diferencia está dentro del ruido.",
    },
}
