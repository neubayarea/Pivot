# 部署到甲骨文（Oracle Cloud）Ubuntu 虚拟机

这份文档写给没做过运维的同学。照着做完，你会得到一个 `https://…` 的公网网址，打开就是 Pivot 的看板。

## 先弄懂它是怎么跑的

整套系统打成**一个 Docker 镜像、一个进程**：接口（含实时推送的 WebSocket）、AI 小组（worker）、模拟器、网页文件，都在这一个程序里，数据放在内存里（`PIVOT_PROFILE=local`）。前面再放一个 **Caddy**，负责 HTTPS 证书和把请求转给程序。

```
浏览器 ──https/wss──▶ Caddy（80/443，自动证书） ──▶ app（8000，单进程）
```

要知道的后果：

- **重启就清空数据**。程序重启后只剩自带的演示比赛，这是有意的（演示用）。
- **生成的比赛存在服务器硬盘上，不进 GitHub**。启动时自己生成，存到 `PIVOT_DATA_DIR`，详见 [比赛数据放在哪](match-data.md)。
- **只能跑一份**。实时推送只在同一个进程里有效，不要开多个 app 容器。

用到的文件都在 [`deploy/oracle/`](../deploy/oracle)：

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 启动 app 和 Caddy 两个容器 |
| `Caddyfile` | Caddy 的配置：用哪个域名、转发到哪 |
| `.env.example` | 需要填的设置项，复制成 `.env` 再填 |
| `deploy.sh` | 更新代码并重新部署，一条命令 |

本机想先试试，不用 Docker 也行：

```bash
pnpm install && pnpm --filter web build
```

```bash
uv run python -m pivot_api.single
```

然后打开 http://127.0.0.1:8000 。

## 1. 创建虚拟机

1. 登录 [Oracle Cloud 控制台](https://cloud.oracle.com/)，左上角菜单 → **Compute → Instances → Create instance**。
2. **Image**：点 Change image，选 **Canonical Ubuntu 24.04**（22.04 也可以）。
3. **Shape**：点 Change shape，二选一：
   - **Ampere（ARM）`VM.Standard.A1.Flex`**：免费层，建议 2 个 OCPU、12 GB 内存。镜像能在 ARM 上构建，不用担心。
   - **x86 `VM.Standard.E2.1.Micro`**：也免费，但只有 1 GB 内存，构建镜像会很慢，可能失败。有付费额度就选 `VM.Standard.E4.Flex`（1 OCPU、8 GB）。
   - 免费的 ARM 机器经常显示 “Out of capacity”，换一个 Availability domain 再试，或者过一会儿再试。
4. **Networking**：保持默认，新建 VCN 和公共子网，确认勾选了 **Assign a public IPv4 address**。
5. **Add SSH keys**：选 Generate a key pair for me，**两个文件都下载下来**（私钥丢了就登不上了）。也可以上传自己的公钥。
6. 点 Create。等状态变成 Running，在详情页记下 **Public IP address**，下面用 `<公网IP>` 代表它。

## 2. 在云控制台放行 80 和 443（安全列表）

甲骨文默认只开放 22（SSH）。

1. 实例详情页 → **Primary VNIC** 下面的 **Subnet** 链接 → **Security Lists** → 点默认的那个（Default Security List for …）。
2. **Add Ingress Rules**，加两条：
   - Source CIDR `0.0.0.0/0`，IP Protocol `TCP`，Destination Port Range `80`
   - Source CIDR `0.0.0.0/0`，IP Protocol `TCP`，Destination Port Range `443`
3. 保存。

> 如果子网用的是 Network Security Group（NSG），在 NSG 里加同样的两条规则。

## 3. 登录虚拟机

Mac / Linux 终端里（把私钥路径换成你下载的文件）：

```bash
chmod 600 ~/Downloads/ssh-key-*.key
```

```bash
ssh -i ~/Downloads/ssh-key-XXXX.key ubuntu@<公网IP>
```

用户名是 `ubuntu`。下面的命令都在虚拟机里执行。

## 4. 在虚拟机里放行 80 和 443（iptables）——最容易漏的一步

**甲骨文的 Ubuntu 镜像自带一套 iptables 防火墙规则，默认把 80 和 443 挡住了**。只改第 2 步的安全列表不够，网页会一直打不开（连接超时）。

看一下现在的规则：

```bash
sudo iptables -L INPUT -n --line-numbers
```

通常能看到最后一条是 `REJECT ... reject-with icmp-host-prohibited`。要把放行 80、443 的规则插在它**前面**。先装保存规则的工具：

```bash
sudo apt-get update && sudo apt-get install -y iptables-persistent
```

（装的时候问要不要保存当前规则，选 Yes。）然后插入规则（插在第 6 行，一般在 REJECT 之前；如果上一步看到 REJECT 在别的行号，就把 6 换成那个行号）：

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
```

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
```

保存，这样重启后还在：

```bash
sudo netfilter-persistent save
```

再看一次 `sudo iptables -L INPUT -n --line-numbers`，确认 80 和 443 的 ACCEPT 在 REJECT 上面。

> 不要用 `ufw`，也不要直接清空 iptables（`iptables -F`），甲骨文的规则里有虚拟机正常工作需要的条目。

## 5. 装 Docker

用 Docker 官方脚本，ARM 和 x86 都适用：

```bash
curl -fsSL https://get.docker.com | sudo sh
```

让 `ubuntu` 用户不用 sudo 也能用 docker：

```bash
sudo usermod -aG docker ubuntu
```

**退出再重新 ssh 登录**一次，让上面的设置生效。检查：

```bash
docker run --rm hello-world
```

```bash
docker compose version
```

## 6. 克隆仓库

仓库是私有的，需要能读它的 GitHub 账号。最简单的是在虚拟机上用 GitHub CLI 登录：

```bash
sudo apt-get install -y gh git
```

```bash
gh auth login
```

（按提示选 GitHub.com → HTTPS → Login with a web browser，在自己电脑上打开网址输入验证码。）然后：

```bash
gh repo clone neubayarea/Pivot ~/Pivot
```

## 7. 填 `.env`

```bash
cd ~/Pivot/deploy/oracle && cp .env.example .env && nano .env
```

至少要改 `PIVOT_DOMAIN`：

- 有自己的域名：先在域名服务商那里加一条 A 记录指向 `<公网IP>`，然后填这个域名，例如 `pivot.example.com`。
- 没有域名：用 sslip.io，把公网 IP 的点换成横线，例如 IP `140.238.1.2` 填 `140-238-1-2.sslip.io`。不需要注册，直接能用。

AI 相关的几项（`PIVOT_PIPELINE`、`PIVOT_FOUNDRY_*`、`PIVOT_MODEL_*`、`AZURE_*`）找 D 线同学要。不填也能启动，AI 部分会用固定的假解释。`nano` 里 Ctrl+O 回车保存，Ctrl+X 退出。

`.env` 里有密钥，**不要提交到 git，不要发到群里**（`.gitignore` 已经忽略了它）。

用 Dokploy 部署时没有 `.env` 文件：把 `.env.example` 里的各行复制到应用的 Environment 页再改值。注意 `PIVOT_WS_URL` 要自己填成 `wss://<域名>/api/ws`，`PIVOT_DATA_DIR` 填挂了持久卷的文件夹（例如 `/data`）。

## 8. 启动

```bash
cd ~/Pivot/deploy/oracle && docker compose up -d --build
```

第一次要构建镜像，ARM 免费机器上大约 3–5 分钟。好了以后：

```bash
docker compose ps
```

两个容器都是 `Up`，app 显示 `healthy`，就可以在浏览器打开 `https://<PIVOT_DOMAIN>`。第一次访问时 Caddy 要去申请证书，可能要等十几秒。

## 9. 更新到最新代码

`main` 合并了新东西以后，在虚拟机上：

```bash
~/Pivot/deploy/oracle/deploy.sh
```

它会拉取 `main` 的最新代码、重新构建、重启，最后打印网址。要部署别的分支：`deploy.sh 分支名`。

## 10. 看日志

```bash
cd ~/Pivot/deploy/oracle && docker compose logs -f app
```

Ctrl+C 退出。看 Caddy（证书、代理问题）把 `app` 换成 `caddy`。只看最近 200 行：`docker compose logs --tail 200 app`。

## 11. 回滚

新版本有问题，退回到上一个能用的版本：

```bash
cd ~/Pivot && git log --oneline -10
```

找到想退回的那次提交（例如 `5b07004`），然后：

```bash
cd ~/Pivot && git checkout 5b07004 && cd deploy/oracle && docker compose up -d --build
```

问题修好后，再跑一次 `deploy.sh` 就会回到 `main` 的最新版。

## 常见问题

| 现象 | 原因和办法 |
| --- | --- |
| 浏览器一直转圈、连接超时 | 80/443 没放行：检查第 2 步的安全列表和第 4 步的 iptables |
| 证书错误 / Caddy 日志里有 `challenge failed` | `PIVOT_DOMAIN` 没指向这台机器的公网 IP，或者 80 端口不通。改好后 `docker compose restart caddy` |
| 页面能开，但实时推送不动 | 看浏览器开发者工具里 WebSocket 的地址应是 `wss://<PIVOT_DOMAIN>/api/ws/...`；改了 `.env` 里的域名后要 `docker compose up -d` 重新创建容器 |
| `docker compose up` 构建时内存不够被杀 | 机器太小（1 GB）。换 Ampere 机器，或者加 swap：`sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| 频繁重建后申请证书被拒（rate limit） | 不要删 `caddy_data` 卷（`docker compose down -v` 会删），证书存在里面 |
| 想停掉 | `cd ~/Pivot/deploy/oracle && docker compose down` |

## 设置项一览

| 变量 | 说明 |
| --- | --- |
| `PIVOT_DOMAIN` | 公网域名，Caddy 用它申请证书，网页的 WebSocket 地址也由它拼出来 |
| `PIVOT_DEMO` | `1` 启动时放入演示比赛，`0` 空着启动 |
| `PIVOT_WORKER` / `PIVOT_SIMULATOR` | `1` 在同一个进程里运行 AI 小组 / 模拟器，`0` 关掉（模拟器的实时入口还没做，做好后自动启用） |
| `PIVOT_PIPELINE` | `fake` 用固定解释，`detect` 用真正的判定、写稿、核对流程（D06） |
| `PIVOT_FOUNDRY_ENDPOINT`、`PIVOT_FOUNDRY_API_VERSION`、`PIVOT_MODEL_STANDARD`、`PIVOT_MODEL_MINI` | Foundry 模型的地址和部署名，D 线提供 |
| `AZURE_TENANT_ID`、`AZURE_CLIENT_ID`、`AZURE_CLIENT_SECRET` | 虚拟机不在 Azure 里，用服务主体登录 Azure 去调模型，D 线 / A 线提供。三个要一起填；填了密钥就只用这个服务主体登录 |
| `PIVOT_WEB_DIST` | 网页文件的位置，镜像里已经设好，不用填 |
| `PIVOT_SIM_MATCHES` | 启动时生成几场模拟比赛，默认 6，`0` 不生成 |
| `PIVOT_DATA_DIR` | 生成的比赛和 AI 写的结果存在哪个文件夹，要指向一块持久的硬盘卷，例如 `/data`。不设就存在容器里，重新部署就丢，见 [比赛数据放在哪](match-data.md) |
| `PIVOT_RESULTS` | `1`（默认）把 AI 写的结果存到 `PIVOT_DATA_DIR/results/`，重启后读回来不再调模型；`0` 只放在内存里 |
| `PIVOT_RESULTS_TAG` | 默认空。改成一个新值再部署，就丢掉存下的结果、让 AI 全部重写，见 [比赛数据放在哪](match-data.md) |
