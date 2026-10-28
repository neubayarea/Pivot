import { useId, useRef, type ReactNode } from "react";
import type { Claim, StatRef } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { useMatch } from "../data/match";
import { isMessageKey, useT, type T } from "../i18n";

const metricLabel = (m: StatRef["metric"], t: T) => {
  const key = `metric.${m}`;
  return isMessageKey(key) ? t(key) : m[0].toUpperCase() + m.slice(1).replaceAll("_", " ");
};

export function formatValue(c: Claim): string {
  if (c.unit === "pct") return `${c.value}%`;
  if (c.unit === "index") return `${c.value > 0 ? "+" : c.value < 0 ? "−" : ""}${Math.abs(c.value).toFixed(2)}`;
  return String(c.value);
}

/** Puts the tooltip above its number (below when there is no room), kept inside the window, so a
 * panel that clips its overflow cannot cut it off. */
function place(anchor: HTMLElement, tip: HTMLElement) {
  const r = anchor.getBoundingClientRect();
  const w = tip.offsetWidth;
  const h = tip.offsetHeight;
  const gap = 8;
  const left = Math.max(gap, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - gap));
  const top = r.top - h - gap >= gap ? r.top - h - gap : r.bottom + gap;
  tip.style.left = `${Math.round(left)}px`;
  tip.style.top = `${Math.round(top)}px`;
  tip.style.visibility = "visible";
}

/** A number with its source: hover or focus shows where it was read from (metric, team, window), in words. A "from" claim
 * (the earlier value of a "4 to 14" figure) adds its own window and value. */
export default function Sourced({ claim, from, className = "", children }: { claim: Claim; from?: Claim; className?: string; children: ReactNode }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { span } = useClock();
  const { metric, team, player_id, window: statWindow } = claim.stat_ref;
  const tip = useId();
  const anchor = useRef<HTMLSpanElement>(null);
  const tipEl = useRef<HTMLSpanElement>(null);
  const show = () => {
    const a = anchor.current;
    const b = tipEl.current;
    if (!a || !b) return;
    place(a, b);
    // The tip is fixed to the window; scrolling would leave it behind, so it goes until the next hover.
    window.addEventListener("scroll", hide, { capture: true, once: true });
  };
  const hide = () => {
    if (tipEl.current) tipEl.current.style.visibility = "";
  };
  return (
    <span ref={anchor} className={`src ${className}`.trim()} tabIndex={0} aria-describedby={tip}
      onMouseEnter={show} onFocus={show} onMouseLeave={hide} onBlur={hide}>
      {children}
      <span ref={tipEl} className="tip" role="tooltip" id={tip}>
        <b>{metricLabel(metric, t)}</b>
        <span>{teams[team].name}{player_id ? ` · ${playerName(player_id)}` : ""}</span>
        {from && (
          <span>
            {span(from.stat_ref.window)} · {formatValue(from)}
          </span>
        )}
        <span>
          {span(statWindow)} · {formatValue(claim)}
        </span>
      </span>
    </span>
  );
}
