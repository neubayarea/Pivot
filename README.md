# Pivot

Microsoft × Premier League 黑客松项目。架构见 [docs/architecture.md](docs/architecture.md)，协作约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 目录

| 目录 | 内容 |
| --- | --- |
| `apps/api` | FastAPI 后台（A），目前只有 `/healthz` |
| `apps/simulator` | 比赛模拟器（B），占位 |
| `apps/worker` | AI 工作流与 Agent（D），占位 |
| `apps/web` | 网页界面（C），Vite + React + TypeScript |
| `packages/pivot_core` | 共享的领域模型和核心逻辑 |
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

部署到甲骨文虚拟机见 [docs/deploy-oracle.md](docs/deploy-oracle.md)。
