// The coach's plan (Ax60): each side's coach, shape and starting tactics side by side, from the
// TeamTactics the API sends and the page used to drop (#276). Match sites show a formation and stop
// there; this reads the settings the simulator plays by. Changes during the match arrive as events.
import type { TeamTactics as Tactics } from "@pivot/contracts";
import { useMatch, type Side } from "../data/match";
import { usePrefs, type MessageKey } from "../i18n";
import Card from "./Card";
import "../styles/prematch.css";

const SIDES: Side[] = ["home", "away"];

/** Settings that run from one end to the other; the meter fills up to the chosen step. */
const SCALES = [
  ["press", ["low", "mid", "high"]],
  ["line_height", ["low", "mid", "high"]],
  ["width", ["narrow", "normal", "wide"]],
  ["tempo", ["slow", "normal", "fast"]],
  ["passing", ["short", "mixed", "direct"]],
] as const satisfies readonly (readonly [keyof Tactics, readonly string[]])[];
const LANES = ["left", "centre", "right"] as const;
const FLAGS = ["counter_attack", "offside_trap", "time_wasting"] as const satisfies readonly (keyof Tactics)[];

export default function TeamTactics() {
  const { preMatch, teams, sheets, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  if (!preMatch) return null;
  const { plans } = preMatch;
  const fan = prefs.audience === "fan";
  const label = (key: string) => t((fan ? `plan.fan.${key}` : `plan.${key}`) as MessageKey);
  const value = (key: string, v: string) => t(`plan.${key}.${v}` as MessageKey);

  return (
    <Card title={label("title")} note={t("plan.note")} className="plan">
      <div className="plan-heads">
        {SIDES.map((s) => {
          const { coach } = plans[s];
          const formation = sheets?.[s].formation ?? coach.preferred_formation;
          return (
            <div key={s} className={`plan-head ${s}`}>
              <span className="plan-team">{teams[s].name}</span>
              <span className="plan-shape">{formation}</span>
              <span className="plan-coach">
                {coach.name} · <span className={`plan-style ${coach.style}`}>{t(`plan.style.${coach.style}`)}</span>
              </span>
              {formation !== coach.preferred_formation && (
                <small className="muted">{t("plan.usually", { formation: coach.preferred_formation })}</small>
              )}
            </div>
          );
        })}
      </div>

      <div className="plan-rows">
        {SCALES.map(([key, steps]) => (
          <div key={key} className="plan-row">
            <span className="nm">{label(key)}</span>
            {SIDES.map((s) => {
              const v = plans[s].tactics[key];
              const at = (steps as readonly string[]).indexOf(v);
              return (
                <span key={s} className={`plan-val ${s}`}>
                  <span className="plan-meter" role="img" aria-label={`${at + 1}/${steps.length}`}>
                    {steps.map((step, i) => <i key={step} className={i <= at ? "on" : undefined} />)}
                  </span>
                  <span className="plan-word">{value(key, v)}</span>
                </span>
              );
            })}
          </div>
        ))}
        <div className="plan-row">
          <span className="nm">{label("attack_focus")}</span>
          {SIDES.map((s) => {
            const v = plans[s].tactics.attack_focus;
            return (
              <span key={s} className={`plan-val ${s}`}>
                {/* Three lanes seen from the team's own goal; balanced lights all three. */}
                <span className="plan-meter lanes" role="img" aria-label={value("attack_focus", v)}>
                  {LANES.map((l) => <i key={l} className={v === l || v === "balanced" ? "on" : undefined} />)}
                </span>
                <span className="plan-word">{value("attack_focus", v)}</span>
              </span>
            );
          })}
        </div>
      </div>

      <div className="plan-cols">
        {SIDES.map((s) => {
          const tx = plans[s].tactics;
          const flags = FLAGS.filter((f) => tx[f]);
          const sp = tx.set_pieces;
          return (
            <div key={s} className={`plan-col ${s}`}>
              {flags.length > 0 && (
                <p className="plan-flags">{flags.map((f) => <span key={f} className="stamp line">{t(`plan.flag.${f}`)}</span>)}</p>
              )}
              <h4>{t("plan.setPieces")}</h4>
              <ul className="plan-sp">
                <li>
                  <b>{t("plan.sp.corners")}</b>{" "}
                  {t("plan.sp.cornersLine", {
                    delivery: value("delivery", sp.corner_delivery), target: value("target", sp.corner_target), n: sp.players_forward_on_corners,
                  })}
                </li>
                <li>
                  <b>{t("plan.sp.defending")}</b>{" "}
                  {t("plan.sp.defendingLine", { how: value("defence", sp.corner_defence), n: sp.players_back_on_corners })}
                </li>
                <li>
                  <b>{t("plan.sp.freeKicks")}</b> {value("fk", sp.free_kick_style)}
                </li>
              </ul>
              {tx.instructions.length > 0 && (
                <>
                  <h4>{t("plan.instructions")}</h4>
                  <ul className="plan-sp">
                    {tx.instructions.map((ins, i) => (
                      <li key={i}>
                        <b>{playerName(ins.player_id)}</b>{" "}
                        {ins.instruction === "man_mark" && ins.target_player_id
                          ? t("plan.ins.markWho", { who: playerName(ins.target_player_id) })
                          : t(`plan.ins.${ins.instruction}`)}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
