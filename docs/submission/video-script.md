# Pivot: demo video script

Length **1:57** (limit 2:00). Narration: **249 words**, about 1:47 at 140 words a minute. The rest is room for clicks. Captions: [video-captions.srt](video-captions.srt), with the same timings as below.

Demo match: **M-seed-101**, **Harbour City 3–3 Northgate Rovers**. The site opens it by default: https://pivot.in-stacks.com/

Every number below was read off the live site and its API on **2026-10-27**, after tonight's regeneration (set-piece positions #265, per-coach tactics #289). Before recording, run the [checks](#check-the-live-site-10-minutes-before) to confirm them again.

## Tabs

The match page has six tabs (#316, merged in #323), each with its own link `?tab=`:

| Tab | `?tab=` | Used in |
|---|---|---|
| **Overview** 概况 | `overview` | Shots 1–3, 6b |
| **What if** 假如 | `whatif` | Shot 5 |
| **Replay** 回放 | `replay` | Shot 6a. While a replay is playing, this tab is labelled **Live**. |
| **Stats** 数据 | `stats` | Shot 4 |
| **Line-ups** 阵容 | `lineups` | Shot 7b |
| **Preview** 赛前 | `preview` | Shot 7a |

Viewer settings can go in the link too: `mode=fan|analyst`, `team=home|away|none`, `player=<id>|none`, `lang=en|zh|es`. M. Miquingorini is `h10`. On camera, change them with the top-bar controls: **Fan / Analyst**, **♥ Team**, **★ Player**, **EN / 中文 / ES**.

Section names change with the viewing mode. Analyst says "Form & table", "Head-to-head", "The coach's plan" and "News & storylines". Fan says "How they come in", "When they last met", "How each coach wants to play" and "The talk before the game". Shots 1–2 are in analyst mode and shots 3–7 in fan mode.

## Shot list

| # | Time | Picture: what to click | Narration (words) | Judging point |
|---|---|---|---|---|
| 1 | 0:00–0:12 | **Overview.** Open the [start link](#links). Score band: **Harbour City 3–3 Northgate Rovers**, "Miquingorini 60′, 65′, 82′" and "Rasfelrassen 19′ · Anbel 35′ · Renbelov 89′". Scroll slowly to "The 3 moments that changed the course of this match" and the momentum chart with markers **① 14′ ② 35′ ③ 72′**. The header folds into the slim bar as you scroll. | Harbour City three, Northgate Rovers three: one simulated match. Pivot finds the moments that turned it, explains why, and lets you replay it with one thing changed. **(27)** | The problem and the one-line pitch |
| 2 | 0:12–0:31 | **Turning points, analyst view.** Click card **② 35′ "Anbel's goal shifts momentum decisively"** (Verified ✓, "Set off by 35′ Goal: O. Anbel"). Under **Why it turned**: "Checked: 10 numbers, 2 events". Hover the underlined **0 to 4** in the second sentence: the tooltip shows *Final-third passes · Northgate Rovers · 30′–34′*. Click evidence chip **#676**: the mini pitch shows "35′ Goal: O. Anbel". Hold 1 s on "Judged, written and checked by the AI. Claims checked: 10." | Pivot found three turning points. Take Anbel's goal at thirty-five minutes. A Judge agent confirms it really swung the game. An Explainer writes why. A Verifier recomputes every number from the event log: Northgate's passes into the final third went from zero to four. **(44)** | Football insight, trust in the AI |
| 3 | 0:31–0:45 | **Switch to fan and pick a team.** Still on card ②, click **Fan** in the top bar, then **♥ Team → Harbour City**. The headline changes from "Anbel's goal shifts momentum decisively" to **"Harbour City lose grip after Northgate's second"**, and the text takes Harbour City's side ("After the goal, Harbour City's passes into the attacking third dropped to zero…"). Click **中文** (headline "Northgate再下一城 Harbour City失控"), then **ES** ("Harbour City pierde control tras segundo gol de Northgate"), then back to **EN**. | Now switch to Fan and pick Harbour City. Same moment, same checked facts, told from your side: "Harbour City lose grip after Northgate's second." In Chinese or Spanish, too. **(29)** | Personalisation (rule 4.1): audience, team, language |
| 4 | 0:45–0:57 | **Follow a player.** Click **★ Player → M. Miquingorini**. (Or tap his name and press **☆ Follow** on his player card, #324, once that is live.) Card ③ now reads "Miquingorini's goal lifts Harbour City". Click the **Stats** tab. At the top: "How Harbour City did · 3–3 · Best player: M. Miquingorini, rated 9.3", then **Player spotlight**: rating **9.3** (team average 7.0), Goals **3**, Shots **7**, Top speed **33** km/h. Click **Heatmap**, then hover "In the turning points" (14′, 35′, and 72′ "set it off"). | Follow a player. Miquingorini scored a hat-trick and is rated nine point three. You get his shots, his heatmap and his part in each turning point. **(26)** | Personalisation (rule 4.1): followed player |
| 5 | 0:57–1:18 | **What-if.** Click the **What if** tab, then **Pivot 3, 72′** in the row at the top. (The same panel is also under card ③ on Overview.) Click chip **Disallow 65′ goal**, keep **200** runs, click **Run simulation**. Result: **+27pts**, "Without the 65′ goal, Northgate Rovers's chance of winning rises from 26% to 53%, and the most likely score goes from 2–2 to 1–2." **Clear difference**. As played (from 64′): HBC 32 % · Draw 43 % · ROV 26 %. With the change: HBC 13 % · Draw 35 % · ROV 53 %. In fan mode with Harbour City a line adds "Harbour City's chance of winning: 32% as played, 13% with the change." Hold 2 s on the bars, then on "◆ ranges do not overlap". | So what if his equaliser had been ruled out? Pivot saves the match at that minute and plays the rest two hundred times each way. Northgate's chance of winning doubles, from twenty-six to fifty-three percent. The ranges don't overlap. It's a clear difference. **(43)** | Innovation, football insight |
| 6 | 1:18–1:35 | **Replay and set pieces.** (a) 1:18–1:27: open the [replay link](#links) (`from=66`). As soon as the pitch shows, pause (❚❚), click **5×** on the bar under the pitch, then play. Passes draw a line from passer to receiver and tackles flash. At 65′ Miquingorini's goal gets a gold ring. (b) 1:27–1:35: **Overview** → **Set pieces & shots** → **Set pieces** → row **60′ HBC Free kick in the attacking third · M. Rasnosen · Goal**. The clip plays at 1×. It shows "In the box: HBC 3 attackers, ROV 8 defenders (keeper included)", "Marking: Man-to-man, 3 of 3 attackers had a defender within 2.5 m" and "What happened: 60′ HBC, Goal: M. Miquingorini". | Every match replays on the pitch, with passes, shots and tackles drawn as they happen. Set pieces too: his first goal came from a free kick, three attackers against eight defenders, all three man-marked. **(34)** | Demo, football insight |
| 7 | 1:35–1:46 | **Preview and line-ups.** (a) Click the **Preview** tab. "Qualification at stake". Under "How they come in", "2 points apart": Harbour City **3rd, 48 pts** (D W L L L), Northgate Rovers **5th, 46 pts** (W D W W L). Scroll to "The talk before the game": "S. Katoo under pressure after 3 defeats in Harbour City's last five league games". (b) Click **Line-ups**, section "How each coach wants to play". Harbour City **4-3-3, S. Katoo, Defensive**, low press, slow tempo. Northgate Rovers **4-2-3-1, Y. Darquiner, Balanced**. | Before kick-off: third against fifth, two points apart, the storylines, and each coach's plan: a defensive four-three-three against a balanced four-two-three-one. **(21)** | Completeness, football context |
| 8 | 1:46–1:57 | **End card**: a plain slide, or the match page dimmed behind text. **Pivot** · *Azure AI Foundry: models for the Judge, Explainer and Comparator agents · Azure Cosmos DB: results · Azure Blob Storage: match library* · *pivot.in-stacks.com · github.com/neubayarea/Pivot* · *All clubs, players and matches are synthetic.* | The agents run on Azure AI Foundry. Results live in Cosmos DB, matches in Blob Storage. Every club and player is synthetic. This is Pivot. **(25)** | Microsoft technology, data rules |

Total: 249 words. If it runs long, cut "It's a clear difference." from shot 5 (4 words) and let the "Clear difference" label say it.

### Which what-if to use, and why

Use **Disallow 65′ goal** from turning point ③ (72′). It is about the player followed in shot 4, and it is one of the three changes with a large effect. Each chip was replayed 200 times each way (#320). On 10/27 the live server returned:

| Turning point | Change | As played → with the change (API values) | Clear difference? |
|---|---|---|---|
| ③ 72′ | **Disallow 65′ goal** (Miquingorini's equaliser) | ROV win 25.5 % → 52.5 %, HBC win 31.5 % → 13.0 %, most likely score 2–2 → 1–2 | yes, for HBC win and ROV win |
| ② 35′ | Disallow 35′ goal (Anbel) | ROV win 82.0 % → 49.5 %, HBC win 6.5 % → 20.0 % | yes, all three |
| ① 14′ | Disallow 19′ goal (Rasfelrassen's penalty) | HBC win 31.0 % → 45.5 %, ROV win 49.0 % → 25.5 % | yes, for HBC win and ROV win |
| any | Cancel or move a substitution, press higher | at most 7.5 points on any outcome | no |

The page rounds these to whole percentages (26 % → 53 %, 32 % → 13 %). The scenario in the video is `M-seed-101:see12b333150f` (`/api/scenarios/M-seed-101:see12b333150f`); the inline panel says "Instant: simulated before". **Do not click other chips on camera.** Later on 10/27 the server no longer returned some of the others, for example the 35′ one. A scenario that is not stored runs again, and that takes minutes on the 2-core server (the 65′ one took 155 s the first time).

### Why this order

Shots 1–2 state the problem and show the checked explanation on the strongest card. Turning point ① is an "Auto summary" (the template fallback), so the script never opens it. Shots 3–4 are the personalisation rule 4.1 asks for: audience, team and language, then a followed player. Shot 5 asks a question about that player's goal. Shot 6 shows the pitch and the same player's set-piece goal, and shot 7 shows what the page knows before kick-off.

## Before recording

### Screen and browser

- Chrome, **incognito window**: the site remembers language, viewer settings and match in browser storage. Page area **1920 × 1080**, zoom 100 %. Record at 1920 × 1080, 30 fps.
- Hide the bookmarks bar and the Dock, close other tabs, turn on **Do Not Disturb**, mute system sounds.
- **No music**, or only music you hold a licence for. **No Premier League logos or marks** anywhere: browser tabs, desktop, end card.
- Mouse: turn on cursor highlight if your recorder has it. Hold still for half a second before each click.

### Links

| Use | Link |
|---|---|
| Start (shots 1–2) | https://pivot.in-stacks.com/?match=M-seed-101&tab=overview&mode=analyst&team=none&player=none&lang=en |
| Shot 2 with card ② already open | add `&pivot=M-seed-101:p34` |
| Shot 4, if you cut there | https://pivot.in-stacks.com/?match=M-seed-101&tab=stats&mode=fan&team=home&player=h10&lang=en |
| Shot 5, if you cut there | https://pivot.in-stacks.com/?match=M-seed-101&tab=whatif&pivot=M-seed-101:p74&mode=fan&team=home&player=h10&lang=en |
| Shot 6a, replay | https://pivot.in-stacks.com/?match=M-seed-101&tab=replay&from=66&mode=fan&team=home&player=h10&lang=en |
| Shot 7a | https://pivot.in-stacks.com/?match=M-seed-101&tab=preview&mode=fan&team=home&player=h10&lang=en |
| Shot 7b | https://pivot.in-stacks.com/?match=M-seed-101&tab=lineups&mode=fan&team=home&player=h10&lang=en |

Old links with `tab=pre|live|post` still work: they open Preview, Replay and Overview.

`team=none&player=none` in the start link clears anything a previous take saved. `from=` is in minutes of match time. The replay starts at 20×, so pause it first.

### Check the live site (10 minutes before)

```bash
curl -s https://pivot.in-stacks.com/api/matches/M-seed-101 | python3 -c "import json,sys;print(json.load(sys.stdin)['score'])"
curl -s https://pivot.in-stacks.com/api/matches/M-seed-101/pivots | python3 -c "import json,sys;[print(p['pivot_id'],p['status'],p['narrative']['headline']) for p in json.load(sys.stdin)]"
curl -s https://pivot.in-stacks.com/api/scenarios/M-seed-101:see12b333150f | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r['baseline']['away_win'],r['counterfactual']['away_win'])"
```

On 10/27 these printed:
- the score `home 3, away 3`;
- `p13 degraded "Momentum swings to Northgate Rovers"`, `p34 confirmed "Anbel's goal shifts momentum decisively"` and `p74 confirmed "Miquingorini's goal sparks Harbour City revival"`;
- `0.255 0.525`.

If anything differs, re-read the shots off the page, then change the narration and the captions together. If the last command says "not found", the what-if is no longer stored; see backup 5.

### Warm up (open each once, so nothing is written on camera)

1. The start link. Wait for the momentum chart and the three cards.
2. Card ② → Fan → ♥ Harbour City. Wait until the headline reads "Harbour City lose grip after Northgate's second". While a version is being written, the card says "Writing the fan version. Showing the analyst version for now."; on 10/27 that took about 30 s. Then click 中文 and ES once each.
3. ★ Miquingorini. Check that card ③ reads "Miquingorini's goal lifts Harbour City".
4. Stats → Player spotlight → Heatmap.
5. What if → Pivot 3, 72′ → Disallow 65′ goal → Run simulation. The result must appear within a few seconds (it says "200 runs in 154.7 s", the time it took when first computed). It can show "Replaying… 400 of 400" for a second while the stored result loads; cut that if it shows.
6. The replay link, and the 60′ free-kick clip.
7. Preview and Line-ups.

Then open the start link again, so every panel starts closed and the viewer is back to Analyst, no team, no player.

### Recording tips

- Record each shot as its own take. Record the voice separately and lay it over.
- Shots 3 and 5 carry personalisation and innovation. Give them the longest holds.
- In fan mode with Harbour City and Miquingorini, do not show card ③ in Chinese: on 10/27 it was still the template ("Harbour City失去势头"). Card ② was written by the model in all three languages.

## Backup for each shot

| # | If this goes wrong | Do this instead |
|---|---|---|
| 2 | The tooltip on "0 to 4" does not show | Hover "0 to 0.93" in the third sentence (xG) and say "Northgate's expected goals went from zero to nearly one." |
| 3 | The fan text is still loading | Wait off camera and cut. Or show Fan with no team first, then add Harbour City. |
| 4 | Player spotlight is not on Stats | Check that `mode=fan` and a player are set. Overview also shows a "★ Following M. Miquingorini" card (Goals 3, Goes at goal 7) under the what-if panel. |
| 5 | The result is not instant (a queue or a progress bar) | Do not wait on camera. Try the inline panel under card ③ on Overview; on 10/27 it said "Instant: simulated before". If that queues too, record it locally with `PIVOT_PIPELINE=fake` (README, "Run it locally"); a 200-run what-if takes about 30 s on a laptop, so cut the wait. Or narrate over a still of the result: "Northgate's chance of winning doubles." |
| 6 | The replay runs past the goal | Click the gold goal mark on the scrubber; it jumps to 5 s before the goal. Or use Overview → Key moments → **65′ Goal, M. Miquingorini** and play the clip at 0.5×. |
| 7 | Storylines or the coach's plan are missing | Show the table and the formations from Line-ups only, and drop "the storylines" from the narration. |
| 8 | — | A plain slide is fine. |

## What we saw on the live site (2026-10-27)

- Score band: Harbour City 3–3 Northgate Rovers, full time. Goals: Rasfelrassen 19′ (penalty), Anbel 35′, Miquingorini 60′ (from a free kick), 65′ and 82′, Renbelov 89′.
- Turning points, all swinging to Northgate Rovers:
  - ① 14′ "Momentum swings to Northgate Rovers" (Auto summary);
  - ② 35′ "Anbel's goal shifts momentum decisively" (Verified ✓, set off by the 35′ goal);
  - ③ 72′ "Miquingorini's goal sparks Harbour City revival" (Verified ✓, set off by the 65′ goal).
- Card ② in analyst view:
  - "At 35', O. Anbel scored after a Northgate Rovers build-up with 75% pass accuracy, reversing their earlier 44% rate."
  - "Northgate Rovers increased their final-third passes from 0 to 4 and box entries from 0 to 2 after the goal."
  - "…xG from 0 to 0.93 and threat created from 0.007 to 0.30."
- Card ② for a Harbour City fan following Miquingorini: "Harbour City lose grip after Northgate's second", then "O. Anbel scored at 35' to double Northgate's lead, ending Harbour City's strong spell with M. Miquingorini involved."
- Card ③ for the same viewer: "Miquingorini's goal lifts Harbour City", then "M. Miquingorini scored at 65' to level the game, sparking hope for Harbour City fans."
- Player: M. Miquingorini, #10, ST, 100 minutes, rating 9.3, 3 goals, 7 shots, xG 0.80, top speed 33 km/h.
- Match stats: possession 51 % / 49 %, shots 14 / 13, xG 1.63 / 2.28.
- Pre-match: Freeland League, Harbour Park, crowd 38,000, referee S. Midar. Head-to-head over 5 meetings: HBC won 2, 1 draw, ROV won 2.
- Left out of the narration on purpose:
  - in card ②, the tooltip on "0 to 2" (box entries) shows the final-third-passes source instead;
  - card ③'s analyst headline says "Harbour City revival" while its momentum went to Northgate Rovers;
  - the result sentence says "Northgate Rovers's".
