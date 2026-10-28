// The match clock a viewer reads (G2, Ax27). Every time in the data is elapsed time since kick-off,
// stoppage included (`t` in seconds; a pivot's or metric's `minute` is t // 60), so after three
// minutes of first-half stoppage elapsed minute 69 is 67′ on the clock. The page always shows the
// clock: 1′ for the first minute, 45+2′ in added time. Same rules as pivot_core's clock_label and
// label_at, so a pivot, its chips and the event list all read the same minute.
import { useContext } from "react";
import { MatchContext } from "./view";

export type PeriodStart = { period: number; start_t: number };

const BASE: Record<number, number> = { 1: 0, 2: 45, 3: 90, 4: 105 };
const LENGTH: Record<number, number> = { 1: 45, 2: 45, 3: 15, 4: 15 };
/** When the periods are not known (the fixture): no stoppage, the second half kicks off at 45:00. */
export const PLAIN_PERIODS: PeriodStart[] = [{ period: 1, start_t: 0 }, { period: 2, start_t: 45 * 60 }];

function periodAt(periods: PeriodStart[], t: number): [number, number] {
  const started = periods.filter((p) => p.start_t <= t).sort((a, b) => a.start_t - b.start_t).at(-1);
  return started ? [started.period, t - started.start_t] : [1, t];
}

/** "64", "45+2" or "PEN" at elapsed second `t`; the page adds the ′. */
export function minuteAt(periods: PeriodStart[], t: number): string {
  const [period, periodT] = periodAt(periods, t);
  if (period === 5) return "PEN";
  const m = Math.floor(periodT / 60);
  return m < LENGTH[period] ? `${BASE[period] + m + 1}` : `${BASE[period] + LENGTH[period]}+${m - LENGTH[period] + 1}`;
}

/** An elapsed minute from the data (pivot, metric, window edge), read at its first second like the overlay. */
export const minuteLabel = (periods: PeriodStart[], minute: number) => minuteAt(periods, minute * 60);

const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** Running clock "63:20": 45:00 when the second half kicks off. Added time counts on from the
 * period's end like the minute labels do (Ax83): "45+1:30", "90+8:37" (the 9th added minute, 90+9′). */
export function clockAt(periods: PeriodStart[], t: number): string {
  const [period, periodT] = periodAt(periods, t);
  const s = Math.max(0, Math.floor(periodT));
  const length = LENGTH[period];
  if (length === undefined) return mmss(Math.floor(120 * 60 + s));
  if (s >= length * 60) return `${BASE[period] + length}+${String(Math.floor((s - length * 60) / 60))}:${String((s - length * 60) % 60).padStart(2, "0")}`;
  return mmss(BASE[period] * 60 + s);
}

/** An event's own minute as the event list shows it, without the quote: "63'" -> "63". */
export const eventMinute = (e: { clock_label: string }) => e.clock_label.replace(/'$/, "");

/** The clock of the match on screen (plain periods outside a match, e.g. in a component test). */
export function useClock() {
  const periods = useContext(MatchContext)?.match.periods ?? PLAIN_PERIODS;
  return {
    periods,
    minute: (minute: number) => minuteLabel(periods, minute),
    at: (t: number) => minuteAt(periods, t),
    clock: (t: number) => clockAt(periods, t),
    /** A right-open window of elapsed minutes, [55, 60) -> "56′–60′" with no stoppage before it. */
    span: ([from, to]: readonly [number, number]) => `${minuteLabel(periods, from)}′–${minuteLabel(periods, Math.max(from, to - 1))}′`,
  };
}
