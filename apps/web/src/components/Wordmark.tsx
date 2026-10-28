import { useId } from "react";
import { Link } from "react-router-dom";

// Carry3's "p" mark (Ax86). The same drawing is public/logo.svg; here it is inline so the letter takes the bar's text colour.
const P = "M 1267 569 L 1241 554 L 1203 536 L 1179 527 L 1139 516 L 1112 511 L 1090 509 L 1089 508 L 1078 508 L 1077 507 L 1010 508 L 968 514 L 942 520 L 910 530 L 882 541 L 853 555 L 823 573 L 774 611 L 773 610 L 774 608 L 774 594 L 773 593 L 774 591 L 774 511 L 773 510 L 594 510 L 594 1497 L 599 1515 L 607 1531 L 620 1548 L 635 1560 L 656 1570 L 675 1574 L 696 1574 L 713 1570 L 738 1556 L 753 1542 L 762 1529 L 771 1507 L 774 1488 L 774 922 L 775 921 L 775 910 L 776 909 L 776 901 L 779 881 L 786 852 L 798 819 L 815 785 L 830 762 L 847 741 L 867 721 L 888 704 L 913 688 L 948 672 L 984 662 L 1004 659 L 1013 659 L 1014 658 L 1049 658 L 1050 659 L 1072 661 L 1101 668 L 1137 682 L 1160 695 L 1186 714 L 1213 740 L 1230 762 L 1243 783 L 1258 815 L 1269 852 L 1274 887 L 1274 918 L 1273 919 L 1272 937 L 1267 962 L 1254 1000 L 1237 1032 L 1220 1056 L 1208 1070 L 1186 1091 L 1165 1107 L 1149 1117 L 1125 1129 L 1090 1141 L 1050 1148 L 1018 1148 L 1010 1145 L 1000 1136 L 997 1130 L 996 1115 L 1000 1105 L 1061 998 L 1047 1002 L 1035 1002 L 1034 1003 L 1018 1002 L 999 997 L 986 991 L 973 982 L 956 965 L 943 942 L 940 931 L 869 1059 L 855 1082 L 841 1112 L 833 1141 L 831 1153 L 830 1175 L 831 1176 L 832 1194 L 839 1220 L 847 1237 L 854 1248 L 865 1262 L 879 1276 L 904 1294 L 939 1312 L 972 1323 L 997 1328 L 1015 1329 L 1016 1330 L 1072 1329 L 1073 1328 L 1082 1328 L 1103 1325 L 1139 1317 L 1179 1304 L 1210 1291 L 1237 1277 L 1276 1252 L 1309 1226 L 1338 1198 L 1360 1173 L 1383 1142 L 1408 1099 L 1424 1064 L 1435 1033 L 1445 995 L 1452 951 L 1453 917 L 1454 916 L 1452 867 L 1446 828 L 1437 792 L 1420 745 L 1403 711 L 1382 678 L 1351 639 L 1326 614 L 1296 589 Z";

/** The p mark on its own, cropped to the artwork: bowl 0-77 % of the height, stem descender below. */
function Mark() {
  return (
    <svg className="wordmark-p" viewBox="594 507 860 1067" aria-hidden="true" focusable="false">
      <path fill="currentColor" d={P} />
      <circle cx="1032.5" cy="908" r="94" fill="#FFCC1F" />
    </svg>
  );
}

// Dx10: a football for the "o". Centre panel in Pivot yellow, the other panels ink; the rim takes the text
// colour, so the ball keeps its edge on the dark bar. The same drawing is in public/wordmark.svg and favicon.svg.
const pentagon = (cx: number, cy: number, r: number, deg: number) =>
  [0, 1, 2, 3, 4].map((k) => {
    const a = ((deg + 72 * k) * Math.PI) / 180;
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
const SPOKES = [0, 1, 2, 3, 4].map((k) => {
  const deg = -90 + 72 * k;
  const [ux, uy] = [Math.cos((deg * Math.PI) / 180), Math.sin((deg * Math.PI) / 180)];
  return { patch: pentagon(50 * ux, 50 * uy, 13.5, deg + 180), x1: 18 * ux, y1: 18 * uy, x2: 36.5 * ux, y2: 36.5 * uy };
});

/** The football that stands in for the "o". */
function Ball() {
  const clip = `wm-ball-${useId()}`;
  return (
    <svg className="wordmark-o" viewBox="-50 -50 100 100" aria-hidden="true" focusable="false">
      {/* The panels a little smaller than the rim, so a light rim never covers a patch. */}
      <g transform="scale(.935)">
        <clipPath id={clip}><circle r={47} /></clipPath>
        <circle r={47} fill="#FFFFFF" />
        <g clipPath={`url(#${clip})`} fill="#121418" stroke="#121418" strokeWidth={3.5} strokeLinejoin="round">
          {SPOKES.map((s, i) => (
            <g key={i}><polygon points={s.patch} /><line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} /></g>
          ))}
        </g>
        <polygon points={pentagon(0, 0, 18, -90)} fill="#FFCC1F" stroke="#121418" strokeWidth={3.5} strokeLinejoin="round" />
      </g>
      <circle r={47} fill="none" stroke="currentColor" strokeWidth={6} />
    </svg>
  );
}

/** The site's name in the bar: the p mark and a football stand in for two letters, so it reads "pivot". With `to` it is a link home. */
export default function Wordmark({ to }: { to?: string }) {
  const body = <><Mark /><span aria-hidden="true">iv</span><Ball /><span aria-hidden="true">t</span></>;
  return to
    ? <Link to={to} className="brand" aria-label="Pivot">{body}</Link>
    : <span className="brand" role="img" aria-label="Pivot">{body}</span>;
}
