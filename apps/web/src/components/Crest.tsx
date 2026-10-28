// Dx12 (#443): the club crest beside a team's name. The 20 crests are transparent 256 px PNGs in
// public/crests/<short>.png, one per club in pivot_core/sim/world.py CLUBS. A crest is decorative:
// the team's name is always next to it, so it has an empty alt and is hidden from screen readers.
// For a club without a crest (or if the image fails to load) the caller's kit-colour chip shows instead.
import { useState, type ReactNode } from "react";

export const CRESTS = new Set([
  "cor", "tes", "elm", "hbc", "van", "dun", "rov", "kel", "ost", "fal",
  "mar", "sal", "pel", "qua", "bri", "hol", "wes", "tho", "gre", "lun",
]);

export const crestSrc = (short: string | null | undefined): string | null => {
  const key = (short ?? "").trim().toLowerCase();
  return CRESTS.has(key) ? `/crests/${key}.png` : null;
};

type Props = {
  /** The club's short name, e.g. "TES". */
  short: string | null | undefined;
  /** Width and height in CSS pixels. */
  size?: number;
  className?: string;
  /** What to show for a club without a crest: usually the kit-colour dot used before. */
  fallback?: ReactNode;
};

export default function Crest({ short, size = 20, className, fallback = null }: Props) {
  const src = crestSrc(short);
  const [broken, setBroken] = useState<string | null>(null);
  if (!src || broken === src) return <>{fallback}</>;
  return (
    <img className={`crest${className ? ` ${className}` : ""}`} src={src} alt="" aria-hidden="true"
      width={size} height={size} loading="lazy" decoding="async" draggable={false}
      onError={() => setBroken(src)} />
  );
}
