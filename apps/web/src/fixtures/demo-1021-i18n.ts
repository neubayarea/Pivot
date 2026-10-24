// Chinese and Spanish versions of the demo-1021 explanations, standing in for what the Explainer
// writes when the API is asked for `?lang=zh|es` (A11). Same sentences in the same order, so the
// evidence chips and checked figures line up with the English ones. Names stay as in the data.
import type { Pivot1 as Pivot } from "@pivot/contracts";
import type { Lang } from "../i18n";

type Version = { headline: string; sentences: string[] };

const NARRATIVES: Record<string, Partial<Record<Lang, Version>>> = {
  "pv-38": {
    zh: {
      headline: "一张红牌，比赛倒向 Harbour City",
      sentences: [
        "Petrov 被红牌罚下，Northvale 最后 52 分钟只能十人应战。",
        "红牌之后的十分钟里，Harbour City 的控球率从 48% 升到 61%。",
        "他们进入禁区的次数从 2 次增至 7 次，三分钟后 Okafor 破门。",
      ],
    },
    es: {
      headline: "La roja inclinó el partido hacia Harbour City",
      sentences: [
        "La roja a Petrov dejó a Northvale con diez durante los últimos 52 minutos.",
        "La posesión de Harbour City pasó del 48% al 61% en los diez minutos posteriores a la expulsión.",
        "Sus llegadas al área pasaron de 2 a 7, y Okafor marcó tres minutos después.",
      ],
    },
  },
  "pv-63": {
    zh: {
      headline: "一次换人，左路攻守易势",
      sentences: [
        "换人之后，Harbour City 在前场三区的传球从 9 次降到 3 次。",
        "Northvale 在右路的对抗中 8 战 6 胜，那里原本是 Moreau 接球的通道。",
        "Northvale 的逼抢从 6 次增至 12 次，扳平进球随之而来。",
      ],
    },
    es: {
      headline: "El cambio le dio la vuelta a la banda izquierda",
      sentences: [
        "Tras el cambio, los pases de Harbour City en el último tercio bajaron de 9 a 3.",
        "Northvale ganó 6 de 8 duelos por su banda derecha, donde Moreau había sido la vía de salida.",
        "Las presiones de Northvale subieron de 6 a 12, y llegó su empate.",
      ],
    },
  },
  "pv-74": {
    zh: {
      headline: "改打三中卫，Harbour City 稳住阵脚",
      sentences: [
        "Harbour City 改打三中卫，Northvale 的逼抢从 12 次降到 5 次。",
        "后场出球 16 次中有 14 次找到队友，之前是 11 次中有 6 次。",
      ],
    },
    es: {
      headline: "La línea de tres le dio aplomo a Harbour City",
      sentences: [
        "Harbour City pasó a defender con línea de tres, y las presiones de Northvale bajaron de 12 a 5.",
        "Los pases desde la defensa encontraron a un compañero 14 de 16 veces, frente a 6 de 11 antes.",
      ],
    },
  },
};

/** S2 before/after row labels, keyed by the English label. */
const ROW_LABELS: Record<string, Partial<Record<Lang, string>>> = {
  "HCY possession": { zh: "HCY 控球率", es: "Posesión de HCY" },
  "HCY box entries": { zh: "HCY 进入禁区", es: "Llegadas al área de HCY" },
  "HCY final-third passes": { zh: "HCY 前场三区传球", es: "Pases de HCY en el último tercio" },
  "NVR duels won": { zh: "NVR 对抗成功", es: "Duelos ganados de NVR" },
  "NVR pressures": { zh: "NVR 逼抢", es: "Presiones de NVR" },
  "HCY pass accuracy from defence": { zh: "HCY 后场出球成功率", es: "Precisión de pase de HCY desde atrás" },
  "Momentum (avg)": { zh: "平均势头", es: "Impulso (media)" },
};

/** The pivot as the API would serve it in `lang`; English, marked as such, when there is no version. */
export function localisePivot(p: Pivot, lang: Lang): Pivot {
  const v = NARRATIVES[p.pivot_id]?.[lang];
  if (!p.narrative || !v || v.sentences.length !== p.narrative.sentences.length) return p;
  const sentences = p.narrative.sentences.map((s, i) => ({ ...s, text: v.sentences[i] }));
  return {
    ...p,
    narrative: {
      ...p.narrative, headline: v.headline, prefs: { ...p.narrative.prefs, language: lang },
      sentences: sentences as typeof p.narrative.sentences,
    },
  };
}

export const localiseRowLabel = (label: string, lang: Lang) => ROW_LABELS[label]?.[lang] ?? label;
