// Scenario updates pushed on the match channel ("scenario.progress", "scenario.completed", or a
// plain "scenario"). The What-if Lab polls GET /api/scenarios/{id} anyway; a push just lands sooner.
export type ScenarioPush = { scenario_id: string } & Record<string, unknown>;

const listeners = new Set<(push: ScenarioPush) => void>();

export const isScenarioEnvelope = (type: string) => type === "scenario" || type.startsWith("scenario.");

/** Hands the payload to every open What-if run; ones without a scenario id are dropped. */
export function publishScenario(payload: unknown): void {
  const p = payload as { scenario_id?: unknown; scenario?: { scenario_id?: unknown } } | null;
  // Accept the Scenario itself, or `{ scenario: Scenario }`.
  const body = (typeof p?.scenario_id === "string" ? p : p?.scenario) as ScenarioPush | undefined;
  if (typeof body?.scenario_id !== "string") return;
  for (const fn of listeners) fn(body);
}

export function subscribeScenario(fn: (push: ScenarioPush) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
