// Numbers in the analyst's report (C19 hotfix): one formatter for all of them, safe for the nulls a
// live match sends for what it has not reached yet. Null or NaN reads "–".
import { isNum } from "../../data/analysis";

export const DASH = "–";
/** `v` to `d` decimals. */
export const num = (v: number | null | undefined, d = 2) => (isNum(v) ? v.toFixed(d) : DASH);
/** `v` as a whole per cent of 100 ("56%"). */
export const pct = (v: number | null | undefined) => (isNum(v) ? `${Math.round(v)}%` : DASH);
/** A share from 0 to 1 as a whole per cent ("0.49" -> "49%"). */
export const share = (v: number | null | undefined) => (isNum(v) ? `${Math.round(v * 100)}%` : DASH);
/** A count ("14"). */
export const count = (v: number | null | undefined) => (isNum(v) ? String(Math.round(v)) : DASH);
/** `v`, or 0 for a length, a share or a bar. */
export const or0 = (v: number | null | undefined) => (isNum(v) ? v : 0);
