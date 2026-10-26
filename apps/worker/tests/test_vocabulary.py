import re
from pathlib import Path
from typing import get_args

from pivot_core.domain import STAT_UNITS, StatMetric
from pivot_worker import vocabulary as v

STYLE_GUIDE = Path(__file__).parents[1] / "prompts" / "style_guide.md"


def test_vocabulary_matches_the_contract_one_to_one():
    assert tuple(v.STAT_TERMS) == get_args(StatMetric)
    assert set(v.STAT_TERMS) == set(STAT_UNITS)
    assert len(v.STAT_TERMS) == 23


def test_every_term_is_filled_in_and_every_unit_has_a_suffix():
    for metric, term in v.STAT_TERMS.items():
        assert term.metric == metric
        assert term.label and term.fan_label and term.definition and term.higher_means
        assert STAT_UNITS[metric] in v.UNIT_SUFFIX


def test_fan_labels_avoid_jargon():
    for term in v.STAT_TERMS.values():
        assert not any(j.lower() in term.fan_label.lower() for j in v.JARGON), term.metric


def test_word_lists_do_not_overlap():
    lists = [set(v.UP_WORDS), set(v.DOWN_WORDS), set(v.SIGNIFICANCE_WORDS), set(v.BANNED_TERMS)]
    for i, a in enumerate(lists):
        for b in lists[i + 1:]:
            assert not a & b


def test_vocabulary_markdown_lists_every_metric():
    for audience in ("analyst", "fan"):
        table = v.vocabulary_markdown(audience)
        assert all(f"`{m}`" in table for m in v.STAT_TERMS)
    assert "quality of chances" in v.vocabulary_markdown("fan")


def test_style_guide_has_five_good_and_five_bad_examples():
    text = STYLE_GUIDE.read_text()
    assert len(re.findall(r"^### Good \d", text, re.M)) == 5
    assert len(re.findall(r"^### Bad \d", text, re.M)) == 5


def test_style_guide_lists_every_banned_term():
    text = STYLE_GUIDE.read_text()
    banned_line = text.split("Currently:", 1)[1].split("\n- ", 1)[0]
    listed = {w.strip(" .\n") for w in banned_line.replace("\n", " ").split(",")}
    assert listed == set(v.BANNED_TERMS)
