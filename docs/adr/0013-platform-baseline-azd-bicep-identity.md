# ADR-0013：平台基线——azd + Bicep、GitHub Actions OIDC、托管身份

- 状态：已采纳
- 日期：2026-10-23

## 背景

项目要用到十余个 Azure 资源，必须能一键创建和销毁：赛后不删干净就会持续计费。仓库会公开，不能出现任何密钥。只剩 3.5 天，部署必须做到一条命令完成。

## 备选方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. azd + Bicep（尽量使用 Azure Verified Modules）** | `azd up` 一条命令完成创建和部署；Azure 原生；模块现成 | 团队可能对 Bicep 不熟 |
| B. Terraform | 支持多云，生态大 | 状态文件要单独管理；接入 azd 部署流程还要额外配置 |
| C. 在门户里手工创建 | 第一次最快 | 不可复现，容易出错，赛后也难清理干净 |

## 决策

- 用 azd 加 Bicep：根目录放 `azure.yaml`，`infra/` 下放 `main.bicep` 和各模块。开发环境的环境名为 `pivot-dev`，评审期的环境名为 `pivot-demo`。
- 在 GitHub Actions 中用 OIDC 联合凭据登录 Azure，不保存客户端密钥。
- 服务之间全部使用用户分配的托管身份加数据面 RBAC，不使用连接字符串：

| 服务 | 角色 |
|---|---|
| Cosmos DB | Cosmos DB Built-in Data Contributor（Cosmos 原生 RBAC） |
| Service Bus | Azure Service Bus Data Sender / Data Receiver |
| Event Hubs | Azure Event Hubs Data Sender / Data Receiver |
| Web PubSub | Web PubSub Service Owner |
| Foundry 模型 | Cognitive Services OpenAI User（以 Foundry 当前的角色要求为准） |
| Container Registry | AcrPull |
| Storage | Storage Blob Data Contributor（Functions 宿主存储和推演分片结果） |
| Key Vault | Key Vault Secrets User（只用于将来可能接入的第三方密钥） |

- 在仓库里开启 GitHub 秘密扫描和推送保护；本地开发使用 `az login` 的开发者身份（DefaultAzureCredential）。
- 成本护栏：给资源组设 50 美元预算告警；所有资源打上 `env` 和 `owner` 标签；比赛结束后执行 `azd down --purge`。

## 后果

- **正面**：评审期的环境可以随时重建；公开仓库里没有任何密钥；赛后清理只需一条命令。
- **负面**：Bicep 模板约占 A 半天时间。
- **风险**：RBAC 授权生效有几分钟延迟，部署后立刻冒烟测试可能失败。缓解办法是在部署后的钩子里先等待，再带重试执行冒烟测试。
