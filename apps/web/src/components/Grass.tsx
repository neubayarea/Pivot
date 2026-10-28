// The grass under every SVG pitch (Dx11): green in two shades, mown in 12 stripes across the length of
// the pitch, the way a ground staff cuts it. Colours come from tokens.css (--pv-pitch, --pv-pitch-stripe),
// so the night theme darkens them in one place.

/** How many stripes a full-length pitch is cut into. */
export const STRIPES = 12;

/**
 * Grass from (x, y) over w x h. `along` is the axis the pitch runs along: "x" for a pitch drawn left to right
 * (stripes stand upright), "y" for one drawn up the page (stripes lie across).
 */
export default function Grass({ w, h, x = 0, y = 0, along = "x", stripes = STRIPES }: {
  w: number; h: number; x?: number; y?: number; along?: "x" | "y"; stripes?: number;
}) {
  const len = along === "x" ? w : h;
  const step = len / stripes;
  return (
    <g className="grass" aria-hidden="true">
      <rect x={x} y={y} width={w} height={h} fill="var(--pv-pitch)" />
      {Array.from({ length: Math.ceil(stripes / 2) }, (_, i) => {
        const at = (2 * i + 1) * step;
        if (at >= len) return null;
        const size = Math.min(step, len - at);
        return along === "x"
          ? <rect key={i} x={x + at} y={y} width={size} height={h} fill="var(--pv-pitch-stripe)" />
          : <rect key={i} x={x} y={y + at} width={w} height={size} fill="var(--pv-pitch-stripe)" />;
      })}
    </g>
  );
}
