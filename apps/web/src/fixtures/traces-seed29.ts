// The detect chains of M-seed-29 as the live API served them on 10/25
// (GET https://pivot.in-stacks.com/api/matches/M-seed-29/traces, What-if chains left out): p39 is
// sent back three times and ends with the template; p69 and p89 pass first time. Used by the S4 tests.
// A recording from before B06-opta (10/26): the demo's pivots are now p37, p66 and p79; these ids stay
// as they were served, since the tests only read how chains are grouped and shown.
import type { AgentTrace } from "@pivot/contracts";

export const SEED29_TRACES: AgentTrace[] = [
  {
    "trace_id": "detect:M-seed-29:39:d1:0",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 0,
    "match_id": "M-seed-29",
    "agent": "judge",
    "model": "mini",
    "prompt_hash": "78e49f746ba3",
    "input_ref": "M-seed-29:p39",
    "output_summary": "is_pivot=true severity=3: Northgate Rovers received a card and dropped to ten men, Harbour City scored and momentum stayed strongly with them.",
    "latency_ms": 2252,
    "tokens": 6296,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:1",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 1,
    "match_id": "M-seed-29",
    "agent": "explainer",
    "model": "standard",
    "prompt_hash": "ecbe894895d2",
    "input_ref": "M-seed-29:p39",
    "output_summary": "Lisais' red card shifts momentum to Harbour City",
    "latency_ms": 2527,
    "tokens": 5408,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:2",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 2,
    "match_id": "M-seed-29",
    "agent": "verifier",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p39",
    "output_summary": "number_mismatch",
    "latency_ms": 86,
    "tokens": 0,
    "status": "rejected",
    "verdict": {
      "passed": false,
      "issues": [
        {
          "code": "number_mismatch",
          "message": "The number 10 in sentence 1 has no matching claim.",
          "sentence_index": 0
        }
      ]
    }
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:3",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 3,
    "match_id": "M-seed-29",
    "agent": "explainer",
    "model": "standard",
    "prompt_hash": "ecbe894895d2",
    "input_ref": "M-seed-29:p39",
    "output_summary": "invalid output (1 schema errors: Input should be 'possession_pct', 'passes', 'pass_accuracy_pct', 'passes_final_third', 'box_entries', 'shots', 'shots_on_target', 'xg', 'threat_total', 'pressures', 'tackles_won', 'interceptions', 'duels_won', 'turnovers', 'momentum_avg', 'line_height_m', 'team_width_m', 'press_distance_m', 'distance_covered_km', 'progressive_passes', 'ppda', 'xa' or 'field_tilt_pct')",
    "latency_ms": 2589,
    "tokens": 5747,
    "status": "retried",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:4",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 4,
    "match_id": "M-seed-29",
    "agent": "verifier",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p39",
    "output_summary": "schema_invalid",
    "latency_ms": 36,
    "tokens": 0,
    "status": "rejected",
    "verdict": {
      "passed": false,
      "issues": [
        {
          "code": "schema_invalid",
          "message": "1 schema errors: Input should be 'possession_pct', 'passes', 'pass_accuracy_pct', 'passes_final_third', 'box_entries', 'shots', 'shots_on_target', 'xg', 'threat_total', 'pressures', 'tackles_won', 'interceptions', 'duels_won', 'turnovers', 'momentum_avg', 'line_height_m', 'team_width_m', 'press_distance_m', 'distance_covered_km', 'progressive_passes', 'ppda', 'xa' or 'field_tilt_pct'",
          "sentence_index": null
        }
      ]
    }
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:5",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 5,
    "match_id": "M-seed-29",
    "agent": "explainer",
    "model": "standard",
    "prompt_hash": "ecbe894895d2",
    "input_ref": "M-seed-29:p39",
    "output_summary": "invalid output (1 schema errors: Input should be 'possession_pct', 'passes', 'pass_accuracy_pct', 'passes_final_third', 'box_entries', 'shots', 'shots_on_target', 'xg', 'threat_total', 'pressures', 'tackles_won', 'interceptions', 'duels_won', 'turnovers', 'momentum_avg', 'line_height_m', 'team_width_m', 'press_distance_m', 'distance_covered_km', 'progressive_passes', 'ppda', 'xa' or 'field_tilt_pct')",
    "latency_ms": 2825,
    "tokens": 5919,
    "status": "retried",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:6",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 6,
    "match_id": "M-seed-29",
    "agent": "verifier",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p39",
    "output_summary": "schema_invalid",
    "latency_ms": 49,
    "tokens": 0,
    "status": "rejected",
    "verdict": {
      "passed": false,
      "issues": [
        {
          "code": "schema_invalid",
          "message": "1 schema errors: Input should be 'possession_pct', 'passes', 'pass_accuracy_pct', 'passes_final_third', 'box_entries', 'shots', 'shots_on_target', 'xg', 'threat_total', 'pressures', 'tackles_won', 'interceptions', 'duels_won', 'turnovers', 'momentum_avg', 'line_height_m', 'team_width_m', 'press_distance_m', 'distance_covered_km', 'progressive_passes', 'ppda', 'xa' or 'field_tilt_pct'",
          "sentence_index": null
        }
      ]
    }
  },
  {
    "trace_id": "detect:M-seed-29:39:d1:7",
    "chain_id": "detect:M-seed-29:39:d1",
    "step": 7,
    "match_id": "M-seed-29",
    "agent": "template",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p39",
    "output_summary": "A card changes the game",
    "latency_ms": 191,
    "tokens": 0,
    "status": "degraded",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:69:d1:0",
    "chain_id": "detect:M-seed-29:69:d1",
    "step": 0,
    "match_id": "M-seed-29",
    "agent": "judge",
    "model": "mini",
    "prompt_hash": "78e49f746ba3",
    "input_ref": "M-seed-29:p69",
    "output_summary": "is_pivot=true severity=2: Harbour City's tactical shift and substitutions led to sustained momentum loss and Northgate Rovers gaining control despite being down a player.",
    "latency_ms": 1449,
    "tokens": 6453,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:69:d1:1",
    "chain_id": "detect:M-seed-29:69:d1",
    "step": 1,
    "match_id": "M-seed-29",
    "agent": "explainer",
    "model": "standard",
    "prompt_hash": "ecbe894895d2",
    "input_ref": "M-seed-29:p69",
    "output_summary": "Harbour City drops line and press",
    "latency_ms": 1528,
    "tokens": 5467,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:69:d1:2",
    "chain_id": "detect:M-seed-29:69:d1",
    "step": 2,
    "match_id": "M-seed-29",
    "agent": "verifier",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p69",
    "output_summary": "pass",
    "latency_ms": 53,
    "tokens": 0,
    "status": "ok",
    "verdict": {
      "passed": true,
      "issues": []
    }
  },
  {
    "trace_id": "detect:M-seed-29:89:d1:0",
    "chain_id": "detect:M-seed-29:89:d1",
    "step": 0,
    "match_id": "M-seed-29",
    "agent": "judge",
    "model": "mini",
    "prompt_hash": "78e49f746ba3",
    "input_ref": "M-seed-29:p89",
    "output_summary": "is_pivot=true severity=2: Northgate Rovers scored to reduce the deficit and momentum swung sharply and stayed with them for several minutes.",
    "latency_ms": 1221,
    "tokens": 6377,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:89:d1:1",
    "chain_id": "detect:M-seed-29:89:d1",
    "step": 1,
    "match_id": "M-seed-29",
    "agent": "explainer",
    "model": "standard",
    "prompt_hash": "ecbe894895d2",
    "input_ref": "M-seed-29:p89",
    "output_summary": "Anlitesov's goal shifts momentum late",
    "latency_ms": 1718,
    "tokens": 5394,
    "status": "ok",
    "verdict": null
  },
  {
    "trace_id": "detect:M-seed-29:89:d1:2",
    "chain_id": "detect:M-seed-29:89:d1",
    "step": 2,
    "match_id": "M-seed-29",
    "agent": "verifier",
    "model": null,
    "prompt_hash": null,
    "input_ref": "M-seed-29:p89",
    "output_summary": "pass",
    "latency_ms": 47,
    "tokens": 0,
    "status": "ok",
    "verdict": {
      "passed": true,
      "issues": []
    }
  }
];
