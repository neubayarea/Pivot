# Explanation style guide (English)

How the Explainer and the Comparator write, and what the Verifier holds them to. The stat
vocabulary and every word list named here live in `apps/worker/src/pivot_worker/vocabulary.py`;
`tests/test_vocabulary.py` keeps this file and that module in step.

## The job

A pivot card answers one question: **why did the match turn here?** Write it the way a calm
match analyst would say it on air: what changed, who made it change, and the evidence.

## Shape

- **Headline**: at most 8 words, no numbers (neither digits nor words like "two"), no team score. Name the change, not the outcome
  ("Rovers' press flips the midfield", not "Rovers lead 2-1").
- **Sentences**: 1 to 3, each at most 30 words, one idea per sentence.
- **Order**: what happened (the trigger) → what changed in the numbers → what it led to.
- **Evidence**: every sentence cites 1 to 4 `evidence_ids`, all from 8 minutes before the
  pivot to 5 minutes after it.
- **Numbers**: every number in `text` has a matching entry in `claims`, with a `stat_ref`
  from the vocabulary. No number without a claim, no claim without the number in the text.
  The screen shows the recomputed value, so round the way you would say it on air.
  Match minutes written as `61'` are not claims.

## Numbers and units

| unit | write | example |
|---|---|---|
| count | whole number | "4 shots" |
| pct | whole or one decimal, with `%` | "pass accuracy fell to 71%" |
| xg | two decimals, with `xG` (analyst) or as "chances worth about half a goal" (fan) | "0.84 xG" |
| index | two decimals, only for `momentum_avg` | "momentum of 0.32" |
| m | whole metres | "a line 6 m higher" |
| km | one decimal | "11.2 km covered" |

Compare two windows of the same length when you say something rose or fell, and put both
values in `claims` (same metric, same team).

## Words

- **Direction words** (rose, fell, dropped, climbed, …; see `UP_WORDS` and `DOWN_WORDS`) are
  checked against the sign of the change between your two claims. If you have no pair of
  claims, do not use them.
- **Significance words** (significant, clearly, decisive, proven, conclusive; `SIGNIFICANCE_WORDS`)
  only appear in what-if comparisons whose confidence intervals do not overlap. Never in a pivot card.
- **Banned terms** (`BANNED_TERMS`): betting language, absolutes the numbers cannot support,
  and blame. Currently: bet, betting, odds, wager, punter, accumulator, bookmaker, always,
  never, guaranteed, certain, certainly, definitely, undoubtedly, 100%, single-handedly,
  choked, disgrace, pathetic, useless.
- Talk about decisions and patterns, not character. "The switch left the left flank open"
  is fine; "the full-back was lazy" is not.
- Everyone in Pivot is fictional. Use the names from the match data only; never mention real
  clubs, players, competitions or brands.
- Analyst audience may use the vocabulary labels (xG, line height, press distance). The fan
  audience uses the `fan_label` wording and none of the `JARGON` list.

## Good examples

### Good 1

> **Headline**: Okafor's arrival flips the left flank

1. "Okafor came on at 61' and Rovers' final-third passes rose from 3 to 9 in the next five minutes."
   - evidence: `m063-s01042` (substitution), `m063-s01077` (pass)
   - claims: `passes_final_third` home (56, 61) = 3; `passes_final_third` home (61, 66) = 9

Why it works: trigger first, a pair of claims backs "rose", both windows are 5 minutes.

### Good 2

1. "After the red card Harbour's line dropped from 41 m to 33 m, inviting Rovers onto them."
   - evidence: `m063-s00811` (card)
   - claims: `line_height_m` away (31, 36) = 41; `line_height_m` away (36, 41) = 33

Why it works: one idea, the direction word matches the sign, the effect is described as a pattern.

### Good 3

1. "Rovers pressed higher and won the ball back 5 times in the middle third."
   - evidence: `m063-s00930`, `m063-s00944`, `m063-s00951`
   - claims: `tackles_won` home (38, 43) = 5

Why it works: a single number with its claim; "higher" is a description, not a change claim on a number.

### Good 4

1. "Harbour created 0.84 xG in eight minutes, more than in the whole first half."
   - evidence: `m063-s01120` (shot), `m063-s01133` (shot)
   - claims: `xg` away (55, 63) = 0.84; `xg` away (0, 45) = 0.61

Why it works: the comparison is explicit and both sides of it are claims.

### Good 5 (fan audience)

> **Headline**: The goal that woke Harbour up

1. "Once Mensah scored, Harbour suddenly had most of the ball and kept Rovers pinned back."
   - evidence: `m063-s01201` (shot, goal)
   - claims: none

Why it works: no jargon, no number in the text (so no claim needed), the trigger is named.

## Bad examples

### Bad 1

1. "Rovers had 72% possession after the switch." — claims: none

Why it fails: a number without a claim (`number_mismatch`).

### Bad 2

> **Headline**: Rovers score 2 in 5 minutes

Why it fails: digits in the headline. "Two goals in three minutes" fails the same way:
numbers written as words count too.

### Bad 3

1. "Pass accuracy rose to 68%." — claims: `pass_accuracy_pct` home (56, 61) = 74; `pass_accuracy_pct` home (61, 66) = 68

Why it fails: the numbers fell, the text says "rose" (`direction_mismatch`).

### Bad 4

1. "Harbour were definitely the better side and always looked like scoring, so the odds shifted their way."

Why it fails: absolutes and betting language (`banned_term`), no evidence, no claim for "better".

### Bad 5

1. "The substitution was a significant turning point that changed everything about how both teams approached the rest of the second half in every area of the pitch."

Why it fails: more than 30 words (`too_long`), significance wording in a pivot card
(`significance_unsupported`), and nothing specific to check.
