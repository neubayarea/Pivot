# Pivot: submission text

Text for the hackathon submission form. Facts and numbers match the [README](../../README.md); update both together.

## Title

Pivot: find the moment a match turned, explain why, and replay it with one thing changed

## One-liner

Pivot spots the turning points of a football match, has AI agents explain why each one mattered with every number checked by code, and lets fans replay the rest of the match with one decision changed to see how much it really mattered.

## Project description

**The problem.** Commentary says *that* a moment was big, rarely *why* or by how much. AI can write fluent match summaries, but it is unreliable with numbers, and a wrong number in front of fans destroys trust.

**What Pivot does.** Pivot watches a match minute by minute and does three things:

1. **Finds the pivots.** A momentum meter (an exponentially weighted threat difference) feeds a CUSUM change-point alarm. The alarm flags the minutes where the game swung and stayed swung.
2. **Explains them.** A Judge agent decides whether a candidate is a real turning point. An Explainer agent writes a short explanation in which every sentence cites match events and every number cites a statistic. A deterministic Verifier recomputes each number from the event log and checks the score, the direction of momentum and the cited events. Failed drafts go back with the problems listed. After three failures a correct template is shown instead, so fans never see a wrong number or an error. Explanations come in Analyst or Fan style, in English, Chinese and Spanish.
3. **Tests them.** In the What-if Lab a fan asks "what if the red card had not been given?". Pivot saves the match at that minute and plays it on hundreds of times with and without the change, using paired random seeds. It shows the win/draw/loss shift with 95 % Wilson intervals, and a Comparator agent explains the difference. The Verifier blocks any wording the numbers do not support.

**Technology.** Azure AI Foundry (gpt-4.1-mini) runs the agents. The detect pipeline is a Microsoft Agent Framework workflow with the rewrite loop and fallbacks built in. Azure Cosmos DB stores explanations, agent traces and what-if results, so answers survive restarts and repeat questions are instant. Azure Blob Storage holds the simulated match library. The server signs in through Microsoft Entra ID with no stored keys. CI runs on GitHub Actions.

**Football insight.** Matches come from our own possession-chain simulator with 22 rated players and per-second tracking. All of it is synthetic, with no real clubs or players. We calibrated it against real Premier League numbers: 29 of 44 checks fall within tolerance, including goals (2.9 vs 3.1 per match), shots (25.4 vs 26.8), fouls and pass height. It also reproduces game-state effects: after a red card the 11-man side's share of shots rises to 0.77, against 0.72 in real Premier League matches with a red card. Where it still misses (pass accuracy, clearances, interceptions), we publish that too.

**How it maps to the judging criteria.**
- **Innovation:** verified, counterfactual explanations instead of plain summaries.
- **Technical implementation:** a multi-agent workflow, deterministic verification and a reproducible simulator.
- **Football insight:** it answers "why does this moment matter", in numbers.
- **Microsoft technology:** Foundry, Agent Framework, Cosmos DB, Blob Storage, Entra ID and GitHub.
- **Demo and completeness:** a live site, a local mode that needs no keys, and every number traceable to an event.

## Testing instructions

Live site: https://pivot.in-stacks.com/?match=M-seed-29 (no sign-in; a private window is best).

1. The link opens the demo match, Harbour City 3–1 Northgate Rovers. Click **Start demo**, then **60×**, to watch momentum and the pivots appear live.
2. Click the **85′** pivot. Read "Why it turned" and click an evidence number (for example `#1553`) to see the event on the pitch.
3. Switch **Analyst / Fan** and **EN / 中文 / ES** in the top bar.
4. Open the **40′** pivot (the red card), click **What if…**, choose **Remove 38′ red card** with **200** runs, and click **Run simulation**. This result was computed in advance and appears instantly. Please avoid other scenarios on the live server: it has 2 CPU cores and new scenarios take several minutes.
5. Optional: the raw agent trace for a pivot is at https://pivot.in-stacks.com/api/pivots/M-seed-29:p89/traces.

To run locally without any keys, follow "Run it locally" in the README (`PIVOT_PIPELINE=fake`). Everything works, including every what-if scenario. Explanations are template text in that mode.

All data is synthetic. What-if results are simulations, not predictions.
