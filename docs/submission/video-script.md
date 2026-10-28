# Pivot: demo video script

Length **1:57** (limit 2:00). Narration: **253 words**, about 1:48 at 140 words a minute. The rest is room for clicks. Captions: [video-captions.srt](video-captions.srt), with the same timings as below.

Demo match: **S2026-27-TES-VAN**, **Tessmouth United 4–3 Vantry Town** (Freeland League, matchday 27, a fixture of the simulated season). The site opens it by default once #381 is deployed: https://pivot.in-stacks.com/

Every number below was read on **2026-10-27, about 17:00 PT**, from the site run locally against the live site's own stores (the same Cosmos DB results and Blob match library), before #381 was deployed. After the deploy, run the [checks](#check-the-live-site-10-minutes-before) against the live site to confirm them again.

## Tabs

The match page has six tabs, each with its own link `?tab=`:

| Tab | `?tab=` | Used in |
|---|---|---|
| **Overview** 概况 | `overview` | Shots 1–4, 6b |
| **What if** 假如 | `whatif` | Shot 5 |
| **Replay** 回放 | `replay` | Shot 6a. While a replay is playing, this tab is labelled **Live**. |
| **Stats** 数据 | `stats` | Shot 4 |
| **Line-ups** 阵容 | `lineups` | Shot 7b |
| **Preview** 赛前 | `preview` | Shot 7a |

Viewer settings can go in the link too: `mode=fan|analyst`, `player=<id>|none`, `lang=en|zh|es`. D. Sahaltessen is `h11`. **Do not rely on `team=` in a link** for this match: in a fresh window `team=home` is dropped, and `team=none` does not clear a team saved by an earlier take (see [what we saw](#what-we-saw-2026-10-27)). Pick the team on camera with **♥** instead. On camera, change the settings with the top-bar controls: **Fan / Analyst**, **♥ Team**, **★ Player**, **EN / 中文 / ES**, or with the **♡** next to a team name in the score band and **☆ Follow** next to a player.

Section names change with the viewing mode. Analyst says "Form in detail" and "The coach's plan". Fan says "How they have been playing" and "How each coach wants to play". Shots 1–2 are in analyst mode and shots 3–7 in fan mode (shot 5 switches to Analyst for the details and back).

## Shot list

| # | Time | Picture: what to click | Narration (words) | Judging point |
|---|---|---|---|---|
| 1 | 0:00–0:12 | **Overview.** Open the [start link](#links). Score band: **Tessmouth United 4–3 Vantry Town**, "Sahaltessen 37′, 54′, 75′" and "Quinsenlier 67′", "Sadoseno 17′, 80′" and "Beltoov 26′". Scroll slowly to "The 3 moments that changed the course of this match" and the momentum chart with markers **① 12′ ② 50′ ③ 88′**. The header folds into the slim bar as you scroll. | Tessmouth United four, Vantry Town three: one simulated match. Pivot finds the moments that turned it, explains why, and lets you replay it with one thing changed. **(27)** | The problem and the one-line pitch |
| 2 | 0:12–0:31 | **Turning point ①, analyst view.** Card **① 12′ "Vantry Town gains control with sharp attack"** is open under the list (Verified ✓, "Set off by 17′ Goal: Z. Sadoseno", "Swung to Vantry Town", "Checked 6 numbers, 5 events"). Under **Why it turned**, hover the underlined **4 to 14** in the second sentence: the tooltip shows *Final-third passes · Vantry Town · 7′–11′ · 4*. Click evidence chip **#329** at the end of the third sentence: the mini pitch shows "17′ Goal: Z. Sadoseno". Hold 1 s on "Judged, written and checked by the AI. Claims checked: 6. Evidence: 5." | Pivot found three turning points. Take the twelfth minute, when Vantry took over. A Judge agent confirms it really swung the game. An Explainer writes why. A Verifier recomputes every number from the event log: Vantry's passes into the final third went from four to fourteen. **(46)** | Football insight, trust in the AI |
| 3 | 0:31–0:45 | **Switch to fan and pick a team.** Click **Fan** in the top bar, then **♥ Team → Tessmouth United** (or the **♡** next to "Tessmouth United" in the score band). The overview switches to the fan version: "How the match was decided", then "How Tessmouth United did · 4–3". In "The 3 moments…" list the first row now reads **"Tessmouth United lose control after Vantry's goal"** with "Swung against you". Click that row: the turning point opens on its own page with the same headline, "Verified: 8 numbers, 1 events checked", and the text takes Tessmouth's side ("Meanwhile, Tessmouth United's share of the ball and presence in the attacking third dropped sharply."). Click **中文** (headline "Vantry 进球后 Tessmouth 失控"), then **ES** ("Tessmouth United pierde control tras gol de Vantry"), then back to **EN**. Click **← Live board**. | Now switch to Fan and pick Tessmouth. Same moment, same checked facts, told from your side: "Tessmouth United lose control after Vantry's goal." In Chinese or Spanish, too. **(28)** | Personalisation (rule 4.1): audience, team, language |
| 4 | 0:45–0:57 | **Follow a player.** On Overview, in "How Tessmouth United did": "Best player: D. Sahaltessen, rated 9.9". Press **☆ Follow** under his rating; "★ Following: D. Sahaltessen" appears under the score. Click the **Stats** tab. **Player spotlight**: "Tessmouth United, Forward", rating **9.9** (Team average 6.9), Goals **3**, Shots **9**, Top speed **35** km/h, Sprints **12**. Click **Heatmap**, then **Their shots**. Keep "In the turning points" below it out of frame (see [what we saw](#what-we-saw-2026-10-27)). | Follow a player. Sahaltessen scored a hat-trick, the first from the penalty spot, and is rated nine point nine. You get his shots, his heatmap and his passing. **(28)** | Personalisation (rule 4.1): followed player |
| 5 | 0:57–1:18 | **What-if.** Click the **What if** tab. **Pivot 1, 12′** and the chip **Disallow 17′ goal** are already selected. Click **Analyst** in the top bar: the fan result is one sentence and a bar, without the gap, the label or the ranges. Keep **200** runs, click **Run simulation**. Result: "Instant: simulated before", **+16pts**, "Without the 17′ goal, the chance of Tessmouth United winning rises from 34% to 50%, and the most likely score goes from 1–1 to 1–0." **Clear difference**. As played (from 17′): TES 34 % · Draw 30 % · VAN 37 %. With the change: TES 50 % · Draw 23 % · VAN 27 %. Hold 2 s on the bars, then on the 95 % ranges, TES 27–40 against 43–57, and "◆ ranges do not overlap". Click **Fan** again: a line reads "Tessmouth United’s chance of winning: 34% as played, 50% with the change." | So what if Vantry's opening penalty had been ruled out? Pivot saves the match at that minute and plays the rest two hundred times each way. Tessmouth's chance of winning rises from thirty-four to fifty percent. Those ranges don't overlap. It's a clear difference. **(44)** | Innovation, football insight |
| 6 | 1:18–1:35 | **Replay and set pieces.** (a) 1:18–1:27: open the [replay link](#links) (`from=75`). As soon as the pitch shows, pause (❚❚), click **5×** on the bar under the pitch, then play. Passes draw a line from passer to receiver and tackles flash. At 77:04 on the replay clock (the 75′ goal; the replay clock counts first-half stoppage time) Sahaltessen scores and the score goes from 3–2 to 4–2. (b) 1:27–1:35: **Overview** → **Set pieces & shots** → **Set pieces** → row **7′ TES Free kick in shooting range · G. Rosaberez · Shot**. The clip plays at 1×. It shows "In the box: TES 5 attackers, VAN 11 defenders (keeper included)", "Marking: Man-to-man, 4 of 5 attackers had a defender within 2.5 m", "Wall: 5 players" and "What happened: 7′ TES, Shot by X. Haltosais, xG 0.08". | Every match replays on the pitch, with passes, shots and tackles drawn as they happen. Set pieces too: on this free kick, five attackers faced all eleven Vantry players, with five in the wall. **(34)** | Demo, football insight |
| 7 | 1:35–1:46 | **Preview and line-ups.** (a) Click the **Preview** tab, "The build-up": Freeland League, Quayside Park, crowd 43,367. Scroll to "What comes next" (a Freeland Cup semi-final for each side, in 3 and 4 days) and "Last five at a glance": goals a game **3.4** against **1.8**. Above it, Tessmouth's last five read W W W W L and Vantry's D D D D D. (b) Click **Line-ups**: "The line-up from your side", **Tessmouth United 4-2-3-1 against Vantry Town 4-1-4-1**, "Your attack against their defence: ST 1 v 2 CB CB, Outnumbered". Scroll to "How each coach wants to play": **G. Ronotoson, Balanced** and **L. Senladoov, Balanced**. | Before kick-off: four wins in five for Tessmouth, five draws for Vantry, a cup semi-final days later, and each coach's plan. **(21)** | Completeness, football context |
| 8 | 1:46–1:57 | **End card**: a plain slide, or the match page dimmed behind text. **Pivot** · *Azure AI Foundry: models for the Judge, Explainer and Comparator agents · Azure Cosmos DB: results · Azure Blob Storage: match library* · *pivot.in-stacks.com · github.com/neubayarea/Pivot* · *All clubs, players and matches are synthetic.* | The agents run on Azure AI Foundry. Results live in Cosmos DB, matches in Blob Storage. Every club and player is synthetic. This is Pivot. **(25)** | Microsoft technology, data rules |

Total: 253 words. If it runs long, cut "It's a clear difference." from shot 5 (4 words) and let the "Clear difference" label say it.

### Which what-if to use, and why

Use **Disallow 17′ goal** at turning point ① (12′): Sadoseno's penalty that put Vantry ahead, the goal that set off the turning point shown in shots 2–3. Of the stored chips it has by far the largest effect. Each chip was replayed 200 times each way. On 10/27 the result store held these for this match, and no others:

| Turning point | Change | As played → with the change (API values) | Clear difference? |
|---|---|---|---|
| ① 12′ | **Disallow 17′ goal** (Sadoseno's penalty) | TES win 33.5 % → 50.0 %, draw 30.0 % → 23.0 %, VAN win 36.5 % → 27.0 %, most likely score 1–1 → 1–0 | yes, for TES win (27–40 against 43–57) |
| ① 12′ | Cancel 55′ substitution | TES win 40.0 % → 48.0 %, VAN win 22.0 % → 12.5 % | smaller; not used |
| ① 12′ | Move substitution to 75′ | at most 1.5 points on any outcome | no |
| ② 50′, ③ 88′ | any | not stored | — |

The page rounds these to whole percentages (34 % → 50 %). The "as played" numbers differ from chip to chip (33.5 %, 40 %, 43 % for a Tessmouth win) because each chip has its own seeds: that is the spread of 200 replays. The scenario in the video is `S2026-27-TES-VAN:sa3a52146740e` (`/api/scenarios/S2026-27-TES-VAN:sa3a52146740e`). **Do not click other chips or other turning points' what-ifs on camera.** A scenario that is not stored runs again, and that takes minutes on the 2-core server (this one took 86.3 s the first time; the result says "200 runs in 86.3 s").

Its "Why it differs" text is the template, not the model's ("Replays: Tessmouth United win more likely"; the model's text failed the check 3 times on 10/27). Because of that, the **first** Run simulation after each server restart asks the model again, which takes about 30 s and shows "Replaying… 400 of 400" meanwhile. After that it answers at once until the server restarts. So run it once in the warm-up.

### Why this order

Shots 1–2 state the problem and show the checked explanation on the only model-written, verified card: turning points ② and ③ are "Auto summary" (the template fallback), so the script never opens them. Shots 3–4 are the personalisation rule 4.1 asks for: audience, team and language, then a followed player. Shot 5 asks a question about the goal that set off turning point ①, from the picked team's side. Shot 6 shows the pitch and a set piece, and shot 7 shows what the page knows before kick-off.

Shot 3 comes before shot 4 on purpose: once a player is followed, turning point ① switches to a version written for that viewer, and on 10/27 that version was the template ("Tessmouth United lose their grip").

## Before recording

### Screen and browser

- Chrome, **incognito window**, a new one for every take: the site remembers language, viewer settings, team and match in browser storage, and the link cannot clear the team. Page area **1920 × 1080**, zoom 100 %. Record at 1920 × 1080, 30 fps.
- Hide the bookmarks bar and the Dock, close other tabs, turn on **Do Not Disturb**, mute system sounds.
- **No music**, or only music you hold a licence for. **No Premier League logos or marks** anywhere: browser tabs, desktop, end card.
- Mouse: turn on cursor highlight if your recorder has it. Hold still for half a second before each click.

### Links

| Use | Link |
|---|---|
| Start (shots 1–2) | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=overview&mode=analyst&player=none&lang=en |
| Shot 4, if you cut there (then pick ♥ Tessmouth United) | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=stats&mode=fan&player=h11&lang=en |
| Shot 5, if you cut there (then pick ♥ Tessmouth United) | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=whatif&pivot=S2026-27-TES-VAN:p11&mode=fan&player=h11&lang=en |
| Shot 6a, replay | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=replay&from=75&mode=fan&player=h11&lang=en |
| Shot 7a | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=preview&mode=fan&player=h11&lang=en |
| Shot 7b | https://pivot.in-stacks.com/?match=S2026-27-TES-VAN&tab=lineups&mode=fan&player=h11&lang=en |

Old links with `tab=pre|live|post` still work: they open Preview, Replay and Overview.

`from=` is in minutes of the replay clock, which counts stoppage time, so the second-half goals sit about 2 minutes later than their labels (the 75′ goal is at 77:04). The replay starts at 20×, so pause it first.

### Check the live site (10 minutes before)

```bash
curl -s https://pivot.in-stacks.com/api/matches | python3 -c "import json,sys;print(json.load(sys.stdin)[0]['match_id'])"
curl -s https://pivot.in-stacks.com/api/matches/S2026-27-TES-VAN | python3 -c "import json,sys;print(json.load(sys.stdin)['score'])"
curl -s https://pivot.in-stacks.com/api/matches/S2026-27-TES-VAN/pivots | python3 -c "import json,sys;[print(p['pivot_id'],p['status'],p['narrative']['headline']) for p in json.load(sys.stdin)]"
curl -s "https://pivot.in-stacks.com/api/matches/S2026-27-TES-VAN/pivots?audience=fan&team=home" | python3 -c "import json,sys;print(json.load(sys.stdin)[0]['narrative']['headline'])"
curl -s https://pivot.in-stacks.com/api/scenarios/S2026-27-TES-VAN:sa3a52146740e | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r['baseline']['home_win'],r['counterfactual']['home_win'])"
```

On 10/27 these printed:
- `S2026-27-TES-VAN` (the first match listed, the one the site opens);
- the score `home 4, away 3`;
- `p11 confirmed "Vantry Town gains control with sharp attack"`, `p53 degraded "Tessmouth United goal swings the match"` and `p91 degraded "Tessmouth United change shifts the balance"`;
- `Tessmouth United lose control after Vantry's goal`;
- `0.335 0.5`.

If anything differs, re-read the shots off the page, then change the narration and the captions together. If the last command says "not found", the what-if is no longer stored; see backup 5.

### Warm up (open each once, so nothing is written on camera)

1. The start link. Wait for the momentum chart and card ①.
2. Fan → ♥ Tessmouth United → click ① in the list. Wait until the headline reads "Tessmouth United lose control after Vantry's goal". While a version is being written, the card says "Writing the fan version. Showing the analyst version for now." Then click 中文 and ES once each.
3. ☆ Follow D. Sahaltessen → Stats → Player spotlight → Heatmap.
4. What if → Pivot 1, 12′ → Disallow 17′ goal → Run simulation. The first time after a server restart this takes about 30 s (see [which what-if](#which-what-if-to-use-and-why)). Run it a second time: now it must say "Instant: simulated before" in Analyst at once.
5. The replay link, and the 7′ free-kick clip.
6. Preview and Line-ups.

Then close the incognito window and open a new one for the take, so the viewer starts as Analyst, no team, no player.

### Recording tips

- Record each shot as its own take. Record the voice separately and lay it over.
- Shots 3 and 5 carry personalisation and innovation. Give them the longest holds.
- With Sahaltessen followed, keep the turning-point headlines out of frame where you can: the row at the top of the What if tab and "In the turning points" on Stats show "Sahltessen's goal sparks Tessmouth fightback" (a misspelt name) for ②, and ① and ③ are the template there.

## Backup for each shot

| # | If this goes wrong | Do this instead |
|---|---|---|
| 2 | The tooltip on "4 to 14" does not show | Hover "17.6% to 87.5%" in the first sentence (field tilt) and say "Vantry's share of the territory went from under a fifth to nearly nine tenths." |
| 3 | The fan text is still loading | Wait off camera and cut. Or show Fan with no team first, then add Tessmouth United. |
| 4 | Player spotlight is not on Stats | Check that the mode is Fan and a player is followed. Overview shows the same Player spotlight under "How Tessmouth United did". |
| 5 | The result is not instant (a queue or a progress bar) | Do not wait on camera. Press Run simulation again after it finishes (step 4 of the warm-up). If it queues for minutes, record it locally with `PIVOT_PIPELINE=fake` (README, "Run it locally"); a 200-run what-if takes about 30 s on a laptop, so cut the wait. Or narrate over a still of the result: "Tessmouth's chance of winning rises from a third to a half." |
| 6 | The replay runs past the goal | Click the goal mark on the scrubber; it jumps to 5 s before the goal. Or use Overview → Key moments → **75′ Goal, D. Sahaltessen** and play the clip at 0.5×. |
| 7 | Preview shows less than this | Show the formations and the coach's plan from Line-ups only, and say "Before kick-off: the form, and each coach's plan." |
| 8 | — | A plain slide is fine. |

## What we saw (2026-10-27)

Read from the site run locally against the live stores, at 1024 × 768.

- Score band: Tessmouth United 4–3 Vantry Town, full time. Goals: Sadoseno 17′ (penalty, after "16′ Penalty to VAN, foul by J. Nosaez"), Beltoov 26′, Sahaltessen 37′ (penalty), 54′ (VAR check, goal confirmed) and 75′, Quinsenlier 67′, Sadoseno 80′. Tessmouth came from 0–2 down.
- Turning points:
  - ① 12′ "Vantry Town gains control with sharp attack" (Verified ✓, set off by the 17′ goal, swing to Vantry Town);
  - ② 50′ "Tessmouth United goal swings the match" (Auto summary, set off by the 54′ goal);
  - ③ 88′ "Tessmouth United change shifts the balance" (Auto summary, set off by "82′ Substitution: Y. Samoris on, B. Vikmitesis off").
- Card ① in analyst view:
  - "At 12', Vantry Town's field tilt rose from 17.6% to 87.5%, gaining territorial control."
  - "Their final-third passes rose from 4 to 14 and box entries from 0 to 5, increasing attacking pressure."
  - "This attacking dominance led to Z. Sadoseno's goal at 17', turning momentum to Vantry Town."
- Card ① for a Tessmouth fan: "Tessmouth United lose control after Vantry's goal", "Vantry Town scored at 17' after building pressure with more passes into the final third and box entries.", "Meanwhile, Tessmouth United's share of the ball and presence in the attacking third dropped sharply." In Chinese "Vantry 进球后 Tessmouth 失控", in Spanish "Tessmouth United pierde control tras gol de Vantry". A Vantry fan gets the template for all three.
- Player: D. Sahaltessen, #11, ST, 101 minutes, rating 9.9, 3 goals, 9 shots, xG 1.88, top speed 35 km/h, 12 sprints.
- Match stats: possession 48.7 % / 51.3 %, shots 19 / 20, xG 2.76 / 2.22.
- Pre-match: Freeland League, Quayside Park, crowd 43,367, referee Z. Latesanson. Tessmouth 4th on 44 points, Vantry 9th on 38 (in the API only; the page does not show the table for this match). One earlier meeting, 0–0 (also API only). No storylines.
- Left out of the video on purpose:
  - in card ① (analyst), the tooltip on "0 to 5" (box entries) shows the final-third-passes source ("Final-third passes · Vantry Town · 12′–16′ · 14"), and it is cut off at the left edge of the card;
  - the followed-player versions: ① and ③ are the template, ② is model-written but spells him "Sahltessen" in English and Chinese, and the Spanish one is the template;
  - "Why it differs" in the what-if is the template, and its third sentence says Tessmouth's shots fell (13.6 to 12.3) while their chance of winning rose;
  - "Verified: 8 numbers, 1 events checked" ("1 events"; Spanish "8 cifras y 1 eventos");
  - the last five games in Preview are all marked "(home)" for both sides, and the home and away record reads 9 home and 17 away games for Tessmouth, 11 and 15 for Vantry, after 26 games;
  - both coaches' plans are identical (Balanced, medium press, normal tempo, mixed passing, the same set-piece plan).
