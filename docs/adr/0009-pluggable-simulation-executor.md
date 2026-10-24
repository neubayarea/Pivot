# ADR-0009：推演执行器可插拔——默认本地进程池，大规模时用 Container Apps Jobs

- 状态：已采纳（Jobs 适配器属于 Could，按时间决定是否交付）
- 日期：2026-10-23
- 相关：ADR-0001、ADR-0008

## 背景

默认推演规模是基线和反事实各 500 次。单核估算约 10 秒，PRD 的要求是 30 秒内完成。Cloud Native 的叙事希望展示弹性扩展，但演示首先要稳定、要快。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. 模拟器容器内的进程池（2 vCPU）** | 没有冷启动；1,000 次运行估算 3 到 6 秒 | 只能纵向扩展 |
| B. Container Apps Jobs 分片 | 可以并行跑上万次；横向弹性 | 每次作业执行有调度和镜像拉取开销（数秒到数十秒），N 较小时反而更慢 |
| C. Durable Functions 扇出扇入 | 编排能力强 | Python 冷启动加上编排复杂度；与 Jobs 的定位重叠 |
| D. Azure Batch | 适合超大规模计算 | 对本场景过重 |

## 决策

定义端口 `SimulationExecutor.run(spec, n_runs) -> SimSummary`，提供两个适配器：

- `LocalPoolExecutor`：默认实现，用于 N ≤ 2,000；
- `AcaJobExecutor`：用于 N > 2,000。把任务拆成若干分片（每片 250 次），每个分片把结果写入 Blob，Worker 汇总。

两个适配器调用同一个 `run_shard(spec, seeds)` 函数，结果逐位一致。

## 后果

- **正面**：Demo 主线（500 次）延迟最低、最稳定；架构上保留了横向扩展路径。如果有时间，可以在视频中加一段 5,000 次分片运行的展示。
- **负面**：如果 Jobs 适配器没做完，Cloud Native 的展示会少一个亮点；README 和架构图中如实说明扩展方式。
- **风险**：进程池占满 CPU 会拖慢实时比赛。缓解办法是实时比赛和批量推演分别部署成两个 Container App 修订版本（或者限制进程池最多 2 个进程）。

## 实现情况（B04、B08，2026-10-24）

- 代码在 `packages/pivot_core/src/pivot_core/sim/whatif.py`，入口是 `run_whatif(match, spec, plants=...)`，返回 `SimResult`（`executor="local_pool"`）。
- “存档”不读数据库里的分钟快照：同一个种子的比赛每次踢出来都一样，所以用原种子重新踢到 `at_minute`，把引擎整个复制一份就是存档（`save`）。踢到第 37 分钟约 1 到 3 秒。
- 两组各 `n_runs` 次，第 i 次在两组里都用种子 `seed_base + i`（配对种子）；胜平负比例带 Wilson 95% 区间，两组区间不重叠才算 `significant`。
- 每个进程池任务跑 10 次（`run_shard(key, blob, seeds)`），以后的 `AcaJobExecutor` 可以直接调用同一个函数，结果逐位一致。`SimulationExecutor` 端口和 Jobs 适配器还没做。
