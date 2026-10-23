# ADR-0012：前端使用 React + Vite + D3，部署在 Static Web Apps

- 状态：已采纳
- 日期：2026-10-23

## 背景

评审中 UX 占 20%。界面需要三种定制图表：球场事件图、势头曲线和结果分布图。前端由 C 一个人负责，视觉风格要能随最终选定的 UI 方案切换。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. React + TypeScript + Vite + D3** | 完全可控；开发服务器快；静态托管便宜 | 图表组件要自己写 |
| B. Next.js | 框架能力全面 | 用不上服务端渲染，反而更重 |
| C. Streamlit 或 Gradio | Python 开发者上手最快 | 界面一眼就能认出来，定制和品牌化困难，UX 分吃亏 |
| D. Power BI Embedded | 企业感强 | 实时交互和定制能力弱；有授权成本 |

## 决策

采用方案 A。

- React 负责渲染 SVG，D3 只用于比例尺、路径生成和时间格式化，避免和 React 抢 DOM。
- REST 请求用 TanStack Query；实时连接用原生 WebSocket，走 Web PubSub 的 JSON 子协议。
- 类型来自 `packages/contracts` 自动生成的 TypeScript 文件，禁止手写接口类型。
- 主题完全由 CSS 变量驱动，选定 UI 风格后只需替换一份令牌文件。
- 托管在 Static Web Apps 免费层；API 地址通过构建时的环境变量注入；API 端开启 CORS 白名单。

## 后果

- **正面**：UI 风格可以按评审需要切换；同一套组件既能用于 Demo，也能用于 README 截图。
- **负面**：三个图表组件约需 1 人天。
- **风险**：D3 和 React 的状态同步问题。约束是：D3 只计算，不直接操作 DOM。
