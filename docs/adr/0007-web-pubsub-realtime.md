# ADR-0007：实时推送使用 Azure Web PubSub

- 状态：已采纳（替换 PRD 中的 SignalR Service）
- 日期：2026-10-23

## 背景

前端需要实时收到指标、转折点和推演进度，从事件产生到界面更新的 p95 不超过 2 秒。后端全部是 Python，会有多个发布方：模拟器（或指标处理函数）和 Worker。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. Azure Web PubSub** | 有官方 Python 服务端 SDK；浏览器用原生 WebSocket 即可连接；支持按组推送；Serverless | 免费层的连接数和每日消息数有限 |
| B. Azure SignalR Service | 生态成熟 | 最佳搭档是 ASP.NET 或 Functions 绑定；Python 服务端只能走 REST；前端还要引入客户端库 |
| C. API 直接用 SSE 推送 | 最简单 | 长连接全压在 API 上；横向扩容需要额外的背板 |
| D. 轮询 | 零基础设施 | 延迟高，请求浪费 |

## 决策

采用 Web PubSub。

- 每场比赛一个组：`match.{matchId}`。前端调用 `GET /api/realtime/negotiate?matchId=` 拿到带“加入该组”权限的客户端连接 URL。
- 所有消息使用统一信封：`{type, matchId, seq, ts, payload}`。`type` 取值见架构文档 §7.2。
- 本地形态 L 由 FastAPI 的 WebSocket 端点实现同样的信封，前端代码不用区分环境。
- 开发期用免费层；评审期升级为 Standard 1 单位，应对多位评委同时访问。

## 后果

- **正面**：推送和 API 的扩缩互不影响；多个发布方可以直接推送，不用绕经 API。
- **负面**：多一个资源和一层身份配置。
- **风险**：断线期间会漏消息。缓解办法是客户端自动重连后，用 `GET /timeline?sinceSeq=` 补齐缺失的数据。
