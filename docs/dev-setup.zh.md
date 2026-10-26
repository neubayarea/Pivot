# Pivot 开发者说明（中文）

英文的项目介绍见仓库首页 [README](../README.md)。架构见 [architecture.md](architecture.md)，协作约定见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 目录

| 目录 | 内容 |
| --- | --- |
| `apps/api` | FastAPI 后台（A）：REST、WebSocket、「假如」接口，`pivot_api.single` 单进程跑整套 |
| `apps/simulator` | 模拟器的命令行入口（B），模拟器本身在 `packages/pivot_core/sim` |
| `apps/worker` | AI 工作流与 Agent（D）：判断员、写稿员、核对员、对比员 |
| `apps/web` | 网页界面（C），Vite + React + TypeScript |
| `packages/pivot_core` | 共享的领域模型、模拟器、势头和转折点检测 |
| `packages/pivot_adapters` | 本机和 Azure（Cosmos DB、Blob）的存储适配器 |
| `packages/contracts` | 导出的 JSON Schema 和 TS 类型（脚本生成，不要手改） |

## 本地怎么跑

需要先装 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync                      # 装好所有 Python 包和开发工具
uv run ruff check .          # 代码检查
uv run pytest                # 跑测试
uv run python -m pivot_api   # 启动 API，打开 http://127.0.0.1:8000/healthz
pnpm install && pnpm --filter web dev   # 启动网页，打开 http://localhost:5173
```

单进程跑整套（API、实时推送、worker、网页都在 http://127.0.0.1:8000）：

```bash
pnpm --filter web build && uv run python -m pivot_api.single
```

用 Docker 跑同样的单进程镜像：

```bash
docker build -t pivot .
docker run --rm -p 8000:8000 pivot
```

部署到甲骨文虚拟机见 [deploy-oracle.md](deploy-oracle.md)。

## AI 模型（D01）

Agent 用两个 Foundry 模型部署：`standard`（Explainer、Comparator、Translator）和 `mini`（Judge）。代码里只认环境变量，不写死模型名：

| 变量 | 含义 |
| --- | --- |
| `PIVOT_FOUNDRY_ENDPOINT` | Foundry（Azure OpenAI）资源的终结点，例如 `https://<resource>.openai.azure.com/` |
| `PIVOT_MODEL_STANDARD` | standard 部署的名字 |
| `PIVOT_MODEL_MINI` | mini 部署的名字 |

本地用 `az login` 的身份访问，不用 API 密钥；账号需要在该资源上有 “Cognitive Services OpenAI User” 角色。验证两个部署都能用、同时 10 个请求不被限流：

```bash
uv run scripts/foundry_quota_test.py
```
