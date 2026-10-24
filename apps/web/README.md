# apps/web

网页界面（C 线）：Vite + React + TypeScript，样式是 Matchday Programme（见 `docs/design/matchday-programme.html`）。

```bash
pnpm install
pnpm --filter web dev     # http://localhost:5173
pnpm --filter web build   # 类型检查 + 打包到 dist/
pnpm --filter web lint    # tsc --noEmit
pnpm --filter web test    # vitest：实时连接的重连、去重、缺口补齐
```

默认连真实接口：先在仓库根目录 `uv run python -m pivot_api`，开发服务器把 `/api`（含 WebSocket）代理到 `http://127.0.0.1:8000`。没有后端时用 `/?fixture=1`（或构建时设 `VITE_PIVOT_FIXTURE=1`）回放前端假数据。

- 路由：S1 `/` 实时看板，S2 `/pivot/:id` 转折点详情，S3 `/whatif/:id`「假如」实验室。S2、S3 目前是静态占位。
- 颜色和字体只用 `src/styles/tokens.css` 里的 `--pv-*` 变量。它是 `docs/design/tokens.css` 的副本，两边一起改。
- 类型从 `@pivot/contracts` 导入（`import type { ViewerPrefs } from "@pivot/contracts"`），不要手写契约类型。
- 比赛数据只从 `useMatch()`（`src/data/match.tsx`）拿，页面不关心数据从哪来：
  - 实时（默认）：`src/data/live/`。`socket.ts` 按 PR #85 的约定连 WebSocket，记最大 `seq`，断线指数退避重连并带 `?since=`；每次（重）连上、发现缺口或服务端重启后，用 REST 重新拉一次再按 seq 合并。`state.ts` 把 REST 快照和推送消息合成一份状态。`?match=<id>` 指定比赛，否则取最近一场进行中的比赛。断线时顶栏下方出现米黄提示条，数据停在断线那一刻。
  - 假数据：`?fixture=1` 时在定时器上回放 `src/fixtures/demo-1021.ts`（不是 B02 的正式数据）。默认从 73:30 开始、5 倍速，74′ 的转折点会从 Analysing 变成 Verified；页面上可以暂停、换速度、重来。`/?fixture=1&from=0` 从开球开始。
