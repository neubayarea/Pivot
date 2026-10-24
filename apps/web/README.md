# apps/web

网页界面（C 线）：Vite + React + TypeScript，样式是 Matchday Programme（见 `docs/design/matchday-programme.html`）。

```bash
pnpm install
pnpm --filter web dev     # http://localhost:5173
pnpm --filter web build   # 类型检查 + 打包到 dist/
pnpm --filter web lint    # tsc --noEmit
```

- 路由：S1 `/` 实时看板，S2 `/pivot/:id` 转折点详情，S3 `/whatif/:id`「假如」实验室。S2、S3 目前是静态占位。
- 颜色和字体只用 `src/styles/tokens.css` 里的 `--pv-*` 变量。它是 `docs/design/tokens.css` 的副本，两边一起改。
- 类型从 `@pivot/contracts` 导入（`import type { ViewerPrefs } from "@pivot/contracts"`），不要手写契约类型。
- 比赛数据只从 `useMatch()`（`src/data/match.tsx`）拿。现在它在定时器上回放前端自用的假数据 `src/fixtures/demo-1021.ts`（不是 B02 的正式数据），C03 接真实接口时只换这一层。
- 回放默认从 73:30 开始、5 倍速，74′ 的转折点会从 Analysing 变成 Verified；页面上可以暂停、换速度、重来。`/?from=0` 从开球开始，`/?from=86` 从第 86 分钟开始。
