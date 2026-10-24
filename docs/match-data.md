# 比赛数据放在哪

一句话：**生成出来的比赛数据存在服务器的硬盘上，不放进 GitHub。**

## 为什么不放进 GitHub

一场模拟比赛连同每秒一帧的跑位数据，压缩后也有几 MB。比赛越生成越多，仓库会越来越大：每个人克隆、拉代码都变慢，GitHub 对单个文件和整个仓库也有大小限制。而且这些数据随时能重新算出来，没有必要保存。

## 那数据从哪来

同一个种子（seed）加同一版模拟器，生成的比赛一模一样。所以服务器只要记住「生成哪几场」，就能自己把比赛算出来：

1. 服务启动时，在后台把要展示的几场比赛模拟出来（`PIVOT_SIM_MATCHES`，默认 6 场），不耽误网站打开。
2. 算好的结果写到服务器硬盘上的 `PIVOT_DATA_DIR/sims/` 文件夹。
3. 下次重启时，文件已经在了就直接读，不用再算。改了模拟器或统计的代码，版本号会变，服务会自动重新生成。

代码在 `apps/api/src/pivot_api/sims.py`。要增减比赛，改那里的比赛列表（种子），不要提交生成的文件。

**录 Demo 用的那场（demo-1021）不一样**：它已经提交在 `eval/fixtures/demo-1021.json` 和 `demo-1021.frames.json.gz` 里。服务启动时直接读这两个文件，不重新模拟，所以每台电脑、服务器上看到的都是同一场，也就是网页默认打开的那场。

- 换别的文件：设 `PIVOT_DEMO_FIXTURE`；
- 不要这场：设 `PIVOT_DEMO_FIXTURE=0`；
- `PIVOT_DEMO=0` 时，它和手写样例 `M-api-demo` 都不加载。
- 重新生成它用 `uv run scripts/make_demo.py --seed 41`。

**虚构联赛的赛季结果（season-2026.json）也提交了**：演示比赛的近况、积分榜、交锋记录、生涯和新闻都从它算出来（B13，见《数据定义说明》CTX-005）。它只有 294 场的比分、进球人、红牌和换人，没有事件和跑位帧，约 100 KB。提交它是为了让这个世界固定下来：模拟器以后改了，演示比赛的背景也不会跟着变。要重算就先跑 `uv run scripts/make_season.py`（12 核电脑上 3 到 6 分钟），再跑 `make_demo.py --seed 41`。

## 放在哪个文件夹

| 在哪跑 | 文件夹 | 说明 |
| --- | --- | --- |
| 自己电脑上 | `./.pivot-data/sims/` | 默认位置，已经写进 `.gitignore`，不会被提交 |
| 服务器（pivot.in-stacks.com） | `/data`（`PIVOT_DATA_DIR=/data`） | 在 Dokploy 里挂了一个名叫 `pivot-data` 的卷到 `/data`，重新部署也不会丢 |

服务器用 Dokploy 部署。新建或重建这个应用时，记得在 Dokploy 里设好：

1. Pivot 应用 → Advanced → Volumes → Add Volume，类型选 Volume Mount，名字 `pivot-data`，挂载路径 `/data`。
2. Environment 里加一行 `PIVOT_DATA_DIR=/data`，保存后点 Deploy。

## 哪些能提交，哪些不能

可以提交：

- 生成比赛的**代码**和**种子列表**。
- `eval/fixtures/` 里的固定样例，比如录 Demo 用的 `demo-1021`。它是测试和演示的基准，体积小、只有一场，是唯一的例外。要往这里加新文件，先在群里说一声。

不要提交：

- `.pivot-data/` 里的任何东西。
- 自己批量生成的比赛文件（`*.json`、`*.json.gz`、`*.frames.json.gz`），不管放在哪个文件夹。
- 任何几 MB 以上的数据文件。拿不准就先问。

提交前看一眼 `git status`，出现上面这些文件就别加进去。已经误提交了，在 PR 里删掉就行；已经合进 `main` 的，在群里说，别自己改历史。
