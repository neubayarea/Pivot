# ADR-0001：模块化单仓 + 端口与适配器 + 三档部署形态

- 状态：已采纳
- 日期：2026-10-23
- 决策者：A（平台）· B（模拟）· C（体验）· D（Agent）
- 相关：ADR-0002、ADR-0003、ADR-0009、ADR-0011

## 背景

距离提交只剩 3.5 天，4 个人需要从第一天起并行开发。目标架构要用到十余个 Azure 服务，这些服务又是 Cloud Native 奖的看点。如果业务代码直接调用每个服务的 SDK，任何一个服务没开通或者没调通，整条链路都会卡住，联调也会把剩下的时间吃光。演示的可靠性必须排在架构的完整度之前。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 微服务优先：每个能力单独一个服务，直接调用 Azure SDK | 部署层面解耦彻底 | 脚手架和联调成本最高；本地跑不通整条链路；一个服务出问题就阻塞所有人 |
| B. 单体脚本：一个 Python 进程做完所有事 | 第一天就能跑 | 展示不了云原生；Agent 角色边界模糊；四个人改同一批文件，冲突多 |
| **C. 模块化单仓 + 端口与适配器** | 领域核心不依赖任何云服务；外部能力都通过端口接入；本地和云端走同一份业务代码 | 多一层适配器（约占代码量 10%）；端口要刻意保持精简 |

## 决策

采用方案 C。

- **领域核心** `packages/pivot_core` 只依赖 `pydantic` 和 `numpy`，里面包含领域模型、模拟器、指标与变点算法、统计函数，以及端口接口。
- **端口**：`EventSink`、`WorkQueue`、`MatchRepository`、`TraceRepository`、`LivePublisher`、`ModelClient`、`SimulationExecutor`。
- **适配器** `packages/pivot_adapters`：`local/`（内存总线、SQLite 或内存存储、FastAPI WebSocket、桩模型）和 `azure/`（Event Hubs、Service Bus、Cosmos DB、Web PubSub、Foundry、Container Apps Jobs）。
- **同一个 Python 镜像，三个入口**：`api`、`simulator`、`worker`。
- **部署形态**用环境变量 `PIVOT_PROFILE` 切换：

| 形态 | 组成 | 用途 |
|---|---|---|
| L（本地） | 单进程，内存适配器；模型调用走 Foundry 或桩 | 开发、单元测试；演示的最后兜底 |
| C1（云端最小） | 在 Container Apps 上运行 api / simulator / worker，配合 Service Bus、Cosmos DB、Web PubSub、Foundry；指标在模拟器进程内计算 | 必须交付的形态 |
| C2（云端完整） | 在 C1 基础上加 Event Hubs + Functions 计算指标，以及 Container Apps Jobs 分片推演 | 应交付，冲 Cloud Native 奖 |

- **契约优先**：`pivot_core.domain` 里的 Pydantic 模型是唯一事实来源，由它导出 JSON Schema，再生成前端的 TypeScript 类型。

## 后果

- **正面**：第一天就能用假数据并行开发；砍需求只改部署形态，不改代码结构；演示时 C2 出问题可以退回 C1，C1 出问题可以退回 L。
- **负面**：适配器带来额外代码；新加一个外部能力必须先定义端口。
- **风险与缓解**：本地适配器和 Azure 适配器的行为可能不一致。缓解办法是给每个端口写一组契约测试，CI 里跑本地实现，部署后对云端跑一次冒烟测试。
