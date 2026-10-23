# ADR-0004：Agent 编排使用 Microsoft Agent Framework 显式工作流，循环有上限

- 状态：已采纳
- 日期：2026-10-23
- 相关：ADR-0005、ADR-0003

## 背景

评审中 Agentic 设计占 20%。Multi-Agent 奖考察四点：每个 Agent 角色清晰，通过共享状态协作，交接有效，能从失败中恢复。与此同时，解释必须在 10 秒内上屏，数字必须 100% 正确。主办方点名的 hero 技术包括 Microsoft Agent Framework 和 Foundry。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 单个大 prompt | 实现最快 | 没有角色边界；不能只重试某一步；很难单独评测 |
| B. 自由对话式多 Agent（由 LLM 决定下一位发言者） | 看起来“自主” | 路径不可预测；延迟和成本失控；无法复现 |
| **C. Agent Framework 显式工作流（图）** | 节点和边是固定的；条件边可以表达“核查失败就回去重写”；每个节点可单独测试；自带可观测性 | 灵活度不如方案 B；SDK 还在快速演进 |
| D. LangGraph 等第三方编排 | 能力相近 | 不是主办方的 hero 技术 |
| E. Foundry Agent Service 托管 Agent | 托管线程，门户里可直接看到 | 函数工具需要往返调用，延迟更高；对确定性工具的控制弱 |

## 决策

采用方案 C，模型来自 Foundry 的部署。

- **发现链**：Judge（判定）→ Explainer（解释）→ Verifier（核查）。核查不通过就沿条件边回到 Explainer，最多 2 次，之后走 TemplateExplainer（确定性模板）。
- **推演链**：Translator（场景翻译，只在自然语言输入时调用）→ 执行器（确定性）→ Comparator（对比）→ Verifier。
- **共享状态**：工作流上下文保存在 Cosmos DB 的比赛分区里，每个节点在交接时写一条 `AgentTrace`。
- **工具**：全部是确定性 Python 函数（`get_events`、`get_metrics`、`compute_stat`、`list_scenario_types`、`get_sim_summary`）。
- **SDK 隔离**：用我们自己的 `AgentRuntime` 端口包住 Agent Framework，并锁定 SDK 版本，防止上游接口变化扩散到业务代码。
- **扩展**（P2）：把“解释某个转折点”暴露为 A2A 端点，供英超 Companion 这类球迷助手调用，正好对应我们“情报引擎”的产品定位。

## 后果

- **正面**：延迟和成本可预测；每次交接和重写都留在轨迹里，可以直接在 Demo 中展示；每个节点可以用固定输入做单元测试。
- **负面**：看不到“涌现”式的协作；新增一种 Agent 需要修改工作流图。
- **风险**：SDK 接口变动 → 版本锁定加端口隔离；模型限流（429）→ 指数退避重试 2 次，然后降级。
