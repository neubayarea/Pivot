// The match pictures (Bx12), ready to drop into a page: each component takes the data its hook
// (data/viz.ts) returns. `VizBox` shows a loading line or an error while the data is not there.
import type { ReactNode } from "react";
import type { VizState } from "../../data/viz";
import { useT } from "../../i18n";

export { default as ShotMap, shotRadius } from "./ShotMap";
export { default as Heatmap, heatCells } from "./Heatmap";
export { default as PassNetwork } from "./PassNetwork";
export { default as AveragePositions } from "./AveragePositions";
export { whoFrom } from "./pitch";
export { useAveragePositions, useHeatmaps, usePassNetwork, useShotMap } from "../../data/viz";

/** `children(data)` once loaded; a short line while loading or when the request failed. */
export function VizBox<T>({ state, children }: { state: VizState<T>; children: (data: T) => ReactNode }) {
  const t = useT();
  if (state.data) return <>{children(state.data)}</>;
  return <p className="viz-empty">{t(state.error ? "viz.error" : "viz.loading")}</p>;
}
