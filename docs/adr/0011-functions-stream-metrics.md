# ADR-0011：流式指标计算使用 Azure Functions（Flex Consumption，Python，Event Hubs 触发）

- 状态：已采纳（属于 C2 形态）
- 日期：2026-10-23
- 相关：ADR-0001、ADR-0002、ADR-0010

## 背景

在 C2 形态中，指标计算要由事件驱动、按分区有序处理，并能按需扩缩；同时最好和 C1 形态共用同一份分析代码。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. Azure Functions，Event Hubs 触发** | 原生触发和检查点；直接复用 `pivot_core.analytics`；按分区扩缩 | 有冷启动 |
| B. Azure Stream Analytics | 类 SQL 的时间窗计算 | CUSUM 和威胁网格要写 UDF；没法复用 Python 代码 |
| C. Fabric 实时智能（Eventstream + KQL） | 实时分析能力强 | 需要容量费用；搭建时间长；对本次范围过重 |
| D. 在模拟器进程内计算 | 最快 | 失去事件驱动的解耦（这正是 C1 的做法，作为退路保留） |

## 决策

采用方案 A，Flex Consumption 计划，保持 1 个常备实例，用来消除演示时的冷启动。

- 每批事件的处理步骤：按 `seq` 去重；upsert 分钟文档；在分钟边界更新 EWMA 和 CUSUM；候选点入队到 `pivot-candidates`；通过 Web PubSub 推送 `metric.updated`。
- 每场比赛的运行状态保存在 match 文档中，用 ETag 乐观并发写入。同一场比赛只落在一个 Event Hubs 分区，因此同一时刻只有一个写入者。

## 后果

- **正面**：C1 和 C2 共用同一份分析代码；指标计算和模拟器在部署上解耦。
- **负面**：多一套部署流水线（Functions 和 Container Apps 分开发布）。
- **风险**：批处理在检查点之前失败会导致重复处理。缓解办法是全部操作都做成幂等 upsert，并按 `seq` 去重。
