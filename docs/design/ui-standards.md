# Pivot UI standards (C11)

> **中文摘要（给人看）：** 这份文件是全站界面的统一标准，赛前、赛中、赛后和其他页面都按它做。它写得很细，让 AI 不看任何别的资料也能照着做。最要紧的几条：
> - 黄色只给 AI（转折点、核对过的数字、"假如"的结果）；
> - 两队的颜色只来自比赛数据；
> - 不用全大写小标签、中间点串、链接后的 "→"、没有意义的编号；
> - 全页只有打开的转折点那一块是浮起来的；
> - 每次改动都要过 web-design-guidelines 检查，附 1440 宽的英文和中文前后截图；
> - 公共的样式只由 ui-overhaul 改，要改先在 #288 说。
>
> 分工见第 9 节。

Status: written 2026-10-27, after C11 1/3 (#292) merged. Applies to every page of `apps/web`.
Owner: the ui-overhaul session (momomojun's side). Questions go to issue #288.

Related:
- `docs/design/c11-design-plan.md`: why it looks like this, the approved prototype, the five reference sites;
- `docs/design/ui-research-2026-10-26.md`: what FotMob, Sofascore and the Premier League site do, and our data inventory;
- `docs/design/ui-audit-1025.md`: the earlier page-by-page bug list.

---

## 1. Goal and quality bar

- **Bar:** the *award-winning sites showcased on* Awwwards (Site of the Day / Month, Developer Award, Honorable Mention) and SiteInspire. It is **not** the look of awwwards.com or siteinspire.com themselves.
- **What we are:** a football **match tool** people use: look up a score, read why a match turned, replay it, change one decision. We are not a marketing landing page, so:
  - no full-screen hero images;
  - no "Enter" splash;
  - no scroll-jacking;
  - no 3D for decoration.
- **Who judges:** Microsoft × Premier League, plus a 2-minute demo video. "User Experience & Presentation" is 20 % of the score.
  - Premier League match-centre conventions must feel familiar: a sticky score card, tabs, a mirrored momentum chart with goal markers, grouped stats tables.
  - **Our memorable part** is the AI **turning points** (verified explanations) and the **What-if** replay. Spend the boldness there; keep everything else quiet.
- **Desktop only for now.** Design at **1440 × 900**. Don't break narrow screens badly, but don't spend time on them.
- **Fictional clubs and players only.** Never use real club names, crests, kits or Premier League marks, in the UI or in committed screenshots.

## 2. Skills to use (install once, then use on every change)

```bash
npx skills add anthropics/skills@frontend-design -g -y
npx skills add vercel-labs/agent-skills@web-design-guidelines -g -y
```

- **frontend-design** (Skill tool name `frontend-design`): use it for *direction and self-critique*.
  1. Load it before you restyle a page.
  2. Check your plan against its list of "generic page" tells: tracked all-caps eyebrows, `A · B · C` meta strings, broadsheet hairlines with slab type, identical boxed cards, "→" on links, and a cream / near-black + single acid accent.
  3. After building, screenshot the page and remove one thing ("look in the mirror and remove one accessory").
- **web-design-guidelines** (Skill tool name `web-design-guidelines`): use it to *review every component you changed* before opening a PR.
  1. It fetches its rules from <https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md> (WebFetch).
  2. Run it on the files you touched.
  3. Fix what matters for a desktop demo: focus visibility, contrast, real buttons and links, hover and active states, reduced motion, tabular numbers, truncation, aria labels, heading order.
  4. List anything you leave in the PR body.

## 3. The five references (what to borrow, what not to)

Award status was checked on each site's Awwwards / SiteInspire page.

| Site | Where it won | Borrow | Do NOT borrow |
|---|---|---|---|
| [World Cup — The Immortals](https://theimmortals.world/) | Awwwards Honorable Mention, 2026-08 | One moment at a time on one timeline, neighbours peeking; small muted sentence-case **label over a big value** ("Host / South Korea & Japan"); tight-tracked sentence-case headlines; light grey stage so the photos' kit colours carry | The 3D trophy, full-screen photos, scroll-driven carousel |
| [The Last Tango](https://www.thelasttango.com/) | Awwwards Honorable Mention, 2026-09 | **Data is the image** (goals become point clouds); one gold disc is the only call to action; **one** orchestrated reveal | The point-cloud 3D, the ornate serif and flourishes, the "Enter" gate, the near-black page |
| [No Football Colors](https://nofootballcolors.com/) | Awwwards Honorable Mention, 2026-05 | Neutral chrome, so **all colour comes from the content**; a condensed heavy face as football's voice | ALL-CAPS headlines, boxed black-bordered buttons, photo heroes |
| [&friends](https://andfriends.soccer/) | SiteInspire, Sports | One loud signal colour on black text; pill / sticker shapes as signals | The collage, stickers everywhere, the ticker, the volume |
| [FieldRank](https://www.fieldrank.run/) | Awwwards *nominee*, Data Visualisation (not an award; chosen as the one working sports-data tool) | Quiet white panels on a grey page; comfortable table rhythm; tabular numbers; "#23 → #2" deltas | Its tracked all-caps monospace labels and its numbered 01/02/03 cards |

## 4. Tokens (source of truth: `apps/web/src/styles/tokens.css`; never hard-code colours)

### Colour roles

| Token | Light | Dark | Role |
|---|---|---|---|
| `--pv-paper` | `#ECEEF1` | `#0F1114` | Page ("stand" grey) |
| `--pv-sheet` | `#FFFFFF` | `#181B20` | Panels |
| `--pv-sunk` | `#F5F6F8` | `#20242A` | Wells inside a panel; resting chips and toggles |
| `--pv-ink` | `#121418` | `#F1F2F4` | Text; **selected state** (picked chip, picked tab underline, primary button) |
| `--pv-ink-2` | `#565D6B` | `#A3A9B5` | Secondary text (6.0 : 1 on paper) |
| `--pv-hair` | `#D8DCE2` | `#2C3139` | Hairlines, chip borders |
| `--pv-focus` | `#1F5FFF` | `#7FA6FF` | Keyboard focus ring only |
| `--pv-gold` | `#FFCC1F` | same | **Pivot yellow: AI only.** Turning-point discs, the open pivot's top edge, the checked-number highlighter, the verified stamp, the What-if result |
| `--pv-gold-soft` | `#FFF3C4` | `#3A3215` | The selected pivot card; highlighted feed row |
| `--pv-red` | `#C8102E` | `#E0384F` | LIVE dot and errors only (never decoration, never a minute) |
| `--pv-home` / `--pv-away` | from data | lightened from data | **Kit colours.** `KitColours` sets `--pv-home-kit` / `--pv-away-kit` from `teams.home.color` / `teams.away.color`. Currently HBC `#1E6B45`, ROV `#4A1D57`. Use them only to say "this is that team": score band halves, momentum areas, pitch dots, stat bars |
| `--pv-bar` | `#16181D` | `#0A0B0D` | Site bar, tooltips, the scoreboard plate |

Rules:
- Yellow appears **only** where the AI found or checked something. A user's selection is ink, never yellow.
- Never write `#1C2C6E`, `red`, `blue`, or a team hex in a component. Use `var(--pv-home)` / `var(--pv-away)`.
- The score band uses the raw kit colours (`--pv-home-kit`) in both themes, with white text.

### Type

- **Big Shoulders Display** (`--pv-display`, weights 700/800/900): numbers and the few big headings, i.e. the score, minutes (`50′`), pivot numbers, page `h1`, "What if…".
- **Hanken Grotesk** (`--pv-body`; `--pv-label` is the same face): everything people read, including labels, buttons and tables.
- **Noto Sans SC**: Chinese. Chinese headlines use `--pv-body` at weight 700, **never the condensed face** (see the `:lang(zh)` block in `base.css`).
- Scale (px): 12 · 14 · 16 (body) · 18 · 24 (section h2) · 36 · 48 (page h1) · 72. The tokens are `--pv-fs-xs` … `--pv-fs-4xl`. Body line-height is 1.55.
- Reading text: 16–17 px, **max-width about 62–70ch**. Never longer than about 75 characters.
- Numbers: `font-variant-numeric: tabular-nums` (class `.num`) wherever numbers line up.
- Headings use `letter-spacing: -.01em` to `-.015em`. No positive tracking anywhere.

### Space, radii, shadow, motion

- Spacing: 4 · 8 · 12 · 16 · 24 · 32 · 48 (`--pv-s1` … `--pv-s7`). Page content is max 1280 px wide with **32 px** side gutters. Panels have 16–24 px padding.
- Radii by rank: panel `--pv-r-panel` 14 px; control `--pv-r-ctl` 8 px; pill / chip `--pv-r-pill`.
- Shadow: **only one element floats**, the open turning point (`--pv-lift`). Everything else is flat white on grey, with no outline borders on panels.
- Motion:
  - **one** orchestrated reveal per page at most: the momentum line draws from kick-off to full time, then the pins drop in.
  - Hover and press feedback may use 150 ms colour transitions.
  - No fade-up on every section.
  - Everything is wrapped in `@media (prefers-reduced-motion: no-preference)` or disabled under `reduce`. Smooth scrolling goes through `scrollBehavior()` from `data/motion.ts`.
- Dark mode is the same system: the tokens switch, and the kit colours are lightened by `color-mix`. Check that white text on a lightened kit colour is still AA. Use `--pv-on-team` (dark ink at night) for text on kit fills.

## 5. Do / don't

Do:
- **Sentence case everywhere**: "Why it turned", "Team stats", "Swung to Harbour City".
- Minutes always with the prime: `63′`, `45+2′`. Convert `clock_label` with `.replace(/'/g, "′")`.
- Label over value for facts: a small muted `dt` over a bold `dd` (see `.open-facts`).
- Sentences instead of chains: "Verified: 12 numbers, 5 events checked"; "Goal: Rasfelrassen"; "X passes to Y".
- Real `<button>` for actions and `<a>`/`<Link>` for navigation. One `h1` per page. A visible focus ring (the global `:focus-visible` rule; don't remove it).
- Put new strings in `apps/web/src/i18n/messages/{en,zh,es}.ts`, all three at once. `hardcoded.test.ts` fails on literal English in JSX.

Don't:
- ALL-CAPS labels, tracked-out eyebrows, or `text-transform: uppercase`.
- `A · B · C` meta strings (a single separator inside a sentence is fine; a chain of three is not).
- "→" appended to links or buttons. Direction arrows that mean "attacking this way" are fine.
- Numbered markers (1, 2, 3 badges) unless the content is a real sequence. Pivot numbers are fine, because pivots are ordered in time and drawn on the chart.
- Identical boxed cards in a grid. Vary rank: hero panel, quiet list, table.
- Yellow for anything the user picked, or for decoration.
- New colours, fonts, radii or shadows in a page's CSS file.

## 6. Shared building blocks (build from these)

Files under `apps/web/src`. Owner: ui-overhaul; ask on #288 before changing them.

| Block | Where | Use |
|---|---|---|
| `Card` | `components/Card.tsx` → `.card` | A white panel with a sentence heading and an optional note on the right. `<Card title={t("board.stats")} note="0′–90+6′">…</Card>` |
| `Button` | `components/Button.tsx` → `.btn`, `.btn.pri`, `.btn.ghost` | `variant="primary"` = ink fill (one per view); default = white with a hairline; ghost = underlined text. `<Button variant="primary" onClick={run}>{t("whatif.run")}</Button>`. For a link styled as a button, use `className="btn"` |
| `Segmented` | `components/Segmented.tsx` → `.seg` | A toggle group: grey well, white selected pill. Props `label`, `options: {value, label, lang?}[]`, `value`, `onChange`. Use it for scope switches (match / first half), picture switches, fan / analyst |
| `Stamp` | `components/Stamp.tsx` → `.stamp.{ok,warn,bad,live,line}` | A small pill. `ok` is yellow (AI verified) only; `line` is neutral |
| `Kicker` | `components/Kicker.tsx` → `.kicker` | A quiet muted line of context. Use rarely; never repeat what the header already says |
| Chip | `.chip` (button) | What-if choices and filters. Rest: white with a hairline; `aria-pressed="true"`: ink |
| Evidence pill | `.ev` (button) | An event id after a sentence. Rest: sunk grey; `.on`: ink |
| Pivot disc | `.badge` (span) | Yellow disc with the pivot number in Big Shoulders 900; ink with a yellow number when selected |
| Facts | `<dl className="open-facts"><div><dt>…</dt><dd>…</dd></div></dl>` | Label over value |
| Kit colours | `components/KitColours.tsx` (mounted in `App.tsx`) | Nothing to do; just use `var(--pv-home)` / `var(--pv-away)` |
| Source tooltip | `components/Sourced.tsx` | Wrap a checked number: `<Sourced claim={c} className="hl">53% to 76%</Sourced>`. Hover or focus shows its stat |
| Motion helper | `data/motion.ts` | `scrollIntoView({ behavior: scrollBehavior() })`; `n.toLocaleString(numberLocale())` |
| Team stats | `components/TeamStats.tsx` (#304) | `const report = useTeamStats(matchId, upTo)` then `<TeamStats state={report} />` |
| Match pictures | `components/MatchPictures.tsx` (#304) | `<MatchPictures upTo={upTo} />`: the switch over the four pictures |
| Viz | `components/viz/*` (#287) | `ShotMap`, `Heatmap`, `PassNetwork`, `AveragePositions`, each fed by its hook in `data/viz.ts` inside `<VizBox state={…}>` |

Header and tabs (`ScoreHeader`, `MatchTabs`, `TopBar`, `Playback`) are the ui-overhaul session's; pages render under them.

## 7. Content rules

- **Fan vs analyst** (`prefs.audience`):
  - Fans get plain words: `stats.fan.*`, `ts.fan.*`.
  - Evidence ids are hidden behind one "Sources" tap per sentence (`.ev-more`).
  - Fans see no raw xG in headline places; the team-stats table shows the 10 plain stats.
  - Analysts get everything.
- **♥ team / ★ player** (`prefs.focus_team`, `prefs.focus_player_id`):
  - the ♥ team's numbers and swings are marked in its kit colour;
  - the ★ player's evidence chips and feed rows get a star, and their name gets the highlighter.
- **Languages:**
  - EN / 中文 / ES via `?lang=` or the toggle.
  - AI text may arrive in English first; show `.lang-note` instead of hiding it.
  - Chinese: Noto Sans SC; headings are not in the condensed face; no extra letter-spacing.
- **Honesty:**
  - What-if is "simulated, not a prediction".
  - Pre-match context effects are "shown for context; not applied in play" (`pre.factorsNote`).
  - A pivot without the AI's text says "Auto summary".

## 8. Data you can use on the live and post-match tabs

All through `useMatch()` (`data/match.tsx`, type `MatchView` in `data/view.tsx`) unless named:

| Data | From | Notes |
|---|---|---|
| Score, clock, status, periods | `match` | `useClock().minute(m)` / `.at(t)` / `.span([from, to])` for display |
| Teams, colours, squads, sheets | `teams`, `squads`, `sheets` | `teams[side].color` feeds the kit colours |
| Events | `events`, `eventById(id)` | `describe(e, playerName, t)` in `EventFeed.tsx` gives the sentence |
| Momentum per minute | `metrics` (`GET /api/matches/{id}/timeline`) | `MomentumChart` |
| Turning points | `pivots` (`GET /api/matches/{id}/pivots`), `pivotDetail(id)` for window and frames | Only `confirmed` / `degraded` are shown as moments |
| What-if | `useScenarioSource()` (`pages/WhatIfLab.tsx`), `WhatIfInline` in `Moments.tsx`; `GET /api/pivots/{id}/scenarios` | Lives **inside** the open pivot on post-match |
| Key moments | `keyMoments(events, finished)` in `data/keyMoments.ts` | Goals, reds, penalties, VAR |
| Set pieces and shots clips | `SetPiecesAndShots` (`components/SetPieces.tsx`) | |
| Team stats, 23 MET grouped | `GET /api/matches/{id}/stats` (#279), `useTeamStats` | Groups: attack, possession, defence, shape, physical; scopes: match, first_half, second_half; `?up_to=` for a replay |
| Shot map / heatmaps / pass network / average positions | `GET /api/matches/{id}/shots \| heatmaps \| pass-network \| positions` (#287), hooks in `data/viz.ts` | `upTo` follows the replay |
| Player stats | `GET /api/matches/{id}/players/stats?player=` (#226), `PlayerCard` | Shown for the ★ player |
| Pre-match context and plans | `preMatch` (#283, #290; coach tactics in #289) | Pre-match tab |
| AI work log | `GET /api/matches/{id}/traces`, `/trace` page | |

### Intended layout: live tab (implemented in #304)

```
[ sticky: site bar · kit-clash score band · replay bar ]   [ tab rail: Pre-match  Live  Post-match ]
┌ On the pitch (PitchBoard, 2/3) ─────────────┐ ┌ Match stats (5 key, MET values) ┐
└─────────────────────────────────────────────┘ └─────────────────────────────────┘
┌ Events (feed, sentences) ───────────────────┐ ┌ Line-ups ───────────────────────┐
Shots, heat and passing  (h2)
┌ [Shot map | Heatmap | Pass network | Average positions]  [team]  picture ≤ 820 px ┐
Team stats  (h2)                                    [Whole match | First half | Second half]
┌ Attack ───────────┐ ┌ Possession ────────┐ ┌ Defence ───────────┐
│ 11  Shots      14 │ │ 57%  Possession 43%│ │ 13 Tackles won  10 │   (Shape, Physical below)
```

### Intended layout: post-match tab (approved prototype; Carry3 decides the final order in #299)

Key elements to keep: yellow only for AI; pivot markers on the momentum chart linked to the pivots; What-if **inside** the open pivot; one floating panel; none of the tells in section 5.

```
The 3 moments that changed the course of this match          [Start demo]
one-line lede (≤ 62ch)
┌ Momentum (hero, full width) ─────────────────────────────────────────────┐
│        ①50′            ②68′             ③83′    ← yellow discs           │
│  ▲▲ home kit ▲▲  ░░ yellow window of the open pivot ░░                   │
│ ──⚽───────────────────────────────────────────────────────────────────── │
│  ▼▼ away kit ▼▼                                                          │
│ ① 50′ headline / cause / Swung to …  │ ② …  │ ③ …   (pivot list)          │
└──────────────────────────────────────────────────────────────────────────┘
┏ open turning point (the only floating panel, yellow top edge) ━━━━━━━━━━━┓
┃ ① 50′  Headline                                     [Previous] [Next]    ┃
┃ Set off by / Swung to / Checked                              Full detail ┃
┃ Why it turned (17px, 62ch)                 │ the pitch at that moment    ┃
┃ What if…  [chip] [chip] [chip]   → Run simulation                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
Key moments (quiet list) · Set pieces & shots · AI work log (one line)
```
Prototype code: branch `b/C-ui-overhaul` (commits `f5b654d`, `faccd8e`) and draft #300. Its screenshots are in `docs/screenshots/c11-prototype/` and `docs/screenshots/c11/pr3a/` on that branch.

### Pre-match: the coach's plan when the two teams differ (#289)

- Show the two plans side by side as a **comparison**: one row per setting (pressing, line height, tempo, width, attack focus, set pieces).
- Home value left, away right, the setting's name between them.
- Mark where they **differ**: e.g. bold both values and a small "different" tag, or a kit-coloured meter per side. Where they are the same, show the row quietly.
- Style words (defensive / balanced / attacking) as plain text, not coloured badges.

## 9. File ownership (to avoid conflicts)

| Who | Files |
|---|---|
| **ui-overhaul** (momomojun's Claude) | `styles/tokens.css`; shared parts of `styles/base.css`; `index.html`; `KitColours`, `ScoreHeader`, `MatchTabs`, `TopBar`, `Segmented`, `Card`, `Stamp`, `Button`, `Kicker`, `Sourced`, `FocusPickers`, `data/motion.ts`; live tab (`LiveTab`, `MatchStats`, `TeamStats`, `MatchPictures`, `EventFeed`, `components/viz/*`, `viz.css`); `PivotDetail`, `WhatIfLab`, `WhatIf.tsx` (result panel), `AgentTraces`, `traces.css` |
| **Carry3** | Pre-match (`PreMatchTab`, `PreMatch`, `TeamTactics`, `Lineups`, `prematch.css`); post-match (`PostMatchTab`, `Moments`, `PivotList`, `WhyItTurned`, `MomentumChart`, `KeyMoments`, `SetPieces`, `post.css`, the outer What-if block on the post tab); `Pitch`, `PitchBoard`, `ClipPlayer`, `Playback` / replay bar, `pitch-board.css`, `setpieces.css` |
| Data files nobody restyles | `sim/season.py`, `sim/tactics.py`, `sims.py`, API and contracts |

- A shared block is changed only by its owner. Ask on #288, and the owner changes it within the hour.
- A page's CSS uses tokens and shared classes and is scoped to its page (e.g. every rule in `post.css` under `.post`).
- i18n files are shared: **add** keys, don't reorder; to change an existing shared key, say so on #288.

## 10. Process

1. `git fetch origin` and start from (or rebase on) `origin/main` before each PR. Never push to main.
2. Keep PRs small: one tab or one layer per PR. Stacked PRs say "sits on #N" at the top.
3. Before opening: `pnpm --filter web lint`, `test`, `build` all green.
   - On a machine whose Node reports a Chinese locale (`node -e "console.log(navigator.language)"` prints `zh-CN`), about 15 tests render Chinese and fail. That is not a real failure: run them with `navigator` set to `en-US`.
4. Run the web-design-guidelines review on the changed files and fix what matters.
5. Screenshots at **1440 × 900**, before and after, **EN and 中文**, as WebP under `docs/screenshots/<task>/`, linked in the PR body. Fictional data only.
6. The PR body is in **plain Chinese** (team rule) and ends with the Claude Code line. Commits end with the Co-Authored-By line.
7. The reviewer is the other person. The coordinator session merges in order once CI is green.
8. Deadline: everything merged by **2026-10-27 12:00 PT**. The merge freeze is 15:00 PT; the demo video is recorded after.

## 11. Acceptance checklist (per tab or page)

- [ ] At 1440 × 900 the first screen shows the tab's main thing (post: momentum and pivots; live: pitch and stats; pre: the tale of the tape).
- [ ] No ALL-CAPS label, no `·` chain, no "→" on a link, no meaningless numbering, no grid of identical boxed cards.
- [ ] Yellow appears only on AI things; team colours come only from `--pv-home` / `--pv-away`.
- [ ] Exactly one `h1`; section headings are `h2` in sentence case.
- [ ] Every action is a button or link, reachable by Tab with a visible focus ring; SVG controls have `role="button"`, an `aria-label`, and Enter / Space handling.
- [ ] Text contrast is AA in light and dark (check white on lightened kit colours).
- [ ] Reduced motion: no reveal, no smooth scroll.
- [ ] Minutes show `′`; numbers are tabular; reading text stays under about 75 characters.
- [ ] EN, 中文 and ES all render with no English fallback in labels and no overflow at 1440; Chinese headings are not in the condensed face.
- [ ] Fan and analyst both make sense; ♥ team and ★ player still mark their things.
- [ ] lint / test / build green; before/after screenshots in EN and zh in the PR.
