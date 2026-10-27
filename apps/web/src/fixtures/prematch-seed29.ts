// A made-up answer from `GET /api/matches/{id}/prematch` (#314) for the recorded Harbour City v
// Rovers match (eval/frozen/m-seed-29-before-ax44.json), in the shape #314 writes down. The tests
// render the pre-match blocks from it until the endpoint lands; the numbers are invented but agree
// with each other (the last five add up to the stats, the records to their splits).
import type { PreMatchReport } from "../data/prematch";

export const prematchSeed29: PreMatchReport = {
  match_id: "M-seed-29",
  matchday: 17,
  teams: {
    home: {
      overall: { played: 16, w: 8, d: 4, l: 4, gf: 25, ga: 17, pts: 28, ppg: 1.75, position: 4 },
      home_only: { played: 8, w: 5, d: 2, l: 1, gf: 15, ga: 7, pts: 17, ppg: 2.13 },
      away_only: { played: 8, w: 3, d: 2, l: 3, gf: 10, ga: 10, pts: 11, ppg: 1.38 },
      last5: [
        { matchday: 12, opponent: "Ashford", venue: "A", ft: [0, 2], ht: [0, 1], result: "L", scored_first: false, came_from_behind: false },
        { matchday: 13, opponent: "Kingsbridge", venue: "H", ft: [1, 1], ht: [1, 0], result: "D", scored_first: true, came_from_behind: false },
        { matchday: 14, opponent: "Eastmoor", venue: "A", ft: [3, 0], ht: [1, 0], result: "W", scored_first: true, came_from_behind: false },
        { matchday: 15, opponent: "Westfield", venue: "H", ft: [2, 2], ht: [2, 0], result: "D", scored_first: true, came_from_behind: false },
        { matchday: 16, opponent: "Salt Harbour", venue: "H", ft: [2, 1], ht: [0, 1], result: "W", scored_first: false, came_from_behind: true },
      ],
      last5_stats: {
        gf_avg: 1.6, ga_avg: 1.2, clean_sheets: 1, failed_to_score: 1, btts: 3, over_2_5: 3, scored_first: 3,
        ht_lead_won: 1, ht_lead_dropped: 2,
        goals_by_period: { "0-15": 1, "16-30": 2, "31-45": 1, "46-60": 2, "61-75": 1, "76-90": 1 },
        conceded_by_period: { "0-15": 0, "16-30": 1, "31-45": 1, "46-60": 1, "61-75": 1, "76-90": 2 },
        reds: 0, avg_rating: 6.9,
      },
      next_fixture: {
        competition: "Freeland Cup", stage: "Quarter-final", opponent: "Eastmoor", venue: "A", days_until: 3,
        importance: "high", rotation_risk: "high", fictional: true,
        rotation_note: "Cup quarter-final in 3 days: 3 regular starters begin on the bench today.",
      },
      usual_xi_today: { regulars_starting: 8, regulars_benched: ["h12", "h13", "h14"], newcomers: ["h09", "h10", "h11"] },
    },
    away: {
      overall: { played: 16, w: 7, d: 3, l: 6, gf: 22, ga: 21, pts: 24, ppg: 1.5, position: 7 },
      home_only: { played: 8, w: 5, d: 1, l: 2, gf: 14, ga: 8, pts: 16, ppg: 2.0 },
      away_only: { played: 8, w: 2, d: 2, l: 4, gf: 8, ga: 13, pts: 8, ppg: 1.0 },
      last5: [
        { matchday: 12, opponent: "Westfield", venue: "H", ft: [2, 0], ht: [1, 0], result: "W", scored_first: true, came_from_behind: false },
        { matchday: 13, opponent: "Lowmarsh", venue: "A", ft: [1, 2], ht: [1, 0], result: "L", scored_first: true, came_from_behind: false },
        { matchday: 14, opponent: "Kingsbridge", venue: "H", ft: [3, 1], ht: [1, 1], result: "W", scored_first: false, came_from_behind: true },
        { matchday: 15, opponent: "Ashford", venue: "A", ft: [0, 0], ht: [0, 0], result: "D", scored_first: false, came_from_behind: false },
        { matchday: 16, opponent: "Eastmoor", venue: "A", ft: [1, 3], ht: [0, 2], result: "L", scored_first: false, came_from_behind: false },
      ],
      last5_stats: {
        gf_avg: 1.4, ga_avg: 1.2, clean_sheets: 2, failed_to_score: 1, btts: 3, over_2_5: 3, scored_first: 2,
        ht_lead_won: 1, ht_lead_dropped: 1,
        goals_by_period: { "0-15": 0, "16-30": 1, "31-45": 2, "46-60": 1, "61-75": 2, "76-90": 1 },
        conceded_by_period: { "0-15": 1, "16-30": 0, "31-45": 2, "46-60": 1, "61-75": 1, "76-90": 1 },
        reds: 1, avg_rating: 6.7,
      },
      next_fixture: {
        competition: "Freeland League", stage: null, opponent: "Lowmarsh", venue: "H", days_until: 7,
        importance: "medium", rotation_risk: "low", fictional: false,
      },
      usual_xi_today: { regulars_starting: 11, regulars_benched: [], newcomers: [] },
    },
  },
  head_to_head: {
    all: { played: 6, home_w: 2, d: 2, away_w: 2 },
    at_this_ground: { played: 3, home_w: 2, d: 1, away_w: 0 },
    meetings: [
      { season: 2023, matchday: 9, venue_club: "club-hbc", ft: [1, 1], ht: [0, 1] },
      { season: 2023, matchday: 28, venue_club: "club-rov", ft: [2, 0], ht: [1, 0] },
      { season: 2024, matchday: 12, venue_club: "club-hbc", ft: [2, 1], ht: [1, 1] },
      { season: 2024, matchday: 31, venue_club: "club-rov", ft: [1, 1], ht: [0, 0] },
      { season: 2025, matchday: 5, venue_club: "club-hbc", ft: [3, 0], ht: [2, 0] },
      { season: 2025, matchday: 22, venue_club: "club-rov", ft: [2, 1], ht: [1, 1] },
    ],
  },
};
