# Pivot: submission text

Text for the hackathon Projects page and submission form. Facts match the code, the [README](../../README.md) and the live site as checked on 2026-10-27. Update them together.

## Title

Pivot: the moments that changed the match, and why

## One-liner

Pivot finds the few moments that turned a football match. AI agents explain why each one mattered, and code checks every number they use. You can then replay the rest of the match with one decision changed, as an analyst or as a fan of either side, in English, Chinese or Spanish.

## Project description

**The problem.** Match stats tell you *what* happened: possession, shots, xG. They don't tell you which moments turned the game, or why. AI can write a fluent match summary, but it gets numbers wrong, and one wrong number is enough to lose a fan's trust.

**What Pivot does.** Each match page opens on *the 3 moments that changed the course of this match*, marked on a momentum chart. Pick one. Pivot shows what set it off (a goal, a card, a substitution), which way the game swung, and two or three sentences on why. Every number in those sentences is underlined and linked to the statistic it was checked against. Under each moment, **What if…** lets you change one thing and see how much it mattered: disallow a goal, remove a red card, cancel or move a substitution, or press higher.

In our demo match, Tessmouth United 4–3 Vantry Town, Sadoseno's 17′ penalty sets off the first turning point. Pivot replays the rest of the match 200 times with that goal disallowed and 200 times as played. Tessmouth's chance of winning goes from 34% to 50%, the most likely score from 1–1 to 1–0, and the 95% ranges for a Tessmouth win don't overlap.

**Why it matters.**
- **Fans** get the story of the match in plain words, from their own team's side, around the player they follow, in their own language.
- **Analysts** get the numbers behind each swing, the evidence events on the pitch, and a way to test "did that decision really decide it?" with a controlled replay instead of an opinion.
- Both can trust it, because no number reaches the screen without being recomputed from the match data.

**How it works.**
1. **Simulator.** We wrote a possession-chain match engine. It plays 22 rated players with per-second positions, and each coach has a style and preferred formation that set the team's tactics. Set pieces use Premier League positions. Every match is reproducible from a seed, and can be saved at any minute and played on from there.
2. **Momentum and pivot detection.** Per-minute momentum is built the way Opta builds the Premier League's match momentum: each team's most dangerous action of the minute, weighted towards the last few minutes. A two-sided change-point alarm (CUSUM) flags the minutes where the game swung and stayed swung. These become candidate turning points.
3. **Judge, Explainer and Verifier agents on Azure AI Foundry.** The detect pipeline is a Microsoft Agent Framework workflow.
   - A **Judge** (a mini model deployment) decides whether a candidate is a real turning point and how big it is.
   - An **Explainer** (a standard model deployment) writes a headline and up to three sentences. Every sentence cites match events, and every number cites a statistic.
   - The **Verifier** is ordinary code, not a model. It recomputes each number from the event log, and checks the score at that minute, which side momentum went to, and that the cited events belong to the moment.
   - A failed draft goes back to the Explainer with the problems listed. After three failures, or if the model is slow or down, a plain summary built only from checked numbers is shown and marked "Auto summary".
4. **Personalisation.** Each explanation is rewritten for **Analyst** or **Fan**, from the side of the team you pick, around the player you follow, in **English, Chinese or Spanish**. Chinese and Spanish are translations of the checked English version, and every version, translations included, goes through the same Verifier. Following a player also brings up the player's card: rating, goals, shots, heatmap, and their part in each turning point.
5. **What-if replays.** The match is saved at the turning point and played on N times as it was and N times with the change. Run *i* of both groups uses the same random seed, so the only difference within a pair is the change. Pivot shows win/draw/loss with 95% Wilson ranges and the most likely scores. A **Comparator** agent explains where the difference comes from, and the Verifier only allows "more likely" or "clear difference" when the numbers support it.

Around the turning points, the match page has:
- a pre-match preview: table, form, head-to-head, storylines and each coach's plan;
- a smooth pitch replay that draws passes, shots, tackles and cards as they happen;
- clips of every key moment and set piece, showing how many attackers and defenders were in the box and how they were marked;
- a shot map, heatmaps, a pass network, average positions and 23 team stats per half;
- an agent trace page with every step the AI took, including drafts the Verifier sent back.

**Microsoft technology.**
- **Azure AI Foundry**: the model deployments behind the Judge, Explainer, Comparator and translations.
- **Microsoft Agent Framework**: the detect workflow, with the rewrite loop and fallback as edges.
- **Azure Cosmos DB**: everything the AI produced (verdicts, explanations per audience, team, player and language, agent traces, what-if results), so a restart or a repeated question doesn't call the model again.
- **Azure Blob Storage**: the library of simulated match files.
- **Microsoft Entra ID**: a service principal with role assignments, so no account keys are stored.
- **GitHub Actions and Projects**: CI and planning.

**Synthetic data, and the way to real matches.** As the rules require, every club, player, coach and match is synthetic, generated by our simulator. Real Premier League numbers were used only to calibrate it. The README's realism scorecard lists where it matches real football and where it still misses. Everything after the simulator reads one thing: a plain list of match events (time, team, player, location, type, outcome). To run Pivot on real matches you would write one adapter, turning a provider's feed (StatsBomb open data first, then a licensed live event feed) into those events. The momentum meter, agents, Verifier and personalisation would stay as they are, and what-if replays would start from the real match state at that minute. That adapter is not written yet.

**Try it:** https://pivot.in-stacks.com (no sign-in) · **Code:** https://github.com/neubayarea/Pivot · **Video:** https://youtu.be/HGJ11chiHKg

## How it maps to the judging criteria

- **Innovation.** Not a summary but a ranked set of turning points. Each one has a checked explanation and a counterfactual replay that measures how much it changed the result.
- **Technical implementation.** A multi-agent workflow with a rewrite loop and a guaranteed fallback. A deterministic Verifier for every number and claim. A reproducible simulator that can be saved at any minute. Paired-seed what-if runs with confidence ranges.
- **Football insight.** It answers "why did this moment matter": momentum before and after, the numbers that changed, the events behind them, and how the result shifts without it.
- **Microsoft technology.** Azure AI Foundry, Microsoft Agent Framework, Azure Cosmos DB, Azure Blob Storage, Microsoft Entra ID, GitHub Actions and Projects.
- **Demo and completeness.** A public site with no sign-in, 20 simulated matches, personalisation by audience, team, player and language, a visible agent trace, and a local mode that needs no keys.

## Testing instructions

Live site: https://pivot.in-stacks.com/ (no sign-in). It opens the demo match, **Tessmouth United 4–3 Vantry Town** (`?match=S2026-27-TES-VAN`). A private window works best, because the site remembers your language, viewer settings and last match.

The match page has six tabs: **Overview, What if, Replay, Stats, Line-ups, Preview**. Each tab has its own link (`?tab=overview|whatif|replay|stats|lineups|preview`).

1. **Overview**: "The 3 moments that changed the course of this match", with a momentum chart marked ① 12′ ② 50′ ③ 88′.
2. Card **① 12′, "Vantry Town gains control with sharp attack"** is open under the list. Under **Why it turned**, hover an underlined number to see the statistic it was checked against. Click an evidence chip such as **#329** to see the event on the mini pitch.
3. In the top bar, switch **Analyst → Fan**, pick **♥ Tessmouth United** and click **① 12′**. The same moment is rewritten from Tessmouth's side ("Tessmouth United lose control after Vantry's goal"). Try **中文** and **ES**. If a version hasn't been written yet, the analyst one shows for a few seconds first.
4. Pick **★ D. Sahaltessen** (three goals). Open **Stats** for his player card, the team's numbers, the shot map, heatmaps and pass network.
5. Open the **What if** tab. Under **Turning point 1, 12′**, click **Disallow 17′ goal**, then **Run simulation**. It was computed in advance, so it shows at once: Tessmouth's chance of winning goes from 34% to 50%. Please stay with the precomputed chips on the live server: it has 2 CPU cores, and a new scenario takes minutes.
6. Under **Key moments**, play any goal as a clip. Under **Set pieces & shots**, open the **7′ free kick** to see who was in the box, how they were marked and who stood in the wall.
7. **Replay**: **Start demo** replays the match from 0′ with momentum drawn live and turning points appearing as they happen. Add `&from=75` to the link to start just before the 75′ goal.
8. **Preview** and **Line-ups**: form, the last five games, home and away records, both line-ups and each coach's plan.
9. **AI log** in the top bar: every step the AI took for each moment, with the model, the time it took and the Verifier's verdict.

To run it locally without any keys, follow "Run it locally" in the README (`PIVOT_PIPELINE=fake`). Everything works there, including every what-if (about 30 seconds each on a laptop). Explanations are template text in that mode.

All data is synthetic. What-if results are simulations of a synthetic match, not predictions.

## Technology

| Part | What we used |
|---|---|
| AI agents | Azure AI Foundry (a standard and a mini model deployment); Microsoft Agent Framework workflow: Judge → Explainer ⇄ Verifier → template fallback; Comparator ⇄ Verifier for what-if text; translator ⇄ Verifier for Chinese and Spanish |
| Storage | Azure Cosmos DB (turning points, explanations per language, audience, team and player, agent traces, what-if results); Azure Blob Storage (simulated match library) |
| Sign-in | Microsoft Entra ID service principal with role assignments; no account keys stored |
| Back end | Python 3.12, FastAPI (REST and WebSocket), one process: simulator, momentum meter, change-point alarm, agents, what-if runner (process pool) |
| Front end | React, TypeScript, Vite |
| Hosting | Oracle Cloud VM (2 cores), deployed with Dokploy; Docker image |
| Engineering | GitHub Actions (lint, tests, contract check, secret scan), GitHub Projects board, Claude Code as coding assistant |
| Calibration data | Premier League 2023/24 and 2024/25 results (football-data.co.uk), StatsBomb open data (summary numbers only; raw files are not in the repository) |
