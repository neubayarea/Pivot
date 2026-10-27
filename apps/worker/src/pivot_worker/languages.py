"""What changes per output language (D12, FR-25): writing instructions, word lists, length
limits, how numbers and minutes are written, and the template phrases.

Evidence and claims never change with the language, so the Verifier recomputes the same
numbers for every version; only the wording rules below are language-specific.
"""

from __future__ import annotations

import re
import unicodedata

from .vocabulary import (
    BANNED_TERMS,
    DOWN_WORDS,
    JARGON,
    LIKELY_DOWN,
    LIKELY_UP,
    MAGNITUDE_WORDS,
    OFF_PITCH_WORDS,
    SIGNIFICANCE_WORDS,
    UP_WORDS,
)

INSTRUCTIONS = {
    "en": "Write in English.",
    "zh": ("Write in Simplified Chinese (简体中文). Keep team and player names exactly as given, in Latin letters; "
           "never translate or transliterate them (Harbour City, not 海港城). Write numbers "
           "with Arabic digits exactly as in the claims, and match minutes as 61'."),
    "es": ("Write in Spanish (español neutro). Keep team and player names exactly as given; never translate "
           "them (Harbour City, not Ciudad Puerto). Write numbers "
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
FAN_JARGON = {"zh": ("预期进球", "期望进球", "预期助攻", "期望助攻", "预期威胁"),
              "es": ("goles esperados", "gol esperado", "asistencias esperadas", "amenaza esperada")}
OFF_PITCH = {"zh": ("旧主", "老东家", "前东家", "旧东家", "老队友", "前队友", "老上司", "恩怨", "宿怨", "旧怨", "不和",
                    "重返", "夜店", "场外", "合同纠纷", "转会传闻", "当年放走", "放走他的", "放走她的", "母队", "旧主场",
                    "老主场", "故地", "昔日东家", "曾效力"),
             "es": ("antiguo club", "exclub", "ex club", "antiguo equipo", "exequipo", "excompañero",
                    "antiguo entrenador", "rencilla", "enemistad", "rencor", "reencuentro", "fuera del campo",
                    "vida nocturna", "que lo dejó ir", "que la dejó ir", "que lo dejó marchar", "que la dejó marchar",
                    "que lo vendió", "que la vendió", "antiguo estadio", "antigua casa", "exjugador", "ex jugador",
                    "excompañeros", "antiguos compañeros", "club de su infancia", "regreso a casa")}
# Off-pitch stories with a name in the middle ("the former Harbour man", "an ex-Rovers captain").
OFF_PITCH_PATTERN = re.compile(r"\b(?:former|ex-)\s*(?:[A-Z][\w'’-]*\s+){1,3}(?:man|woman|player|captain|striker|"
                               r"forward|winger|midfielder|defender|keeper|goalkeeper)\b")

# Words about the score (Dx8), by what they claim. Goal words describe what a goal did to the score;
# state words say where a team stood. Each is checked against the real score around the pivot.
# Words that also mean other things are left out on their own: "level", "levelled off", "behind",
# "fought back", "leading to", "ganando duelos", "perdiendo balones", "en ventaja numérica", "控球领先".
SCORE_WORDS = {
    "equaliser": {
        "en": ("equaliser", "equalizer", "equalise", "equalize", "equalises", "equalizes", "equalised", "equalized",
               "equalising", "equalizing", "draw level", "draws level", "drew level", "pull level", "pulls level",
               "pulled level", "levels the score", "levelled the score", "leveled the score", "level terms"),
        "zh": ("扳平", "追平", "扳回平局", "将比分扳平", "把比分扳平"),
        "es": ("gol del empate", "igualó el marcador", "iguala el marcador", "empató el partido",
               "empata el partido", "logra el empate", "logró el empate", "consigue el empate",
               "consiguió el empate"),
    },
    "take_lead": {
        "en": ("take the lead", "takes the lead", "took the lead", "taking the lead", "go ahead", "goes ahead",
               "went ahead", "going ahead", "edge ahead", "edges ahead", "edged ahead", "in front for the first time"),
        "zh": ("取得领先", "首开纪录", "打破僵局", "先拔头筹", "反超", "反超比分"),
        "es": ("se adelanta", "se adelantó", "se pone por delante", "se puso por delante", "toma la delantera",
               "tomó la delantera", "abre el marcador", "abrió el marcador"),
    },
    "extend_lead": {
        "en": ("extend the lead", "extends the lead", "extended the lead", "extending the lead",
               "extend their lead", "extends their lead", "extended their lead", "extending their lead",
               "double the lead", "doubles the lead", "double their lead", "doubles their lead",
               "stretch the lead", "stretches the lead", "stretched the lead", "stretch their lead",
               "stretches their lead", "stretched their lead", "increase their lead", "increases their lead",
               "increased their lead"),
        "zh": ("扩大领先", "扩大比分", "扩大优势", "领先优势扩大", "拉开比分"),
        "es": ("amplía la ventaja", "amplió la ventaja", "amplía su ventaja", "amplió su ventaja",
               "aumenta la ventaja", "aumentó la ventaja", "aumenta su ventaja", "aumentó su ventaja",
               "dobla la ventaja", "dobló la ventaja", "dobla su ventaja", "dobló su ventaja"),
    },
    "comeback": {
        "en": ("comeback", "come-back", "fightback", "fight-back", "come from behind", "comes from behind", "came from behind", "turn it around", "turns it around",
               "turned it around", "turn the game around", "turns the game around", "turned the game around"),
        "zh": ("逆转", "完成逆转", "反败为胜", "绝地反击"),
        "es": ("remontada", "remonta", "remontó", "remontar", "darle la vuelta", "le dio la vuelta"),
    },
    "trailing": {
        "en": ("trailing", "trailed", "trail by", "a goal down", "a goal behind", "goals down",
               "behind on the scoreboard", "chasing the game", "behind in the match",
               *(f"{verb} {article} {word}" for verb in ("chasing", "chase", "chased", "looking for", "pushing for",
                                                         "push for", "pushed for", "searching for", "hunting for")
                 for article in ("an", "the") for word in ("equaliser", "equalizer"))),
        "zh": ("比分落后", "处于落后", "落后一球", "落后两球", "落后的局面", "寻求扳平", "争取扳平", "追求扳平"),
        "es": ("iba perdiendo", "va perdiendo", "por debajo en el marcador", "abajo en el marcador",
               "a remolque", "busca el empate", "buscaba el empate", "buscando el empate", "buscar el empate"),
    },
    "leading": {
        "en": ("in the lead", "a goal up", "goals up", "protect the lead", "protect their lead",
               "protecting the lead", "protecting their lead", "protected their lead", "defend the lead",
               "defend their lead", "defending the lead", "defending their lead", "hold the lead",
               "hold their lead", "holding the lead", "holding their lead", "sit on the lead", "sit on their lead",
               "sitting on the lead", "sitting on their lead", "sat on their lead", "leading side",
               "ahead on the scoreboard", "with the lead"),
        "zh": ("比分领先", "保住领先", "保持领先", "领先一方", "守住领先", "带着领先", "领先的一方"),
        "es": ("por delante en el marcador", "arriba en el marcador", "con el marcador a favor", "iba ganando",
               "va ganando", "defender la ventaja", "defiende la ventaja", "defendía la ventaja",
               "proteger la ventaja", "protege la ventaja", "protegía la ventaja"),
    },
}


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


def score_words(lang: str) -> dict[str, tuple[str, ...]]:
    """Score words by kind; the English ones apply to every language."""
    return {kind: words["en"] + (words.get(lang, ()) if lang != "en" else ()) for kind, words in SCORE_WORDS.items()}


def jargon(lang: str) -> tuple[str, ...]:
    return JARGON + FAN_JARGON.get(lang, ())


def off_pitch_words(lang: str) -> tuple[str, ...]:
    return OFF_PITCH_WORDS + OFF_PITCH.get(lang, ())


def off_pitch_names(text: str) -> list[str]:
    """Off-pitch stories the word lists cannot hold because a team name sits inside them."""
    return [m[0] for m in OFF_PITCH_PATTERN.finditer(text)]


_CJK = re.compile(r"[㐀-鿿豈-﫿]")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


_LATIN_WORD = re.compile(r"[A-Za-zÀ-ÿ]+")


def wrong_script(text: str, lang: str) -> bool:
    """Chinese asked for and an English sentence written (a bare name like "Rovers" is fine), or Chinese in a
    Latin-script language. English and Spanish share a script, so one cannot be told from the other here."""
    if lang == "zh":
        return not has_cjk(text) and len(_LATIN_WORD.findall(text)) >= 3
    return has_cjk(text)


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
# An ordinal is a minute before "minute", a linking word or the end of a clause ("in the 61st and"),
# not before a noun ("their 12th shot"); "en el 63" is one unless it is a share ("en el 63%").
MINUTES = re.compile(r"(?<![A-Za-z\d.])\d{1,3}(?:\+\d{1,2})?(?P<mark>['’′])|第\s*\d{1,3}\s*分钟"
                     r"|\bminut[eo]\s+\d{1,3}(?:\+\d{1,2})?\b"
                     r"|(?<![A-Za-z\d.])\d{1,3}(?:st|nd|rd|th)\b(?=\s*-?\s*minute|\s*[.,;:!?)]|\s*$"
                     r"|\s+(?:and|but|when|as|after|before|with|while|then|in|on|of|for|from|to)\b)"
                     r"|\b(?:en|desde|hasta|tras)\s+el\s+\d{1,3}(?!\d|\s*%|[.,]\d)", re.IGNORECASE)
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


def minutes_in(text: str) -> list[str]:
    """Match minutes written in `text` ("86'", "第78分钟", "minuto 84", "en el 63", "45+2'"), as clock labels
    without the mark ("86", "45+2"). A number in quotes is not one, as in `mask_minutes`."""
    found = []
    for m in MINUTES.finditer(text):
        if m["mark"] in ("'", "’"):
            before = text[:m.start()]
            if before.endswith(("'", "‘")) or before.rfind("‘") > before.rfind("’"):
                continue
        if digits := re.search(r"\d{1,3}(?:\+\d{1,2})?", m[0]):
            found.append(digits[0])
    return found


# Stat names the Verifier recognises in Chinese and Spanish, besides the template labels (`LABELS`):
# a number next to one of these must be a claim on that stat (#254: field tilt written as 控球率).
STAT_NAMES = {
    "zh": {"possession_pct": ("控球率", "控球"), "field_tilt_pct": ("场地倾斜度", "场地倾斜", "前场占比"),
           "momentum_avg": ("势头",), "threat_total": ("威胁值", "制造的威胁"), "ppda": ("PPDA",),
           "pass_accuracy_pct": ("传球成功率", "传球准确率"), "shots_on_target": ("射正",),
           "pressures": ("逼抢次数", "压迫次数"), "line_height_m": ("防线高度",), "press_distance_m": ("逼抢距离",),
           "tackles_won": ("抢断成功",), "interceptions": ("拦截",), "turnovers": ("丢失球权", "失误")},
    "es": {"possession_pct": ("la posesión", "posesión"), "field_tilt_pct": ("la inclinación del campo",),
           "momentum_avg": ("el impulso", "impulso", "la inercia"), "threat_total": ("la amenaza creada",),
           "ppda": ("PPDA",), "pass_accuracy_pct": ("la precisión de pase", "precisión de pase")},
}

# How a translation must render the stat names (#222, #254): the translator gets this list.
GLOSSARY = {
    "zh": {"field tilt": "场地倾斜度 (never 控球率)", "possession": "控球率", "momentum": "势头",
           "threat created": "威胁值 (never 势头)", "PPDA": "PPDA", "pass accuracy": "传球成功率",
           "final-third passes": "进入前场三区的传球", "box entries": "进入禁区次数", "pressures": "逼抢次数"},
    "es": {"field tilt": "la inclinación del campo (never la posesión)", "possession": "la posesión",
           "momentum": "el impulso", "threat created": "la amenaza creada (never el impulso)", "PPDA": "PPDA"},
}

# The one word allowed between a team and the claim may not be a negation ("Harbour City never take
# control"), and "on top until ..." is the state before the pivot, not a claim about it (#339).
_GAP_EN = r"(?:(?!(?:not|never|cannot|failed|fail|fails|unable|no|nor|barely|hardly)\b)\w+\s+){0,1}?"
_GAP_ES = r"(?:(?!(?:no|nunca|jam[áa]s|sin|tampoco)\b)\w+\s+){0,1}?"
_NOT_UNTIL_EN = r"(?!\s+(?:until|till|before|up to)\b)"
_NOT_UNTIL_ES = r"(?!\s+(?:hasta|antes)\b)"
_NOT_NEGATED_ZH = r"(?<!没)(?<!未)(?<!没能)(?<!未能)(?<!无法)(?<!不再)(?<!没有)(?<!不能)"
_NOT_UNTIL_ZH = r"(?!之前|以前|直到|为止)"

# Momentum said to go to a team (#187). `{T}` is the team-name alternation; `gain` patterns name the side
# that took it, `lose` patterns the side that lost it (so the other side took it).
MOMENTUM_GAIN = {
    "en": (r"\bmomentum\b[^.;!?]{0,60}?\b(?:to|towards|toward|in favour of|in favor of)\s+(?:the\s+)?(?P<t>{T})",
           r"(?P<t>{T})(?:'s?)?\s+(?:\w+\s+){0,3}?(?:seiz\w*|t[ao]k\w*|took|grab\w*|gain\w*|w[io]n\w*|regain\w*|"
           r"claim\w*|stole|steal\w*|wrest\w*|snatch\w*)\s+(?:back\s+)?(?:the\s+)?(?:\w+\s+)?momentum\b",
           # Without the word momentum (#333): "sparks Harbour City revival", "Harbour City take control".
           # Kept small and next to the name; goal and score words (hit back, comeback) are not here.
           r"(?P<t>{T})(?:'s?)?\s+" + _GAP_EN + r"(?:revival|resurgence|renaissance|reawakening|fightback|fight-back)\b",
           r"\b(?:revival|resurgence)\s+(?:of|for|by)\s+(?:the\s+)?(?P<t>{T})",
           r"(?P<t>{T})\s+" + _GAP_EN + r"(?:take|takes|took|taking|seize|seizes|seized|seizing|wrest|wrests|wrested|"
           r"grab|grabs|grabbed|regain|regains|regained)\s+(?:back\s+)?(?:the\s+)?(?:control|command|charge|initiative)\b"
           + _NOT_UNTIL_EN,
           r"(?P<t>{T})\s+(?:are\s+|were\s+|is\s+|was\s+)?(?:back\s+)?(?:in control|in command|on top|take over|"
           r"takes over|took over|taking over)\b" + _NOT_UNTIL_EN,
           # Fighting back and being lifted (#333 follow-up: "Harbour City fights back with Miquingorini's goal",
           # "Miquingorini's goal lifts Harbour City"). Goal words ("hit back", "pull one back") stay out.
           r"(?P<t>{T})\s+" + _GAP_EN + r"(?:fight|fights|fought|fighting)\s+back\b" + _NOT_UNTIL_EN,
           r"(?<!to )(?<!not )(?<!n't )\b(?:lift|lifts|lifted|lifting)\s+(?:the\s+)?(?P<t>{T})(?!['’]s)\b",
           r"(?P<t>{T})\s+(?:are\s+|were\s+|is\s+|was\s+)?lifted\b",
           r"(?P<t>{T})\s+" + _GAP_EN + r"(?:lift|lifts|lifted|lifting)\s+(?:their|its)\s+(?:game|level|tempo|intensity)\b"),
    "zh": (r"势头[^。；！？]{0,12}?(?:倒向|转向|偏向|转到|转移到|移向|归于|站在)\s*(?P<t>{T})",
           r"(?P<t>{T})[^。；！？]{0,10}?(?:掌握|占据|夺回|抢回|抢到|赢得|拿到|获得|取得)(?:了)?[^。；！？]{0,4}?势头",
           r"(?P<t>{T})[^。；！？，,]{0,6}?" + _NOT_NEGATED_ZH + r"(?:复苏|复兴|掌控(?:了)?(?:比赛|局面|节奏)|"
           r"控制(?:了)?(?:比赛|局面)|占据(?:了)?(?:主动|上风)|夺回(?:了)?(?:主动|控制权)|重新掌控)" + _NOT_UNTIL_ZH,
           # 反击 is left out: it is also a counter-attack, a way of playing.
           r"(?P<t>{T})[^。；！？，,]{0,6}?" + _NOT_NEGATED_ZH + r"(?:振作|重振|反扑)",
           r"(?<!没有)(?<!没)(?<!未)提振(?:了)?\s*(?P<t>{T})",
           r"(?<!没有)(?<!没)(?<!未)激活(?:了)?\s*(?P<t>{T})"),
    "es": (r"(?:impulso|inercia)[^.;!?]{0,60}?\b(?:a favor de|hacia|pas[óo] a|pasa a|para|del lado de)\s+"
           r"(?:el\s+|los\s+)?(?P<t>{T})",
           r"(?P<t>{T})\s+(?:\w+\s+){0,3}?(?:tom[óoa]\w*|gan[óoa]\w*|recuper[óoa]\w*|se adueñ[óo] de|se hizo con|"
           r"se llev[óo])\s+(?:el\s+|la\s+)?(?:impulso|inercia)",
           r"(?P<t>{T})\s+" + _GAP_ES + r"(?:toma|tomó|toman|tomaron|recupera|recuperó|asume|asumió)\s+el\s+"
           r"(?:control|mando)\b" + _NOT_UNTIL_ES,
           r"(?P<t>{T})\s+(?:se hace|se hizo|se hacen|se hicieron)\s+con\s+el\s+(?:control|mando)\b" + _NOT_UNTIL_ES,
           r"\b(?:resurgir|resurgimiento)\s+(?:de|del)\s+(?P<t>{T})",
           r"(?P<t>{T})\s+" + _GAP_ES + r"(?:se rehace|se rehizo|se rehízo|reacciona|reaccionó)\b",
           r"(?<!no )\blevant(?:a|ó|an|aron)\s+a\s+(?:los\s+)?(?P<t>{T})",
           # "impulsa la remontada de Harbour City" (#333, live p74 in Spanish)
           r"(?<!sin )(?<!sin la )\bremontada\s+(?:de|del)\s+(?:los\s+)?(?P<t>{T})"),
}
MOMENTUM_LOSE = {
    "en": (r"\bmomentum\b[^.;!?]{0,40}?\baway from\s+(?:the\s+)?(?P<t>{T})",
           r"(?P<t>{T})\s+(?:\w+\s+){0,2}?(?:lost|lose|loses|losing|surrender\w*|ced\w*|gave up|give up)\s+"
           r"(?:the\s+)?momentum\b",
           r"(?P<t>{T})\s+" + _GAP_EN + r"(?:lost|lose|loses|losing)\s+(?:their\s+|its\s+|the\s+)?(?:grip|control|"
           r"command|hold)\b"),
    "zh": (r"(?P<t>{T})[^。；！？]{0,8}?(?:失去|丢掉|丧失|交出)(?:了)?[^。；！？]{0,4}?势头",
           r"(?P<t>{T})[^。；！？，,]{0,6}?" + _NOT_NEGATED_ZH + r"(?:失去|丢掉|丧失)(?:了)?(?:对比赛的)?(?:控制|掌控|主动)"),
    "es": (r"(?P<t>{T})\s+(?:\w+\s+){0,2}?(?:perdi[óo]|pierde|cedi[óo]|cede)\s+(?:el\s+|la\s+)?(?:impulso|inercia)",
           r"(?P<t>{T})\s+" + _GAP_ES + r"(?:perdi[óo]|pierde|pierden|perdieron)\s+el\s+(?:control|mando)\b"),
}
# How a club name gets translated or transliterated by mistake, word by word (#333: 激活海港城, and #186's
# 哈伯城). Club names stay as written in every language, so any of these forms is wrong.
CLUB_WORDS = {
    "zh": {"Harbour": ("海港", "港湾", "哈伯", "哈勃", "哈珀"), "City": ("城", "市"), "Northgate": ("北门", "诺斯盖特"),
           "Rovers": ("流浪者", "漫游者", "罗孚斯", "罗弗斯"), "United": ("联", "联队"), "Athletic": ("竞技",),
           "Town": ("镇",), "Wanderers": ("流浪者",), "Rangers": ("流浪者",), "Albion": ("阿尔比恩",), "Vale": ("谷",),
           "Bay": ("湾",), "Park": ("公园",), "Sporting": ("体育", "竞技")},
    "es": {"Harbour": ("Puerto", "Portuaria", "del Puerto"), "City": ("Ciudad",), "Northgate": ("Puerta Norte",),
           "Rovers": ("Errantes", "Vagabundos"), "United": ("Unido",), "Wanderers": ("Errantes",),
           "Rangers": ("Guardabosques",), "Bay": ("Bahía",)},
}


def club_name_forms(name: str, lang: str) -> list[str]:
    """Translated or transliterated forms of a club name in `lang`: the whole name with at least one word
    translated, and its first word translated (海港城, 北门流浪者, 哈伯城, 北门). A generic word alone (城) is never one."""
    words = CLUB_WORDS.get(lang, {})
    if not words:
        return []
    parts = name.split()
    options = [list(words.get(w, ())) + [w] for w in parts]
    forms: set[str] = set()

    def combos(i: int, chosen: list[str]) -> None:
        if i == len(options):
            if chosen != parts:
                if lang == "zh":
                    forms.add("".join(chosen))
                else:
                    forms.update({" ".join(chosen), " ".join(reversed(chosen)), " de ".join(reversed(chosen))})
            return
        for o in options[i]:
            combos(i + 1, chosen + [o])

    combos(0, [])
    if len(parts) > 1 and (first := words.get(parts[0])):
        forms.update(f for f in first if len(f) >= 2)
    return sorted(forms, key=len, reverse=True)


# Words for the two sides that stand for a team name.
SIDE_WORDS = {
    "en": {"home": ("home side", "home team", "hosts"), "away": ("away side", "away team", "visitors")},
    "zh": {"home": ("主队",), "away": ("客队",)},
    "es": {"home": ("el local", "los locales"), "away": ("el visitante", "los visitantes")},
}

# Reading a pressing stat the wrong way round (#254). For these stats a lower value means a more
# intense press, so after a fall "pressed less" is wrong and after a rise "pressed harder" is.
PRESS_INVERTED = ("ppda", "press_distance_m")
PRESS_MORE = {
    "en": ("more pressing", "pressed more", "pressed harder", "pressing harder", "pressing more", "more intense press",
           "more aggressive press", "pressed higher", "more defensive actions", "pressed more aggressively",
           "stepped up the press", "tighter press", "pressed tighter", "more intense"),
    "zh": ("逼抢更凶", "逼抢更积极", "逼抢更紧", "逼抢更强", "压迫更强", "压迫更紧", "压迫更凶", "防守动作更多", "逼抢加强",
           "压迫加强", "加强了逼抢", "加强了压迫", "逼抢强度上升", "压迫强度上升"),
    "es": ("más presión", "presionó más", "presionaron más", "presión más intensa", "más acciones defensivas",
           "presionó con más intensidad", "presión más alta"),
}
PRESS_LESS = {
    "en": ("less pressing", "pressed less", "less pressure", "fewer defensive actions", "eased off", "less aggressive",
           "less intense", "pressing less", "looser press", "pressed looser", "stopped pressing", "pressure eased",
           "dropped off"),
    "zh": ("逼抢更少", "逼抢减弱", "逼抢变弱", "压迫减弱", "压迫变弱", "防守动作更少", "放松了逼抢", "逼抢放松", "逼抢强度下降",
           "压迫强度下降"),
    "es": ("menos presión", "presionó menos", "presionaron menos", "menos acciones defensivas", "presión más floja",
           "presión más suave"),
}


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


# Multiples ("three times as many", "el triple", "是之前的三倍") in spelled-out text: the later value must
# be about this many times the earlier one. Counting ("hit the post three times") is not a multiple, nor
# is a tactical "doble pivote".
MULTIPLE = {
    "en": re.compile(r"\b(?:(?P<n>\d+(?:\.\d+)?)\s+times|(?P<w>twice))\s+(?:as\s+(?:many|much|high|often)|more|"
                     r"higher|greater|the)\b", re.IGNORECASE),
    "es": re.compile(r"\b(?:(?P<n>\d+(?:\.\d+)?)\s+veces\s+(?:más|mayor|lo|el|la|los|las)|el\s+(?P<w>doble|triple|"
                     r"cuádruple))\b(?!\s+pivote)", re.IGNORECASE),
    "zh": re.compile(r"(?:是|为|达到|成了|变成|变为)[^。；，,\d]{0,8}?(?P<n>\d+(?:\.\d+)?)\s*倍"),
}
_MULTIPLE_WORDS = {"twice": 2.0, "doble": 2.0, "triple": 3.0, "cuádruple": 4.0}


def multiples(text: str, lang: str) -> list[tuple[str, float]]:
    """Each multiple in spelled-out text and the factor it means."""
    pattern = MULTIPLE.get(lang)
    return [(m[0], float(m["n"]) if m["n"] else _MULTIPLE_WORDS[m["w"].lower()])
            for m in pattern.finditer(text)] if pattern else []


def mask_multiples(text: str, lang: str) -> str:
    """The factor of a multiple is checked as a ratio, not as a number."""
    pattern = MULTIPLE.get(lang)
    return pattern.sub(lambda m: " " * len(m[0]), text) if pattern else text


# Players on the pitch ("ten men", "10-man Rovers", "diez jugadores", "只剩10人") in spelled-out text: a
# count of players after red cards, checked against the cards rather than a claim.
PLAYER_COUNT = {
    "en": re.compile(r"(?<![A-Za-z\d.])(?P<n>\d+)(?=\s*-?\s*(?:men|man|players)\b)", re.IGNORECASE),
    "es": re.compile(r"(?<![A-Za-z\d.])(?P<n>\d+)(?=\s+(?:hombres|jugadores|futbolistas)\b)", re.IGNORECASE),
    "zh": re.compile(r"(?<![\d.])(?P<n>\d+)(?=\s*(?:人|名球员|名队员|名场上球员))"),
}


def player_counts(text: str, lang: str) -> dict[int, int]:
    """Where each player count starts in spelled-out text, and the count."""
    pattern = PLAYER_COUNT.get(lang)
    return {m.start(): int(m["n"]) for m in pattern.finditer(text)} if pattern else {}


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
        "stat_fan": "{owner} {label} {verb} to {b} in the next five minutes.",
        "stat_fan_possession_pct": "{team} had the ball {b} of the time in the next five minutes.",
        "rose": "rose", "fell": "fell",
        "momentum": "From there the momentum swung towards {team}.", "momentum_h": "Momentum swings to {team}",
        "momentum_lost": "From there {team} lost their grip on the game.", "momentum_lost_h": "{team} lose their grip",
        "fallback": "The match turned around this point.", "fallback_h": "Momentum swings",
    },
    "zh": {
        "goal": "{team}在{at}进球。", "goal_h": "{team}进球扭转局势",
        "card": "{team}在{at}吃到一张牌。", "card_h": "一张牌改变比赛",
        "substitution": "{team}在{at}换人。", "substitution_h": "{team}换人改变平衡",
        "tactical_shift": "{team}在{at}调整了阵型。", "tactical_shift_h": "{team}变阵改变平衡",
        "injury": "{team}在{at}有球员受伤离场。", "injury_h": "伤病改变比赛",
        "stat": "此后五分钟，{team}的{label}从{a}{verb}到{b}。",
        "stat_fan": "此后五分钟，{team}的{label}{verb}到{b}。",
        "rose": "上升", "fell": "下降",
        "momentum": "此后比赛势头倒向{team}。", "momentum_h": "势头倒向{team}",
        "momentum_lost": "此后{team}失去了比赛势头。", "momentum_lost_h": "{team}失去势头",
        "fallback": "比赛在这一刻发生了转折。", "fallback_h": "比赛势头逆转",
    },
    "es": {
        "goal": "{team} marcó en el {at}.", "goal_h": "El gol de {team} cambia el partido",
        "card": "{team} vio una tarjeta en el {at}.", "card_h": "Una tarjeta cambia el partido",
        "substitution": "{team} hizo un cambio en el {at}.", "substitution_h": "El cambio de {team} inclina la balanza",
        "tactical_shift": "{team} cambió su dibujo en el {at}.", "tactical_shift_h": "El ajuste de {team} inclina la balanza",
        "injury": "{team} perdió a un jugador por lesión en el {at}.", "injury_h": "Una lesión cambia el partido",
        "stat": "En los cinco minutos siguientes, {label} de {team} {verb} de {a} a {b}.",
        "stat_fan": "En los cinco minutos siguientes, {label} de {team} {verb} a {b}.",
        "rose": "subió", "fell": "bajó", "rose_pl": "subieron", "fell_pl": "bajaron",     # "los pases … subieron"
        "momentum": "A partir de ahí el impulso pasó a {team}.", "momentum_h": "El impulso pasa a {team}",
        "momentum_lost": "A partir de ahí {team} perdió el impulso.", "momentum_lost_h": "{team} pierde el impulso",
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
    "zh": {"threat_total": "制造的威胁", "passes_final_third": "打到对方门前区域的传球", "shots": "射门次数",
           "shots_on_target": "射正次数", "box_entries": "攻进禁区的次数", "possession_pct": "控球率"},
    "es": {"threat_total": "el peligro generado", "passes_final_third": "los pases cerca del área rival",
           "shots": "los disparos", "shots_on_target": "los disparos a puerta", "box_entries": "las llegadas al área",
           "possession_pct": "la posesión"},
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

# Why the groups differ (Bx10): the usual final score, and the clearest change in one team's numbers.
REASONS: dict[str, dict[str, str]] = {
    "en": {
        "scores": "As played, the most common final score was {a}; with the change it was {b}.",
        "scores_same": "The most common final score was {a} in both groups of replays.",
        "stat": "From that moment, {owner} {label} {verb} from {a} to {b} on average.",
        "stat_fan": "From that moment, {owner} {label} {verb} to {b} on average.",
        "rose": "rose", "fell": "fell",
    },
    "zh": {
        "scores": "照原样重踢时最常见的终场比分是{a}，做出改变后是{b}。",
        "scores_same": "有没有这一改变，重踢最常见的终场比分都是{a}。",
        "stat": "从这时起，{team}的{label}平均从{a}{verb}到{b}。",
        "stat_fan": "从这时起，{team}的{label}平均{verb}到{b}。",
        "rose": "上升", "fell": "下降",
    },
    "es": {
        "scores": "Tal como se jugó, el resultado final más repetido fue {a}; con el cambio, {b}.",
        "scores_same": "El resultado final más repetido fue {a} con y sin el cambio.",
        "stat": "Desde ese momento, {label} de {team} {verb} de {a} a {b} de media.",
        "stat_fan": "Desde ese momento, {label} de {team} {verb} a {b} de media.",
        "rose": "subió", "fell": "bajó", "rose_pl": "subieron", "fell_pl": "bajaron",
    },
}

# Words for the What-if numbers that are not match stats (Bx10). A number about one of them must
# sit in a sentence that names it, as a stat's number must name the stat.
# Words that give a card its colour (#261): a straight red written as a booking, or a yellow as a sending-off,
# is caught against the cards a sentence cites. "Ten men" is checked against the red cards elsewhere.
CARD_WORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {"yellow": ("yellow", "booked", "booking", "cautioned"),
           "red": ("red card", "sent off", "sending off", "sending-off", "dismissed", "dismissal")},
    "zh": {"yellow": ("黄牌", "警告"), "red": ("红牌", "罚下", "罚出场")},
    "es": {"yellow": ("amarilla", "amonestado", "amonestada", "amonestación"),
           "red": ("tarjeta roja", "roja directa", "expulsado", "expulsada", "expulsión")},
}


REPLAY_NAMES: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {"goals": ("goal", "goals"), "scored_pct": ("scored", "score at least"),
           "cards": ("card", "cards", "booking", "bookings"), "red_cards": ("red card", "red cards", "sent off"),
           "score_share": ("score", "scores", "scoreline", "result")},
    "zh": {"goals": ("进球",), "scored_pct": ("进球", "破门"), "cards": ("牌",), "red_cards": ("红牌", "罚下"),
           "score_share": ("比分",)},
    "es": {"goals": ("gol", "goles"), "scored_pct": ("marcó", "marcaron", "anotó", "anotaron"),
           "cards": ("tarjeta", "tarjetas"), "red_cards": ("tarjeta roja", "tarjetas rojas", "expulsión"),
           "score_share": ("resultado", "resultados", "marcador")},
}


def replay_names(lang: str) -> dict[str, frozenset[str]]:
    """Lower-cased words for the What-if-only numbers, each with the numbers it could mean."""
    names: dict[str, set[str]] = {}
    for table in (REPLAY_NAMES["en"], REPLAY_NAMES.get(lang, {})):
        for metric, words in table.items():
            for w in words:
                names.setdefault(w, set()).add(metric)
    return {w: frozenset(ms) for w, ms in names.items()}
