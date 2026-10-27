# 比赛数据放在哪

一句话：**生成出来的比赛数据存在服务器的硬盘上，不放进 GitHub。**

## 为什么不放进 GitHub

一场模拟比赛连同每秒一帧的跑位数据，压缩后也有几 MB。比赛越生成越多，仓库会越来越大：每个人克隆、拉代码都变慢，GitHub 对单个文件和整个仓库也有大小限制。而且这些数据随时能重新算出来，没有必要保存。

## 那数据从哪来

同一个种子（seed）加同一版模拟器，生成的比赛一模一样。所以服务器只要记住「生成哪几场」，就能自己把比赛算出来：

1. 服务启动时，在后台把要展示的几场比赛模拟出来（`PIVOT_SIM_MATCHES`，默认 20 场），不耽误网站打开。
2. 算好的结果写到服务器硬盘上的 `PIVOT_DATA_DIR/sims/` 文件夹。
3. 下次重启时，文件已经在了就直接读，不用再算。改了模拟器或统计的代码，版本号会变，服务会自动重新生成。

代码在 `apps/api/src/pivot_api/sims.py`。要增减比赛，改那里的比赛列表（种子），不要提交生成的文件。

**网站默认打开哪一场**：比赛列表（`GET /api/matches`）按这份种子列表的顺序排，**第一场就是默认比赛**（现在是种子 101，`M-seed-101`）。这是一条固定规则，不看比赛结果挑。顶栏的比赛选择也按这个顺序。打开一个已经不存在的旧链接（例如以前的 `?match=M-seed-29`），网站会换成默认比赛，并在顶栏下面提示一句。

**20 场要算多久**：2 核的服务器上第一次启动（或改了模拟器之后）大约 1 分半钟（按以前 6 场约 25 秒推算）；算好一场列表里就多一场，网站不用等全部算完。以后重启直接读硬盘，几秒钟。想连这 1 分半也省掉，就在多核电脑上用 `scripts/sims_blob.py` 预先生成并传到 Blob，见下面「模拟比赛放到 Azure Blob」。

**`eval/fixtures/demo-1021.json` 只给测试用**：它是一场提交进仓库的固定比赛（连同 `demo-1021.frames.json.gz`），自动测试拿它当基准，每台电脑上都一样。网站上默认**不放**这场（Ax55）。

- 本机想把它放进比赛列表：设 `PIVOT_DEMO_FIXTURE=1`（或者写另一个文件的路径）；不设或设 `0` 就不加载；
- 手写的样例比赛 `M-api-demo`（`apps/api/src/pivot_api/demo.py`，解说是手写的，没经过 AI 和核对员）只给自动测试用，网站上默认不放；本机前端调试要它，设 `PIVOT_SAMPLE_MATCH=1`；
- 重新生成它用 `uv run scripts/make_demo.py --seed 29`。

**虚构联赛的赛季结果（season-2026.json）也提交了**：测试用的这场固定比赛的近况、积分榜、交锋记录、生涯和新闻都从它算出来（B13，见《数据定义说明》CTX-005）。它只有 294 场的比分、进球人、红牌、换人和每个上场球员的评分，没有事件和跑位帧，约 270 KB。提交它是为了让这个世界固定下来：模拟器以后改了，这场比赛的背景也不会跟着变。要重算就先跑 `uv run scripts/make_season.py`（12 核电脑上 3 到 6 分钟），再跑 `make_demo.py --seed 29`。

## AI 写的结果也存在硬盘上

AI 小组给每个转折点写的东西，也存在同一块硬盘上，重启后直接读回来，不再调用模型：省钱，而且录好的 Demo 里的文字不会因为重启变掉。

存的是：

- 每个候选转折点的结果：确认的、被判定「不是转折点」的、模型写了但没通过核对的，连同它的解释；
- 模型写的、按观众口味改写的版本（语言、球迷/分析师、关注的球队和球员）；
- AI 的工作记录（每一步的判断、写稿、核对，S4 页面上看到的那些）。

放在 `PIVOT_DATA_DIR/results/<比赛>/<版本>/` 下面，分 `pivots/`、`narratives/`、`traces/` 三个文件夹，一条结果一个小 JSON 文件。服务启动时先把这场比赛的结果读回来，再把候选转折点交给 AI 小组；已经有结果的，AI 小组直接跳过。

「假如」重踢的结果（A09）也存在这里的 `scenarios/` 文件夹：同一个问题（同一个转折点、同一种改动、同样的参数和次数）再问一次就直接给答案，不再重踢。比赛的版本一变，这些结果也一起作废。

「版本」跟着比赛本身走：

- 模拟比赛用模拟器的版本号（和 `sims/` 里的文件一样）。改了模拟器或统计代码，比赛变了，旧的解释就不用了，会重新写，旧文件夹自动删掉。
- 测试用的 demo-1021（只在 `PIVOT_DEMO_FIXTURE` 打开时加载）用 `eval/fixtures/demo-1021.json` 文件内容的指纹。重新生成这个文件，解释就会重新写。
- 改了提示词或换了模型，**不会**自动重写：Demo 要的就是文字稳定。想重写，用下面的办法。
- 模型当时调不通（超时、限流、报错）、只好退回模板文字的转折点，**不算数**：下次启动时会重新调用模型去写，连同它那次的工作记录一起丢掉。刚启动时几场比赛同时调模型，最容易被限流，这样不会让模板文字一直留着。
- 模型写了、但三次都没通过核对而退回模板的，算数，会存下来；模型判定「不是转折点」的，也算数。
- 按观众口味改写的版本，只存模型写的；退回模板的那种下次有人看时再写一遍。

想让 AI 重新写：

- 全部重写：在 Dokploy 的 Environment 里加或改 `PIVOT_RESULTS_TAG`（随便一个新值，比如 `2`），重新部署。旧结果会被删掉，所有转折点重新调一次模型。
- 只重写一场：删掉 `/data/results/<比赛>/` 这个文件夹（比如 `M-seed-101`），再重启。
- 完全不存（每次重启都重新写）：`PIVOT_RESULTS=0`。

手写的样例比赛 `M-api-demo`（只在 `PIVOT_SAMPLE_MATCH=1` 时加载）本来就是写死的，不存。代码在 `packages/pivot_adapters/src/pivot_adapters/local/results.py`。

### 存到 Azure Cosmos DB

也可以不存硬盘，存到 Azure 的 Cosmos DB 数据库里（Ax11），服务器自己就不用保存 AI 的结果。规则和上面完全一样（版本、退回模板的不算数、`PIVOT_RESULTS_TAG`），只是换了地方。在 Dokploy 的 Environment 里加两行，重新部署：

```
PIVOT_RESULTS_BACKEND=cosmos
PIVOT_COSMOS_ENDPOINT=https://pivot-cosmos.documents.azure.com:443/
```

- 登录用已经填好的 `AZURE_TENANT_ID`、`AZURE_CLIENT_ID`、`AZURE_CLIENT_SECRET` 服务主体，不用密钥；自己电脑上用 `az login` 的身份。数据库名默认 `pivot`，要换就设 `PIVOT_COSMOS_DATABASE`。
- 启动时连不上 Cosmos（地址错、没权限、网络不通），日志里会有一行 `results backend CosmosResults unavailable ... keeping the AI's results on disk instead`，然后照旧存硬盘，网站照常打开。去掉 `PIVOT_RESULTS_BACKEND` 或改回 `files` 就是原来的样子。从硬盘换到 Cosmos 时，硬盘上已有的结果不会搬过去，第一次启动会重新调一次模型。
- 数据在 `pivot` 数据库的 `results` 容器里，按比赛分区（`/match_id`），一条结果一条记录。容器用数据库共享的 1000 RU/s 免费额度，**不要**给它单独设吞吐量，否则会收费。启动时每场比赛只查一次自己的分区，一场大约 2–3 RU；写一条大约 5 RU。
- 服务主体只有数据读写权限，建不了容器。容器已经建好；要是删了或换了账号，用自己的 `az login` 建一次：

  ```bash
  az cosmosdb sql container create -g rg-pivot -a pivot-cosmos -d pivot -n results -p /match_id
  ```

- 只重写一场：在 Azure 门户的 Data Explorer 里删掉这场比赛的记录，或者整体改 `PIVOT_RESULTS_TAG`。
- 代码在 `packages/pivot_adapters/src/pivot_adapters/azure/cosmos.py`。连真实账号的测试默认跳过，`PIVOT_COSMOS_IT=1 uv run pytest packages/pivot_adapters/tests/test_azure_cosmos.py` 才会跑，它只写一个叫 `it-ax11` 的比赛，跑完自己删掉。

## 模拟比赛放到 Azure Blob

默认模拟比赛只存服务器硬盘，服务器自己 20 场大约 1 分半钟就能算完，所以**这一步不是必须的**，是为了比赛多（几十场）时不用每次都在 2 核的服务器上重新算（Ax15）。

规矩：**Blob 是正本，硬盘是缓存。** 服务启动时每场比赛按顺序试：

1. 硬盘上已经有当前版本的文件，直接用；
2. 没有，就看 Blob 里有没有这个版本，有就下载到硬盘（先下到临时文件，检查完整了才改名，所以下载一半或者坏掉的文件会被忽略）；
3. 都没有，才自己模拟，算完写到硬盘，并传一份到 Blob。

网站读跑位数据（`/frames`）还是读硬盘，所以和以前一样快。Blob 连不上、没权限、容器不存在，日志里会有一行 `simulated-match store ... unavailable`，然后完全照老办法只用硬盘，网站照常打开。

在 Dokploy 的 Environment 里加：

```
PIVOT_SIMS_BACKEND=blob
```

`PIVOT_BLOB_ENDPOINT` 已经填过了；容器名默认 `sims`，要换才加 `PIVOT_BLOB_CONTAINER`。登录用已有的 `AZURE_*` 服务主体，不用密钥。容器不存在时服务会试着建；服务主体没权限建的话，日志里会给出要自己运行的这条命令：

```bash
az storage container create --account-name pivotstore1024 --name sims --auth-mode login
```

文件名和硬盘上一样：`M-seed-101.<版本号>.json.gz` 和 `M-seed-101.<版本号>.frames.json.gz`，版本号就是 `SIM_VERSION`。服务器不会自己删旧版本，用下面的脚本清。

### 在自己电脑上生成并上传

用 `scripts/sims_blob.py`，先 `az login`。文件用服务器同一份代码生成，字节完全一样，先放在 `./.pivot-data/sims/`（不进 git），再传到 Blob。

```bash
export PIVOT_BLOB_ENDPOINT=https://pivotstore1024.blob.core.windows.net/
uv run scripts/sims_blob.py generate-upload --count 50   # 前 50 场，规则同 PIVOT_SIM_MATCHES；也可以 --seeds 101,212
uv run scripts/sims_blob.py list                         # Blob 里每个版本有几场、多大
uv run scripts/sims_blob.py clean                        # 演练：列出不是当前版本的文件，不删
uv run scripts/sims_blob.py clean --yes-delete           # 确认后真的删
```

云端已经有当前版本的比赛会自动跳过；传到一半断了，重新运行同一条命令只补没传的。每次运行开头都会打印当前的 `SIM_VERSION`。用时参考（10 核的 Mac，上传另算在内）：6 场约 6 MB、约 5 秒；50 场约 52 MB、约 25 秒。一场约 1 MB。

### 改了模拟规则之后怎么办

**先说清楚：** `SIM_VERSION` 是模拟器和统计代码算出来的指纹。队友一改规则，版本号就变，**改之前传上去的文件全部作废，服务器不会再用它们。** 所以要等规则改完、合并之后再传，传早了白传。

1. 把改规则的 PR 合并到 `main`，本地 `git pull`。
2. 运行 `uv run scripts/sims_blob.py generate-upload --count N`（N 是要几场）。
3. 重新部署或重启服务器，它会从 Blob 下载新版本，不用自己算。
4. 可选：运行 `uv run scripts/sims_blob.py clean --yes-delete`，删掉旧版本的文件。

忘了第 2 步也不会出事：服务器找不到当前版本，就退回自己模拟（20 场约 1 分半钟），算完还会传上去。区别只是启动后要多等一会儿。

## 放在哪个文件夹

| 在哪跑 | 文件夹 | 说明 |
| --- | --- | --- |
| 自己电脑上 | `./.pivot-data/sims/`、`./.pivot-data/results/` | 默认位置，已经写进 `.gitignore`，不会被提交 |
| 服务器（pivot.in-stacks.com） | `/data`（`PIVOT_DATA_DIR=/data`） | 在 Dokploy 里挂了一个名叫 `pivot-data` 的卷到 `/data`，重新部署也不会丢 |

服务器用 Dokploy 部署。新建或重建这个应用时，记得在 Dokploy 里设好：

1. Pivot 应用 → Advanced → Volumes → Add Volume，类型选 Volume Mount，名字 `pivot-data`，挂载路径 `/data`。
2. Environment 里加一行 `PIVOT_DATA_DIR=/data`，保存后点 Deploy。

## 哪些能提交，哪些不能

可以提交：

- 生成比赛的**代码**和**种子列表**。
- `eval/fixtures/` 里的固定样例，比如测试用的 `demo-1021`。它是测试的基准，体积小、只有一场，是唯一的例外。要往这里加新文件，先在群里说一声。

不要提交：

- `.pivot-data/` 里的任何东西。
- 自己批量生成的比赛文件（`*.json`、`*.json.gz`、`*.frames.json.gz`），不管放在哪个文件夹。
- 任何几 MB 以上的数据文件。拿不准就先问。

提交前看一眼 `git status`，出现上面这些文件就别加进去。已经误提交了，在 PR 里删掉就行；已经合进 `main` 的，在群里说，别自己改历史。
