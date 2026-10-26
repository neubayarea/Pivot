# Pivot: submission text

Text for the hackathon submission form. Facts and numbers match the [README](../../README.md) and the live site as checked on 2026-10-26; update them together.

## Title

Pivot: the moments that changed the match, and why

## One-liner

Pivot finds the few moments that changed the course of a football match, has AI agents explain why each one mattered with every number checked by code, and lets you replay the rest of the match with one decision changed.

## Project description

**The problem.** Match stats tell you what happened: possession, shots, xG. They do not tell you which moments turned the game, or why. AI writes fluent summaries but gets numbers wrong, and one wrong number breaks fans' trust.

**What Pivot does.** Open a match and Pivot leads with *the moments that changed the course of this match*, marked ①②③ on a momentum chart.

1. **Find.** Per-minute momentum is built the way Opta builds the Premier League's: each team's most dangerous action of the minute, weighted towards the last few minutes. A change-point alarm flags the minutes where the game swung and stayed swung.
2. **Explain.** A Judge agent decides whether a candidate is a real turning point. An Explainer agent writes the headline and up to three sentences; every sentence cites match events and every number cites a statistic. A Verifier, written as ordinary code, recomputes each number from the event log and checks the score, the direction of momentum and the cited events. Drafts that fail go back with the problems listed. If three drafts fail, or the model is slow, a plain summary built only from checked numbers is shown instead.
3. **Test.** Under each moment, "What if…" offers changes such as *remove the 38′ red card*. Pivot saves the match at that minute and plays the rest 200 times with and 200 times without the change, using the same random seeds for each pair. It shows the win/draw/loss shift with 95 % Wilson ranges, and a Comparator agent explains where the difference comes from. The Verifier blocks any wording the numbers do not support.

Around the moments: **key moments** (goals, red cards, penalties, VAR reversals, tagged as opener, equaliser, comeback or late winner) play as short clips on the pitch at 0.25× to 5×; **set pieces and shots** shows how many attackers and defenders were in the box at each corner or free kick, whether the marking was zonal or man-to-man, and replays every shot; **more details** has the live pitch (formation, back-line height, compared with five minutes earlier), match stats, every event, both line-ups, and the **agent trace**: every step the AI took, including drafts the Verifier sent back. Everything is available in English, Chinese and Spanish, in Analyst or Fan wording, and each version goes through the same Verifier.

**Football realism.** All clubs, players and matches are synthetic, as the rules require. They come from our own possession-chain simulator with 22 rated players and per-second positions, calibrated against real Premier League numbers: 29 of 44 checks fall within tolerance, including goals (2.9 vs 3.1 per match) and shots (25.4 vs 26.8). After a red card the 11-man side's share of shots rises to 0.77, against 0.72 in real Premier League matches. Where it still misses (pass accuracy, clearances, interceptions), we say so in the README.

**Next.** Everything after the simulator reads a plain list of match events. Real matches need one adapter for a data provider's feed, which we have not written yet.

## How it maps to the judging criteria

- **Innovation.** Not a summary but a ranked set of turning points, each with a checked explanation and a counterfactual replay that shows how much it changed the result.
- **Technical implementation.** A multi-agent workflow with a rewrite loop and a guaranteed fallback; a deterministic Verifier for every number and claim; a reproducible simulator that can be saved at any minute and played on; paired-seed what-if runs with confidence ranges.
- **Football insight.** It answers "why did this moment matter": momentum before and after, the numbers that changed, the goal it led to, and how the result shifts without it.
- **Microsoft technology.** Azure AI Foundry, Microsoft Agent Framework, Azure Cosmos DB, Azure Blob Storage, Microsoft Entra ID, GitHub Actions and Projects.
- **Demo and completeness.** A public site with no sign-in, three languages, a visible agent trace, and a local mode that needs no keys.

## Testing instructions

Live site: https://pivot.in-stacks.com/?match=M-seed-29 (no sign-in). A private window works best, because the site remembers the language and match you used last.

1. The link opens the demo match, **Harbour City 3–1 Northgate Rovers**, on the page "The 3 moments that changed the course of this match". The momentum chart marks the moments ①②③; the cards below show each one's headline and **VERIFIED ✓**.
2. Moment ① (the 38′ red card) is open below the cards under **Why it turned**. Hover the underlined number to see the statistic it was checked against. Click an evidence chip such as **#678** to see the event on the mini pitch.
3. In the same panel under **What if…**, click **Remove 38′ red card**, then **Run simulation**. This scenario was computed in advance, so the result appears at once: win/draw/loss as played and with the change, 95 % ranges, and "Why it differs". Please stay with this scenario on the live server: it has 2 CPU cores, and a scenario that has not been run before takes about 10 minutes.
4. Under **Key moments**, click the **40′ goal** and play the clip; try **0.25×**.
5. Open **Set pieces & shots** and click the **40′ corner** to see who was in the box and how they were marked. The **Every shot** tab replays each shot.
6. Switch **EN / 中文 / ES** in the top bar. Under **Settings** you can switch between **Analyst** and **Fan** wording.
7. Open **More details** for the pitch, match stats, events and line-ups, then **Agent trace → Trace** to see every step the AI took for each moment, including drafts the Verifier sent back and why.
8. Optional: **Start demo** replays the match from 0′ with momentum drawn live. Other matches are in the match menu at the top.

To run it locally without any keys, follow "Run it locally" in the README (`PIVOT_PIPELINE=fake`). Everything works there, including every what-if scenario (about 30 seconds each on a laptop); explanations are template text in that mode.

All data is synthetic. What-if results are simulations of a synthetic match, not predictions.

## Technology

| Part | What we used |
|---|---|
| AI agents | Azure AI Foundry (gpt-4.1-mini); Microsoft Agent Framework workflow: Judge → Explainer ⇄ Verifier → template fallback; Comparator ⇄ Verifier for what-if text |
| Storage | Azure Cosmos DB (pivots, explanations per language and audience, agent traces, what-if results); Azure Blob Storage (simulated match library) |
| Sign-in | Microsoft Entra ID service principal with role assignments; no account keys stored |
| Back end | Python 3.12, FastAPI (REST and WebSocket), one process: simulator, momentum meter, change-point alarm, agents, what-if runner (process pool) |
| Front end | React, TypeScript, Vite |
| Hosting | Oracle Cloud VM (2 cores), deployed with Dokploy; Docker image |
| Engineering | GitHub Actions (lint, tests, contract check, secret scan), GitHub Projects board, Claude Code as coding assistant |
| Calibration data | Premier League 2023/24 and 2024/25 results (football-data.co.uk), StatsBomb open data (summary numbers only; raw files are not in the repository) |
