# Pivot: demo video script

Target length **1:54** (limit 2:00). Narration is **236 words**, about 1:41 at 140 words per minute; the rest is room for clicks and pauses. Captions: [video-captions.srt](video-captions.srt) (same timings as below).

Demo match: **M-seed-29**, Harbour City 3–1 Northgate Rovers, https://pivot.in-stacks.com/?match=M-seed-29

Every shot below was walked through on the live site on **2026-10-26**. What we saw is under each shot. Lines marked **⟳ check live** depend on AI text or simulation results that are being regenerated after the simulator version changed. Before recording, run the [checks](#before-recording) and change the narration if the site shows something else.

## Shot list

| # | Time | Picture (what to click) | Narration (words) | Judging point |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Match page, **More details** open, camera on the **Match stats** card (Possession 57 % / 43 %, Shots 13 / 6). | Match stats tell you what happened: fifty-seven percent possession, thirteen shots. Not why the game turned. **(16)** | The problem: football insight |
| 2 | 0:08–0:17 | Cut to the top of the page: "THE 3 MOMENTS THAT CHANGED THE COURSE OF THIS MATCH" and the momentum chart with markers ① ② ③. Slow move of the mouse along the momentum line. | Pivot finds the moments that turned a match, explains why, and lets you replay it with one thing changed. **(19)** | One-line pitch, innovation |
| 3 | 0:17–0:32 | Hover the three cards under the chart one by one: **① 38′** "Lisais' red card shifts momentum to Harbour City", **② 62′** "Harbour City adopts deeper, less intense press" (set off by 63′ substitution), **③ 75′** "Quinvika's entrance shifts Harbour City's control". Each card shows **VERIFIED ✓**. ⟳ check live | Here's a synthetic match. Harbour City three, Northgate one. Pivot found three turning points. A red card. A substitution that pulled Harbour City deeper. And a second change that won control back. **(32)** | Football insight: why a moment matters |
| 4 | 0:32–0:44 | Card ① is open below the cards ("WHY IT TURNED · 38′ · VERIFIED"). Hover the underlined **12 to 6**: the tooltip shows *Passes · Northgate Rovers · 33′–37′ · 12 · stat_ref.passes*. Then click evidence chip **#678**: the mini pitch marks "38′ Red card · E. Lisais". Show the line "Judge ✓ · Explainer ✓ · Verifier ✓ 4 claims · 4 evidence". ⟳ check live | Pick one. The AI explains why it mattered, and every number is checked. Northgate's passes fell from twelve to six. Hover it to see its source. **(26)** | Technical implementation, trust |
| 5 | 0:44–1:00 | In the same panel, **WHAT IF…**: click chip **Remove 38′ red card**, then **RUN SIMULATION**. Result is instant ("INSTANT · SIMULATED BEFORE"): **−28 points less likely a Harbour City win**, "CLEAR DIFFERENCE", As played HBC 80 % / Draw 15 % / ROV 6 %, With the change HBC 52 % / 30 % / 19 %, 95 % ranges, "ranges do not overlap". Hold 2 s on the bars. ⟳ check live | So did the red card decide it? Remove it, and Pivot replays the rest of the match two hundred times each way. Harbour City's win chance drops from eighty to fifty-two percent. A clear difference. **(35)** | Innovation, football insight |
| 6 | 1:00–1:08 | Scroll to **KEY MOMENTS**. Click row **40′ GOAL · H. Darbelnoez** (tag "EXTENDS THE LEAD", "→ Pivot ①"). The clip opens under the row. Click **0.25×**, then ▶. Caption under the pitch: "On the ball: 9 · C. Felbelroini → 10 · H. Darbelnoez". | Two minutes after the red card, Harbour City scored. Here it is at quarter speed. **(15)** | Demo, football insight |
| 7 | 1:08–1:15 | Open **SET PIECES & SHOTS** ("11 corners · 19 shots, each one replayable"), tab **CORNERS & FREE KICKS**, click **40′ HBC Corner · C. Felbelroini · GOAL**. Point at "In the box: HBC 4 attackers · ROV 3 defenders" and "Marking: Zonal · 0 of 4 attackers had a defender within 2.5 m". ⟳ check live (set-piece positions are being reworked in #245) | From a corner. Four attackers, three defenders, and nobody tight on them. **(12)** | Football insight |
| 8 | 1:15–1:20 | Click **中文** in the top bar. Title becomes "改变这场比赛走向的 3 个时刻"; card ① text and the what-if chips switch to Chinese. Optional: click **ES** for one second. | One click, and it's all in Chinese. Or Spanish. **(9)** | Completeness |
| 9 | 1:20–1:38 | Switch back to **EN**. Open **More details** → **AGENT TRACE** → button **TRACE 3** (opens `/trace`, "EVERY STEP THE AI TOOK"). The top card is **75′ · Quinvika's entrance…**: box "SENT BACK BY THE VERIFIER (2)": *Number does not match: the number 70 in sentence 1 only matches pass_accuracy_pct for Northgate Rovers, but the sentence has it about Harbour City*. Below: Judge · mini → Explainer · standard "First draft" → Verifier · rules "Sent back" → Explainer "Rewrite 1" → Verifier "Every claim checks out". ⟳ check live | Every card comes from a Microsoft Agent Framework workflow. A Judge confirms the moment. An Explainer writes it. A Verifier recomputes every number. Here, it caught the model giving Harbour City the other team's pass accuracy, and sent it back. **(40)** | Microsoft tech, technical implementation |
| 10 | 1:38–1:46 | Architecture picture: the "How it works" diagram in the README on GitHub (https://github.com/neubayarea/Pivot#how-it-works), zoomed so the Azure box (Azure AI Foundry, Cosmos DB, Blob Storage) fills the frame. | The agents run on Azure AI Foundry. Results live in Cosmos DB, matches in Blob Storage. **(16)** | Microsoft tech |
| 11 | 1:46–1:54 | End card: Pivot logo or the match page top, with text *pivot.in-stacks.com · github.com/neubayarea/Pivot · All clubs, players and matches are synthetic.* | Every match here is synthetic, as the rules require. Next: real match data. This is Pivot. **(16)** | Data rules, what comes next |

Total: 236 words.

### Why this order

The first 17 seconds state the problem and the answer. Shots 3–7 stay on one moment (the 38′ red card) and look at it four ways: the explanation, a checked number, the what-if, and the goal it led to with the corner that made it. Shots 8–10 show how it is built. Shot 9 is the strongest proof of "the AI is checked": a real rejected draft from the live site.

## Before recording

### Screen and browser

- Chrome, an **incognito window** (the site remembers language and match in browser storage; on 10/26 a normal window opened in Spanish).
- Page area **1920 × 1080**, browser zoom 100 %. Record at 1920 × 1080, 30 fps.
- Hide the bookmarks bar, close other tabs, hide the Dock, turn on **Do Not Disturb** (no Slack, mail or calendar pop-ups), mute system sounds.
- Language **EN** in the top bar. **Settings → Viewing mode: Analyst**, Your team: none (the script uses the analyst wording; it is the default).
- Mouse: turn on a cursor highlight if your recorder has one. Move slowly; hold still for half a second before every click.

### Check the live site still matches the script (10 minutes before)

```bash
curl -s https://pivot.in-stacks.com/api/matches/M-seed-29/pivots | python3 -c "import json,sys;[print(p['pivot_id'],p['narrative']['headline']) for p in json.load(sys.stdin)]"
```

On 10/26 this printed `p37` "Lisais' red card shifts momentum to Harbour City", `p66` "Harbour City adopts deeper, less intense press" and `p79` "Quinvika's entrance shifts Harbour City's control" (shown on the page as 38′, 62′, 75′). If the minutes or headlines changed, rewrite shot 3, and check shots 4 and 9 against the page.

- **Shot 4:** the first sentence of card ① still has an underlined number. If it is not "12 to 6", say the new number and team.
- **Shot 9:** `/trace` still has a card with "SENT BACK BY THE VERIFIER". If the pass-accuracy example is gone, describe the one shown (any "Number does not match" or "Wrong direction" line works: "Here, it caught a wrong number and sent it back.").
- **Shot 7:** after #245 lands, the 40′ corner numbers may change. Read them off the page.

### Warm up (open each once, so nothing loads on camera)

1. https://pivot.in-stacks.com/?match=M-seed-29 (wait for the momentum chart and the three cards).
2. Card ① → **Remove 38′ red card** → **RUN SIMULATION**. It must say "INSTANT · SIMULATED BEFORE". On 10/26 it did (scenario `M-seed-29:s7209aa0245eb`, HBC 79.5 % → 51.5 %).
3. Key moments → 40′ goal clip, play once.
4. Set pieces & shots → 40′ corner.
5. Switch to 中文 and ES once each (the first request in a language writes it), then back to EN.
6. More details → Agent trace → TRACE 3 (`/trace`).
7. GitHub README "How it works" (the diagram takes a moment to render).

The repository was still **private** on 10/26. Shot 10 shows GitHub, so either record it after the repository is made public, or use the slide backup.

Then reload the match page so every panel starts closed.

### Recording tips

- Record each shot as its own take; cut them together. Record the voice separately and lay it over.
- Shots 5 and 9 are the ones judges remember. Give them the longest holds.
- Stay on M-seed-29 and on the red-card what-if. **Do not click other what-if chips on camera**: on 10/26 only the red-card one was confirmed as already computed, and a new one takes about 10 minutes on the 2-core server (the red-card run took 625 s when it was first computed).

## Backup for each shot

| # | If this goes wrong | Do this instead |
|---|---|---|
| 1 | Stats card shows different numbers | Say the numbers on screen, or drop the numbers: "Match stats tell you what happened. Not why the game turned." |
| 2–3 | Moments changed after regeneration | Use what the page shows; keep the pattern "a red card, a substitution, a second change". If a card shows "Auto summary" instead of "VERIFIED ✓", film a different card and mention it: the fallback is a feature ("If no draft passes, a plain checked summary is shown"). |
| 4 | No underlined number in card ① | Click **FULL DETAIL →** for card ① and hover a number there, or click card ② and hover its number. |
| 5 | Red-card what-if is not instant (shows a queue or progress) | Do not wait on camera. Option A: record it on your laptop with `PIVOT_PIPELINE=fake` (see README "Run it locally"; a 200-run what-if takes about 30 s there, then cut the waiting). Option B: use the screenshot `docs/screenshots/submission/04-whatif-result.png` with a slow zoom, and say "Harbour City's win chance drops sharply." |
| 6 | Clip does not play | Use the 52′ goal or the 11′ goal row; or skip the clip and click **Replay from here →**. |
| 7 | Set-piece panel looks broken (see #244) | Use tab **EVERY SHOT**, click the 40′ goal shot to replay it; narrate "Every shot can be replayed." |
| 8 | Chinese text missing for a card | Switch to ES instead, or show the Chinese title and chips only. |
| 9 | `/trace` empty or slow | Open https://pivot.in-stacks.com/api/pivots/M-seed-29:p79/traces in the browser (raw JSON with the same `number_mismatch`), or use `docs/screenshots/d10-trace/`. |
| 10 | GitHub diagram does not render | Screenshot the diagram from `docs/architecture.md`, or a simple slide: Browser → FastAPI (Oracle VM) → Azure AI Foundry · Cosmos DB · Blob Storage. |
| 11 | — | A plain slide is fine. |

## What we saw on the live site (2026-10-26)

- Top: "AFTER THE MATCH · HARBOUR CITY 3–1 NORTHGATE ROVERS", "THE 3 MOMENTS THAT CHANGED THE COURSE OF THIS MATCH", button START DEMO, momentum chart with markers 1 (38′), 2 (62′), 3 (75′).
- Card ①: "Lisais' red card at 38' forced Northgate Rovers to a mid defensive line and press, reducing their passes from 12 to 6. #678 #679" and "Harbour City dominated possession with 94.7% field tilt and created three box entries, leading to Darbelnoez's goal. #714 #716".
- Inline what-if chips: Remove 38′ red card, Disallow 40′ goal, Cancel 63′ substitution. Red card result as in shot 5. "Why it differs": "Removing the 38′ red card made a Northgate Rovers win more likely in the replays. Northgate Rovers increased shots from 4.9 to 10.4 and xG from 0.65 to 1.5…"
- Key moments: 11′ goal (opener, 1–0), 38′ red card, 40′ goal (extends the lead, 2–0), 46′ penalty to ROV then VAR overturns it, 52′ goal (3–0), 56′ penalty to HBC, 86′ goal ROV (pulls one back, 3–1). Clip speeds 0.25× 0.5× 1× 2× 5×.
- Set pieces: HBC 5 corners · 5 free kicks → 1 shot, 1 goal; ROV 6 corners · 1 free kick → 1 shot, 1 goal.
- More details: On the pitch (team shape, vs 5 min before, formation 4-3-3 vs 4-4-2 · 10 players, back line, width, depth), Line-ups, Match stats, Events, Agent trace.
- Agent trace: all three moments had at least one draft sent back by the Verifier (38′: twice, 62′: once, 75′: once).
- Not read aloud, on purpose: card ② says "PPDA worsen from 6.0 to 3.75, indicating fewer defensive actions per opponent pass" (a lower PPDA means *more* pressing), and the Chinese card ① translates "field tilt" as 控球率 (possession). Neither is in the script.
