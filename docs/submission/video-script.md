# Pivot: demo video script (v2)

Length **1:41** (limit 2:00), 1920 × 1080, 30 fps. Narration: **252 words**, an English AI voice (Microsoft neural voice `en-GB-RyanNeural`, made with `edge-tts`). Captions are burned in and also in [video-captions.srt](video-captions.srt). No music. No Premier League marks. Every club, player and match is synthetic.

This replaces the 17:45 PT script. The site changed a lot since then: the Live tab and the What-if tab now differ between Fan and Analyst, Stats has the analyst deep dive, and a followed player shows across the page. The new cut is built around the five stages of rule 4.1 (ingest, interpret, explain, render, personalise), and it shows the fan / analyst difference by switching on camera.

Recorded on the **live site** https://pivot.in-stacks.com on **2026-10-27, 22:48–23:05 PT**, after #446 was deployed. Each shot was recorded in headless Chrome at 1920 × 1080 through the DevTools screencast, with a drawn cursor. The scripts are in [`scripts/video/`](../../scripts/video/).

## Shot list

A small label in the bottom-left names each part ("Live · Fan view", "Live · Analyst view", "Explain", "Personalise", "What if · Fan view", "What if · Analyst view", "Analyst report").

| # | Time | Picture | Narration | Judging point |
|---|---|---|---|---|
| 1 | 0:00–0:15 | **Live, fan.** Simulated live match S2026-29-BRI-FAL (Brightmoor 2–1 Fallowden, about 42′), Live tab in Fan mode: the pitch plays, "Right now: Brightmoor are on top at the moment.", the momentum line, three plain numbers and "The big moments". A title card ("pivot · The moments that changed the match, and why") sits on top for the first 3 s. | Football stories don't end with the scoreline. Pivot ingests a synthetic match event by event, every pass, shot and tackle, and renders it beside the action. A fan sees the pitch, who's on top right now, and the big moments. | Rule 4.1 ingest and render; the fan experience |
| 2 | 0:15–0:27 | **Live, analyst.** Click **Analyst** in the top bar. The same minute becomes "Last ten minutes": xG, Tilt, PPDA and Poss for both teams, each with a trend line; the tactical pitch with **Shape lines / Pressing zones / Passing lanes** (Pressing zones and Passing lanes clicked on camera), the shape and tactics table, the filterable events and the shot xG card. | Switch to Analyst, and the same match becomes a live data centre: expected goals, field tilt, pressing and possession over the last ten minutes, with shape, pressing zones and passing lanes on the pitch. | Rule 4.1 personalise: two genuinely different experiences |
| 3 | 0:27–0:47 | **Explain.** Demo match S2026-27-TES-VAN (Tessmouth United 4–3 Vantry Town), Overview in Analyst mode. Scroll to **Momentum** with turning points ① 12′ ② 50′ ③ 88′, then to card **① "Vantry Town gains control with sharp attack"** ("Checked: 6 numbers, 5 events"). Hover the underlined **4 to 14**: the tooltip reads *Final-third passes · Vantry Town · 7′–11′ · 4 · 12′–16′ · 14*. End on "Judged, written and checked by the AI. Claims checked: 6. Evidence: 5." | Pivot turns the events into momentum, and flags the minutes where the game swung. A Judge agent on Azure AI Foundry decides if it's a real turning point. An Explainer writes why. And a Verifier, plain code, recomputes every number from the event log: Vantry's passes into the final third went from four to fourteen. | Interpret and explain; multi-agent design; trust |
| 4 | 0:47–1:00 | **Personalise.** Overview in Fan mode. Click **♡** next to Tessmouth United: "How Tessmouth United did · 4–3" appears and the story cards turn to Tessmouth's side ("Tessmouth United lose control after Vantry's goal"). Click **中文** ("这场比赛是怎么定下来的", "Vantry 进球后 Tessmouth 失控"), then **ES** ("Cómo se decidió el partido", "Tessmouth United pierde control tras gol de Vantry"). Cut to Stats with D. Sahaltessen followed: "★ Following: D. Sahaltessen" under the score, Best player 9.9 "★ Following", Player spotlight (Goals 3, Shots 9, Top speed 35, Sprints 12). | Then it personalises. Pick your club, and the same checked moment is told from your side, in English, Chinese or Spanish. Follow a player, and Pivot keeps that player in focus all match. | Rule 4.1 personalise: club, language, player |
| 5 | 1:00–1:18 | **What if.** What if tab in Fan mode, Tessmouth picked: "The biggest what-ifs of this match", top row open: "What if D. Sahaltessen's 54′ goal hadn't counted?", "Without the 54′ goal, the chance of Tessmouth United winning falls from 44% to 20%…", **44% → 20%**, the "Who wins" bars and the likeliest score 3–2 → 2–2. Click **Analyst**: "What if: Disallow 17′ goal", **+16 pts**, "Clear difference", the bars with 95 % ranges, effect +16.5 pts (95 %: +7.0 to +26.0), chance it helps over 99.9 %, expected points, and the range lines ("ranges do not overlap"). | And you can ask: what if? Pivot saves the match at that minute and replays the rest two hundred times each way. A fan gets their team's biggest what-ifs, in one line. An analyst gets the effect with its ninety-five percent range, and whether the difference is clear. | Innovation; football insight |
| 6 | 1:18–1:29 | **Analyst report.** Stats in Analyst mode, scrolling: Match phases → Game state → Shot quality → Set-piece analysis → Attacking lanes → Style profile (radar, percentiles against the stored matches). | After full time, analysts get the deep dive: match phases, game state, shot quality, attacking lanes and style percentiles. | Professional analyst depth |
| 7 | 1:29–1:41 | **End card.** pivot · *The moments that changed the match, and why* · Azure AI Foundry (Judge, Explainer and Comparator agents) · Microsoft Agent Framework (detect workflow, rewrite loop and fallback) · Azure Cosmos DB (results) · Azure Blob Storage (match library) · pivot.in-stacks.com · github.com/neubayarea/Pivot · "All clubs, players and matches are synthetic." | The agents run on Azure AI Foundry and Microsoft Agent Framework, with results in Cosmos DB. Every club and player is synthetic. This is Pivot. | Microsoft technology; data rules |

## Kept out of frame on purpose

- Turning points ② and ③ of the demo match are "Auto summary" (the template), so only ① is opened.
- With a player followed, the turning-point list under Player spotlight spells ② as "Sahltessen"; the shot stops above that list.
- The analyst what-if result shown is the stored one at the top of the tab; nothing is run on camera.

## How to make it again

From a folder with `scripts/video/` copied in, with Chrome, Node 22+, ffmpeg and uv installed:

1. Voice: `uvx edge-tts --voice en-GB-RyanNeural --rate=+6% --file tts/s1.txt --write-media tts/s1.mp3 --write-subtitles tts/s1.srt` for each of the seven lines above (`s1`–`s7`).
2. Shots: `node rec.mjs live`, then `explain`, `personal`, `follow`, `whatif`, `report`. Each writes `takes/<name>.mp4`. Use one browser at a time; the server has 2 cores.
3. Cards: `python cards.py` (end card, title and labels).
4. Edit: `python edit.py` writes `pivot-demo.mp4` and `captions.srt`. The cut points in `PIECES` and the voice start times in `VOICE` match the takes recorded on 10/27; check them again after a new recording.
