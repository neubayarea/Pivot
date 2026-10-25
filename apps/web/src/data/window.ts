// The stretch of match the S2 timeline covers (Cx3): two minutes either side of the pivot, widened
// to take in every evidence event with a little room, but never more than six minutes either side.
export const BASE_S = 2 * 60;
export const MARGIN_S = 30;
export const MAX_SIDE_S = 6 * 60;

/** Window in match seconds, on whole minutes, around a pivot at `minute` with evidence at `times` (seconds). */
export function evidenceWindow(minute: number, times: number[]): [number, number] {
  const at = minute * 60;
  const lo = Math.min(at - BASE_S, ...times.map((t) => t - MARGIN_S));
  const hi = Math.max(at + BASE_S, ...times.map((t) => t + MARGIN_S));
  const from = Math.max(0, at - MAX_SIDE_S, Math.floor(lo / 60) * 60);
  const to = Math.min(at + MAX_SIDE_S, Math.ceil(hi / 60) * 60);
  return [from, to];
}

export const inWindow = ([from, to]: [number, number], t: number) => t >= from && t <= to;
