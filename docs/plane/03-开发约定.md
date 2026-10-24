# 开发约定

小步提交，当天合并，`main` 永远能跑。完整的分工、任务清单和节奏见《Pivot 开发手册》。

## 任务

- 所有任务都在 GitHub Issues 里，标题以任务 ID 开头，例如 `B03 · Simulator: full match with seed determinism`。任务的原始清单在 `docs/plan/tasks.csv`。
- 开工前把 issue 拖到 In progress，并指派给自己。每人同时最多 2 个进行中的任务。
- 卡住超过 45 分钟，就在群里 @ 相关的人；超过 2 小时，给 issue 加 `blocked` 标签，在站会上处理。
- Must 任务按人分配；Should 和 Could 放在公共池，谁先做完手上的 Must，谁按顺序去拉。

## 分支与提交

- 分支名：`<线>/<任务ID>-<简述>`，例如 `b/B03-simulator-core`。
- 提交信息以任务 ID 开头：`B03: add possession-chain step`。
- 不直接推送到 `main`。

## Pull Request

- 一个 PR 只做一个任务，尽量少于 400 行，当天合并。超过一天的分支要拆开。
- 描述里写 `Closes #编号`，合并后会自动关闭 issue。
- 必须通过 CI，并且至少有一位同伴 Review。收到 Review 请求后 30 分钟内响应。
- 合并方式统一用 Squash and merge。
- Review 搭档：A 和 B 互审；D 的 Python 由 A 审；C 的前端由 D 审交互和文案；D 的前端由 C 审。
- 仓库是私有的时候，分支保护需要付费计划，所以先靠约定执行；转为公开后再打开 `main` 的保护规则。

## 契约

- `packages/pivot_core/src/pivot_core/domain` 里的模型是唯一的事实来源，由 B 负责。
- 10/23 20:00 冻结后，只允许新增可选字段。改动契约的 PR 标题要加 `[contract]`，并在群里通知全员。
- 改完运行 `uv run scripts/export_contracts.py` 和 `pnpm --filter @pivot/contracts gen:types`，把生成的文件一起提交。

## 本地开发

- 默认使用 `PIVOT_PROFILE=local`。任何功能先在本地形态跑通，再上云。
- 密钥不进仓库。本地访问 Azure 用 `az login` 的身份。

## 完成定义

- 符合冻结的契约，Schema 校验通过
- 确定性逻辑（模拟器、指标、核查）有单元测试
- 在本地形态下跑通；部署到云端后冒烟测试通过
- 对应的 Demo 步骤可以现场演示
- 在轨迹和遥测里能看到这项功能的记录

## 节奏（当地时间）

- 09:30 早站会，15 分钟
- 13:00 合并窗口：从 10/25 起，`main` 每天这个时间部署到开发环境
- 21:30 晚站会，15 分钟
- 10/26 14:00 功能冻结：之后只修阻断性问题。录 Demo 只用 `demo-1021` 预设。
