# apps/web

网页界面（C 线）：Vite + React + TypeScript，样式是 Matchday Programme（见 `docs/design/matchday-programme.html`）。

```bash
pnpm install
pnpm --filter web dev     # http://localhost:5173
pnpm --filter web build   # 类型检查 + 打包到 dist/
pnpm --filter web lint    # tsc --noEmit
```

- 路由：S1 `/` 实时看板，S2 `/pivot/:id` 转折点详情，S3 `/whatif/:id`「假如」实验室。内容目前是静态占位。
- 颜色和字体只用 `src/styles/tokens.css` 里的 `--pv-*` 变量。它是 `docs/design/tokens.css` 的副本，两边一起改。
- 类型从 `@pivot/contracts` 导入（`import type { ViewerPrefs } from "@pivot/contracts"`），不要手写契约类型。
