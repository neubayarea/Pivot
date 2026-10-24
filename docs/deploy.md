# 部署到 Azure（C1 形态）

这份文档说明怎样用一条命令在 Azure 上建好 Pivot 需要的全部资源，并把三个应用部署上去；以及比赛结束后怎样一条命令删干净。模板在 `azure.yaml` 和 `infra/`，背景见 [ADR-0013](adr/0013-platform-baseline-azd-bicep-identity.md) 和 [架构文档 §11](architecture.md#11-部署视图)。

## 会建出什么

一个资源组 `rg-<环境名>`（开发 `rg-pivot-dev`，评审期 `rg-pivot-demo`），里面有：

| 资源 | 规格 | 用途 |
|---|---|---|
| Container Apps 环境 | Consumption | 运行下面三个应用 |
| `ca-api-…` | 1–3 个副本，公网入口，端口 8000 | Pivot API |
| `ca-worker-…` | 1 个副本，无入口 | Intelligence Worker，消费 `pivot-candidates` 队列 |
| `ca-web-…` | 1–2 个副本，公网入口 | 网页（nginx），`/api` 转发到 API |
| Container Registry | Basic | 存放镜像，在云端构建，本机不需要 Docker |
| Service Bus | Standard，一个队列 `pivot-candidates` | Agent 任务队列，带重复检测和死信 |
| Cosmos DB | NoSQL Serverless，库 `pivot`，容器 `match_data`、`agent_traces` | 比赛数据和 Agent 轨迹，分区键 `/match_id` |
| Web PubSub | 开发期 Free_F1，评审期 Standard_S1 | 实时推送 |
| Key Vault | Standard，RBAC | 目前为空，只给将来的第三方密钥用 |
| Log Analytics + Application Insights | 按量 | 日志和遥测 |
| 用户分配的托管身份 `id-…` | — | 所有应用都用它访问上面的服务 |
| 预算 `budget-<环境名>` | 每月 50 美元 | 到 80% 和 100% 时发邮件 |

模拟器（simulator）还没有可运行的程序，这次没有部署；B 线做好后再加进 `azure.yaml` 和 `infra/main.bicep`。Foundry 模型部署由 D01 负责，这里只把它的地址和部署名作为环境变量传给应用。

**没有任何密码或连接字符串。** Cosmos DB、Service Bus、Web PubSub 都关掉了密钥登录，应用只能通过托管身份访问。

## 谁要做什么

### 1. 团队先确认（一次性）

- **订阅**：用哪个 Azure 订阅，谁有它的 Owner 权限（建角色分配需要 Owner 或 User Access Administrator）。
- **区域**：和 D 一起选一个 Foundry 两档模型都有配额的区域，所有资源放在同一区域。
- **预算邮箱**：收预算告警的邮箱，可以填多个，用逗号隔开。
- **成本**：Service Bus Standard、Container Registry Basic、三个常驻副本按小时计费；Cosmos DB 和 Web PubSub 免费层按用量。一天大约几美元，预算告警兜底。

### 2. 部署的人（A 线）在自己电脑上

需要装好 [Azure Developer CLI（azd）](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 和 [Azure CLI（az）](https://learn.microsoft.com/cli/azure/install-azure-cli)。

```bash
azd auth login
az login
```

```bash
azd env new pivot-dev
```

```bash
azd env set AZURE_SUBSCRIPTION_ID <订阅 ID>
```

```bash
azd env set AZURE_LOCATION <区域，例如 swedencentral>
```

```bash
azd env set PIVOT_BUDGET_EMAILS "a@example.com,b@example.com"
```

Foundry 部署好以后（D01），再设置这三个值；没有也能先部署，Agent 会走降级路径：

```bash
azd env set PIVOT_FOUNDRY_ENDPOINT https://<foundry 资源>.openai.azure.com/
```

```bash
azd env set PIVOT_FOUNDRY_DEPLOYMENT <标准模型部署名>
```

```bash
azd env set PIVOT_FOUNDRY_DEPLOYMENT_MINI <mini 模型部署名>
```

然后一条命令建资源、构建镜像、部署应用：

```bash
azd up
```

第一次大约 10 到 15 分钟。完成后 azd 会打印网页地址（`PIVOT_WEB_URL`）和 API 地址（`PIVOT_API_URL`），所有输出也写在 `.azure/pivot-dev/.env` 里（这个目录不进仓库）。

之后只改了代码，用 `azd deploy` 重新部署；改了 `infra/`，用 `azd provision`。

### 3. 部署完检查

- **角色生效有延迟**：角色分配要几分钟才生效，刚部署完应用访问 Cosmos 或 Service Bus 报 403 是正常的，等 5 分钟再试。
- **预算告警**：在门户打开资源组 → 成本管理 → 预算，确认 `budget-pivot-dev` 存在、金额 50 美元、收件人正确。
- **Foundry 权限**（D 线）：把 `.azure/pivot-dev/.env` 里的 `PIVOT_IDENTITY_PRINCIPAL_ID` 在 Foundry 资源上授予 “Cognitive Services OpenAI User”（或 Foundry 当前要求的角色）。
- **冒烟测试**：A10 负责。

### 4. 评审期（10/26）

```bash
azd env new pivot-demo
```

按第 2 步设置同样的值，再把 Web PubSub 升级到 Standard：

```bash
azd env set PIVOT_WEBPUBSUB_SKU Standard_S1
```

```bash
azd up
```

### 5. 比赛结束后（11/20 公布结果后）

删除资源组里的全部资源，并彻底清除 Key Vault 等软删除的资源：

```bash
azd down --purge
```

## 在 GitHub Actions 里部署（之后再做）

ADR-0013 要求 CI 用 OIDC 登录，不保存密钥。准备好后由有 Owner 权限的人运行一次：

```bash
azd pipeline config --auth-type federated
```

它会建一个服务主体并配好联合凭据，把订阅和环境名写进仓库的 Actions 变量。CI 里的服务主体需要设置 `AZURE_PRINCIPAL_TYPE=ServicePrincipal`。

## 应用读取的环境变量

`infra/main.bicep` 给 api 和 worker 设置了下面这些环境变量，A08 的 Azure 适配器按这些名字读取：

| 变量 | 值 |
|---|---|
| `PIVOT_PROFILE` | `c1` |
| `AZURE_CLIENT_ID` | 托管身份的 client id，`DefaultAzureCredential` 用它选身份 |
| `PIVOT_COSMOS_ENDPOINT`、`PIVOT_COSMOS_DATABASE` | Cosmos 地址，库名 `pivot` |
| `PIVOT_SERVICEBUS_NAMESPACE` | `<名字>.servicebus.windows.net` |
| `PIVOT_WEBPUBSUB_ENDPOINT`、`PIVOT_WEBPUBSUB_HUB` | Web PubSub 地址，hub 名 `pivot` |
| `PIVOT_KEYVAULT_URI` | Key Vault 地址 |
| `PIVOT_FOUNDRY_ENDPOINT`、`PIVOT_FOUNDRY_DEPLOYMENT`、`PIVOT_FOUNDRY_DEPLOYMENT_MINI` | D01 提供 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING`、`OTEL_SERVICE_NAME` | 遥测 |
| `PIVOT_CORS_ORIGINS`（只有 api） | 网页的地址 |

网页容器只有 `API_UPSTREAM`（API 的地址），nginx 用它转发 `/api`。
