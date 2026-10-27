# 网站为什么用起来怪：数据盘点、专业网站对照、现成工具（2026-10-26）

> 给 Carry3 读。这是 momomojun 和 Claude 在 10-26 晚上讨论的完整记录，按发生顺序整理：
> - 第 0 节：读完 Carry3 最新的 issue 以后，需要更正或补充的地方；
> - 第 1 节：momomojun 的原话；
> - 第 2 节：Claude 给 momomojun 的完整汇报；
> - 第 3 节：之后做了什么、决定了什么；
> - 附录 A–D：三份调研的原始报告，以及搜到的 skill 清单。
>
> 读的时候按 **main `3f2f197`** 和线上 https://pivot.in-stacks.com/ （种子 101）对照。两者是同一个版本：线上网页文件的名字和本地打包出来的一样，`index-lEq4Vkn4.js` / `index-BiyT97vs.css`。

---

## 0. 读完 Carry3 最新消息后的更正和补充

写汇报时（10-26 下午）还没看到 Carry3 后来开的 issue。对照以后，有这几处要更正：

1. **手机端先不管**（momomojun 后来的决定）。现在只管电脑上的网页。
   - #276 第一批里"修手机横向溢出"这一项可以拿掉。
   - #278 验收里的"手机 375 宽没有横向滚动"也可以先不做，省下的时间放到电脑版上。
   - 补充：手机溢出 Carry3 在 #259 里**比这份汇报更早**就发现了，而且查得更准：只有英语和西语会溢出，中文没有。汇报里没有区分语言，以 #259 为准。
2. **"顶部比分区 + 分页"已经由 #278 认领。** Carry3 的分法是**赛前 / 赛中 / 赛后**三页，每页有自己的网址，默认打开赛中。汇报里建议的是 7 个标签（概况、转折点、假如、阵容与战术、数据、赛前、AI 工作记录）。两种都可以，三页更简单，**以 #278 为准**。汇报里的"阵容与战术""数据"可以放进赛后（或赛中）页里做成分块。
3. **"赛前"和"教练的安排"已经由 #280 认领**：近期战绩、积分榜、交锋、新闻、场外因素，以及两队战术并排对比。这覆盖了汇报第三批的前两项。
4. **个性化比汇报写的要好一些。** #263（Ax49）已经做了三件事：关注球员弹出球员卡，选了主队标题会站在那一队，球迷卡更有情绪。Claude 在更早的一次回答里说过"选球员只会在事件列表里做标记"，那是 #263 之前的情况，已经不对了；这次走查线上时，球员卡已经能正常弹出。汇报里说这些按钮"藏在设置里"，这一点仍然成立，#278 会把视角切换拿出来。
5. **"假如"结果已经讲成一句故事**（#262 / Ax51），并列出最常见比分、两边射门、xG 和红牌。附录 A 指出还缺进球、控球、黄牌和波动范围，这几项仍然成立。
6. **球迷模式显示分析师原文时现在会提示了**（#260 / Ax50）。
7. **比赛数据接口已经开 PR：#279**（Refs #276），一个接口给出 23 项 MET 数据，分全场和每个半场，也能取"截至第几秒"。每一项都带说明文字和分组，分组照英超官网的进攻 / 控球 / 防守 / 体能 / 纪律。合并后网页的"比赛数据"就可以不再自己算。
8. **#276 里还没有人认领的**：
   - 射门图、热区图、传球网络；
   - 球员卡补齐缺的几项；
   - "假如"补上进球、控球和波动范围；
   - 数据页做成分组表格（等 #279 合并）。

---

## 1. momomojun 的问题（原话）

> 1. 战术有显示吗，或者赛前教练安排能显示吗？有显示吗？现在网站上呈现的数据和我们有的数据有多少差距，我们真的用到了各种数据吗？
> 2. 你觉得现在这个UI设计真的合理吗？我感觉整个网站用起来很怪，你能不能找一些案例学习一下，告诉我怎么样更好
>
> 我希望你找现成的，好用的，如果有什么skill你也可以找来用，还有好的github项目有关的，然后再给我汇报

为此分头做了四件事：
- 逐项核对"我们有的数据"和"网站显示的"（附录 A）；
- 研究 FotMob、Sofascore、英超官网等专业网站（附录 B）；
- 在 GitHub 和 npm 上找现成的开源项目（附录 C）；
- 在 skills.sh 上找设计类 skill（附录 D）。

Claude 还在电脑和手机两种尺寸下，把线上网站从头到尾走了一遍。

---

## 2. 给 momomojun 的完整汇报

### 一、战术和教练安排有显示吗？数据用上了多少？

**战术和教练安排完全没有显示。** 数据我们都有，后台也已经发给网页了，只是网页在读取时把这些丢掉了。网页整理比赛数据的地方是 `apps/web/src/data/live/provider.tsx` 第 197–230 行（`toView`），那里只留下了队名、颜色、球员名单和阵型。

我们的数据一共有 42 类：**14 类显示了，8 类只显示了一部分，20 类完全没显示。** 后台已经发出 42 类里的 38 类，差距几乎全在网页这边。

**完全没显示的（数据都有）：**
- **战术**：压迫高度、防线高度、阵型宽度、节奏、定位球安排等十几项；
- **教练**：执教风格、偏好阵型、能力；
- **赛前**：近期战绩、积分榜排名、交锋记录、新闻、球员生涯和老东家、球员之间的关系、场外影响；
- **球员能力**：34 项能力值；
- **射门图、热区图、传球网络**：每个事件都有位置数据，但从来没有把一整场汇总起来画出来；
- **球员数据里没显示的几项**：预期助攻（xA）、推进传球、过人、冲刺等。

**还有一个比较严重的问题：** 网页上的"比赛数据"是浏览器自己算的 5 个数字，没有用我们定义好的 23 项数据（MET-001…023）。比如控球率，网页用的是"传球次数占比"，和我们的定义不一样。结果就是 AI 解释里说的数字，可能和页面上显示的对不上。

### 二、为什么网站用起来怪

在电脑尺寸和手机尺寸下都走了一遍线上网站，又研究了 FotMob、Sofascore 和英超官网的比赛页面。

**我们的问题：**
1. **第一屏没有比分区。** 比分只在顶栏里占很小一块，进球人、比赛时间都没有放大；第一屏最显眼的是一大段标题和介绍文字（"The 3 moments that changed the course of this match"）。
2. **最基本的东西藏得最深。** 球迷最常看的阵容、数据、事件，都收在页面最底下的"更多详情"里。
3. **我们的特色被藏起来了。** 球迷 / 分析师、选主队、关注球员都放在"设置"下拉菜单里，评委很可能根本找不到。
4. **文字太密。** 解释是一段段长句，句子里夹满 `#904` 这类证据编号。
5. **手机上页面会横向溢出。** 在 375 宽的手机上页面宽到 456，溢出的元素是 `span.kicker`、`h1`、`p.lede`。（见第 0 节：只有英语和西语会溢出，#259；现在决定先不管手机。）
6. **"假如"慢。** 没提前算好的选项，在线上要等好几分钟；本地重踢 200 次也要约 3 分钟。

**专业网站的通行做法：**
- **顶部有一个固定的比分区**：两队、比分、进球人、"关注"按钮，往下滚也一直在。
- **下面用标签页分开内容**，每个标签都有自己的网址，方便直接分享。英超官网的顺序是：概况、集锦、阵容、数据、积分榜、文字直播、比赛信息。
- **势头图和"最重要的几项数据"放在同一张卡片里**，图上直接标出进球。
- **阵容画在球场上**，上方有一排按钮可以切换显示评分、跑动距离、最高速度等。
- **射门图**可以一个一个点着看每次射门。
- **解释分层**：先给一句话，想看证据再点开。

**有两个空白正好是我们的机会：**
- **没有一家网站讲清楚"教练是怎么布置战术的"**，都只写个阵型。我们有完整的战术数据，可以做出别人没有的东西。
- **没有一家网站有真正的球迷 / 分析师切换。** Sofascore 的赛前预测（AI Insights）还要付费才能用。所以我们的视角切换和"假如"都是独有的，应该放在最显眼的地方，不该藏起来。

评委来自微软和英超，英超官网的比赛页又是和微软合作做的（顶栏有 Copilot 的入口）。照着英超官网的格局来排，评委会觉得很熟悉。

### 三、现成能用的

**Skill**（详见附录 D；安装要下载第三方的东西，所以还没装）：
- `anthropics/skills@frontend-design`：100 万次安装，Anthropic 官方出的前端设计规范；
- `vercel-labs/agent-skills@web-design-guidelines`：78.7 万次安装，Vercel 官方出的网页设计检查清单，适合拿来给现在的网站挑毛病；
- `pbakaus/impeccable`：36.3 万次安装，界面打磨，作者不是官方，备选。

**GitHub 开源项目**（详见附录 C，都核实过确实存在，也看过许可证）：

| 项目 | 许可证 | 能做什么 | 接入要多久 | 风险 |
|---|---|---|---|---|
| [Campos](https://github.com/withqwerty/campos) | MIT | React 组件：射门图、传球网络、热区图、阵型 | 每个图 1–2 小时 | 还是测试版、只有 11 颗星，要锁定版本，先试一个图 |
| [simpleheat](https://github.com/mourner/simpleheat) | BSD-2 | 很小的热区图，叠在我们自己画的球场上 | 不到 1 小时 | 低 |
| [d3-soccer](https://github.com/probberechts/d3-soccer) | BSD-3 | 球场直接按 105×68 米画，和我们的坐标一致 | 几小时 | 不是 React 写的，要包一层 |
| [mplsoccer](https://github.com/andrewRowlinson/mplsoccer) | MIT | Python 画图，可以当后备方案，生成图片 | 约 1 小时 | 低 |

势头图、事件时间线和数据对比条不建议用库，我们自己写的比现成的更合适。网上那些 FotMob / Sofascore 的仿制项目都没有许可证，只能看，不能抄。

### 四、建议怎么改

（按第 0 节更正后的版本。）

**第一批（必须做）：**
- ~~修手机上的横向溢出~~：先不管手机；
- 把球迷 / 分析师、选主队、关注球员这几个按钮从"设置"里拿出来，放到比分区旁边（#278）；
- 比赛数据改用我们定义好的 23 项，不要浏览器自己算（后台 #279）。

**第二批：** 照英超官网改成"固定比分区 + 分页"，即 #278 的赛前 / 赛中 / 赛后三页。

**第三批（挑着做）：**
- **教练的安排**：阵型加上压迫高度、防线高度、节奏，这是别人都没有的（#280）；
- **赛前资料**：近期战绩、积分榜、交锋记录、新闻和故事线（#280）；
- **射门图和热区图**：用 Campos 或 simpleheat，还没人认领；
- 球员卡和"假如"补齐缺的几项，还没人认领。

---

## 3. 之后做了什么、决定了什么

- **10-26 晚**：开了 issue #276 给 Carry3，内容是上面的改进清单。
- **比赛数据接口**：momomojun 要求"把这些比赛数据都做个接口，让网页可以拿到"，于是开了 #277，PR 是 #279（`[contract]`），审查人 Carry3。
- **Carry3 认领了**：
  - #278（顶部比分区 + 赛前 / 赛中 / 赛后三页）；
  - #280（赛前页 + 两队教练的战术安排）；
  - #259（手机溢出，更早就开了）。
- **momomojun 决定：手机端先不管，现在只管电脑上的网页。**

---

## 附录 A：数据盘点（我们有什么 / 后台发什么 / 网站显示什么）

原始报告，基于 main `3f2f197`。

**后台接口概况。** `GET /api/matches/{id}`（`routes.py:87`）会返回整个 `Match`：两队、带能力和性格的球员名单、教练、首发和战术，还有完整的 `context`。所以几乎所有数据后台都在发，差距几乎全在后台和网页之间。

其他接口：
- `routes.py`：`/matches`、`/sims`、`/timeline`（MinuteMetric）、`/events`（MatchEvent）、`/frames`（TrackingFrame）、`/matches/{id}/pivots`、`/pivots/{id}`、两个 `/traces`、`/overlay`、`/overlay/timeline`、`/negotiate`；
- `players.py:104`：`/players/stats`（PlayerStatsReport）；
- `whatif.py:616-648`：`/pivots/{id}/scenarios`、`POST /scenarios`、`/scenarios/{id}`（Scenario，含 SimResult）；
- `realtime.py:30`：WebSocket 消息。

（写这份报告时）没有接口发出这几样：
- 球队数据表 MET-001…023（现在由 #279 补上）；
- `PivotCandidate`；
- `Recap`、`OverlayFeed` / `OverlayItem`。

**网页从哪里读比赛数据。** `data/live/provider.tsx:197-230`（`toView`）只留下：
- 队的 `name`、`short_name`、`side`、`color`；
- 球员的 `player_id`、`name`、`shirt_number`、`role`；
- `home.sheet` / `away.sheet`。

教练、战术、能力、性格和 `context` 全都丢掉了。在 `components/`、`pages/`、`data/` 里搜（不算测试），下面这些字段**一处都没有用到**：`coach`、`personality`、`attributes`、`career`、`relationship`、`.news`、`head_to_head`、`last_results`、`league_position`、`effect_id`、`.context`、`referee`、`weather`、`venue`、`competition`、`captain_id`、`penalty_taker`。任何地方都没有热区图、传球图或射门图。

### 对照表

| 数据 | 我们有（位置） | 后台发？ | 网站显示？ |
|---|---|---|---|
| 队名 / 简称 / 颜色 | `match.py` Team | 是 | 是：TopBar 和各处 |
| 球员 id / 名字 / 号码 / 位置 | `people.py` Player | 是 | 是：Roster、FocusPickers、PlayerCard |
| 球员资料（年龄、国籍、身高、体重、惯用脚、逆足、花式、工作积极性、副位置、特质，约 12 项） | `people.py:165` | 是 | 否 |
| 34 项能力 + 6 项汇总评分 | `people.py` PlayerAttributes | 是 | 否 |
| 性格（11 项） | `people.py:140` | 是 | 否（注释里写着"不在屏幕上显示"） |
| 教练（名字、年龄、风格、偏好阵型、4 项能力、性格、生涯） | `people.py:205` | 是 | 否 |
| 首发阵型和首发位置（以及事件里带的阵型变化） | `lineup.py` | 是 | 是：PitchBoard 的 ShapeTable（`PitchBoard.tsx:202`）、`shape.ts lineupAt` |
| 首发表里的队长、定位球主罚、替补名单 | `lineup.py` TeamSheet | 是 | 否（替补状态是从跑位数据推出来的，不是读名单） |
| 战术 TeamTactics（10 项 + 定位球战术 6 项 + 指令） | `lineup.py:57` | 是 | 否（只在"假如"按钮里出现"压低 / 提高压迫"，`scenarios.ts:193`） |
| 生涯 CareerStint（12 项） | `people.py` | 是 | 否 |
| 球员之间的关系 | `people.py` | 是 | 否 |
| 新闻（OffFieldEvent） | `context.py` | 是 | 否 |
| 赛事、球场、天气、草皮、比赛意义、观众人数、裁判 | `context.py`、`officials.py` | 是 | 否 |
| 近期战绩 / 联赛排名 / 积分 | `context.py` TeamForm | 是 | 否 |
| 交锋记录 | `context.py` | 是 | 否 |
| 赛前状态 PreMatchCondition（体能、士气等） | `context.py` | 是 | 否 |
| 场外影响 ContextEffect | `context.py` | 是 | 否（只会出现在解释的句子里，`context_ids` 不显示） |
| 赛季文件（290 场比分 + 4 次交锋） | `eval/fixtures/season-2026.json`、`sim/season.py` | 间接（只给 demo-1021 填 context，`make_demo.py:50`） | 否 |
| 事件基本信息（类型、队、球员、接球人、时间、结果） | `events.py` | 是 | 是：EventFeed |
| 起点 / 终点位置 | `events.py` | 是 | 只有单个事件：`Pitch.tsx:72-83` 画箭头（转折点证据、最近的射门、某一次定位球） |
| 射门：xG、结果 | `events.py` | 是 | 是：EventFeed、SetPieces、KeyMoments |
| 射门：技术动作、射门高度、门将位置、用哪个部位 | `events.py` | 是 | 否 |
| 传球：类型 | `events.py` | 是 | 部分：只有角球 / 任意球 |
| 传球：高度、技术、传法、球速、成功概率 | `events.py` | 是 | 否 |
| 进攻方式、控球段编号 | `events.py` | 是 | 部分：判断定位球、按射门来源筛选 |
| 犯规 / 出牌 / VAR | `officials.py` | 是 | 部分：牌的颜色、判点球、VAR 改判（KeyMoments） |
| 威胁值、是否被逼抢、反抢、对抗类型、门将动作、受伤 | `events.py` | 是 | 否 |
| 跑位 x/y + 球的 x/y/控球人 | `tracking.py` | 是 | 是：PitchBoard、ClipPlayer、定位球站位 |
| 跑位速度、体能、球的高度 z | `tracking.py` | 是 | 否（`setpieces.ts:258` 插值算了 z，但没画出来） |
| 球队数据 MET-001…023 | `analytics/stats.py`、`docs/data-definitions.md:427` | 只作为解释里引用的数字 | 部分，见下 |
| 球员比赛数据（21 项） | `outputs.py` PlayerMatchStats、`ratings.py` | 是 | 部分：21 项里显示 14 项 |
| 每分钟势头 | `momentum.py` MinuteMetric | 是 | 是：MomentumChart |
| 每分钟威胁值 / 压迫次数 | MinuteMetric | 是 | 否 |
| 转折点（标题、句子、证据、引用的数据、严重程度、状态、方向） | `pivots.py`、`narrative.py` | 是 | 是：Moments、WhyItTurned、PivotList、PivotDetail |
| 报警器的原始结果 PivotCandidate（累计值、摆幅） | `pivots.py` | 否 | 否 |
| 转折前后的数据对比表 | 只在 `pivot-detail.ts` 测试数据里 | 否 | 只有测试数据（`provider.tsx:233` 发的是 `beforeAfter: []`） |
| "假如"胜平负、95% 区间、是否明显 | `scenarios.py` | 是 | 是：Distribution、Ranges；`home_advance` 不显示（`scenarios.ts:36` 的 `OUTCOMES` 只有 3 个） |
| "假如"新字段 ArmStats | `scenarios.py:61-99` | 是 | 部分，见下 |
| AI 工作记录 | `traces.py` | 是 | 是：AgentTraces |
| 叠加层的画面 / 时间线 | `outputs.py` | 是 | 是：Overlay 页 |
| 赛后报道 Recap、OverlayFeed / OverlayItem | `outputs.py` | 否 | 否 |

**球队数据。** `MatchStats.tsx` 显示的 5 个数，是浏览器自己算的（`view.tsx computeStats`），不是 MET 值：
- "控球"是传球次数占比，不是 MET-001 按跑位帧算的数；
- 射门和 xG 与 MET-006、MET-008 一致；
- 压迫与 MET-010 一致；
- "前场传球"算的是所有**从前场开始**的传球，不管成功没有，和 MET-004 不一样。

阵型表里的防线位置、宽度、纵深，是浏览器从跑位帧算的，和 MET-016/017 接近，但用了所有帧（`shape.ts:1-6`）。其余 MET 值从来没有以表格形式出现过，只作为数字出现在解释句子里：MET-002/003、005、007、009、011–015、018–023。

**球员数据。** 球员卡（`PlayerCard.tsx:19-28`）显示：上场时间、评分、进球、助攻、射门、xG、传球及成功率、关键传球、抢断成功、拦截、对抗成功、跑动距离；球迷模式还会加上最高速度。从来不显示：xA、推进传球、过人成功、争顶成功、犯规、扑救、冲刺。接口返回的 `event_ids` 也没用上，只显示了转折点链接。

**"假如"新字段。** `WhatIf.tsx:232-252` 显示最常见的 3 个比分及占比，以及两边的平均射门、射正、xG 和红牌。不显示：进球、控球（`possession_pct`）、黄牌（只算了红牌）、`scored_share`（进了至少一球的比例），以及任何数字的波动范围（sd / p10 / p90）。

**射门图、热区图、传球图。** 都不存在。位置数据只用来画单个事件的箭头和实时的球员点，从来没有把一整场汇总起来。

**统计。** 42 类数据里：
- **显示了 14 类**；
- **部分显示 8 类**：首发表的其他信息（替补）、传球类型、进攻方式、犯规 / VAR、球队数据、球员数据、"假如"胜平负、"假如"新字段；
- **完全没显示 20 类**：教练、战术、能力、性格和所有赛前资料都在这一类。

42 类里后台只有 4 类没发：PivotCandidate、转折前后对比表、Recap 和 OverlayFeed。

---

## 附录 B：专业网站怎么排比赛页

原始报告。

**看了哪些、没看到哪些。** 实际打开看了 FotMob、Sofascore 和英超官网的比赛页（阿森纳对埃弗顿 2026-10-24，曼城对阿森纳 2026-04-19），读了 Sofascore、Flashscore、Stats Perform 和英超的官方文章。BBC Sport 打不开（工具屏蔽了这个网站）。ESPN、谷歌比赛卡和 Opta Analyst 没搜到比赛页的说明。也没找到 FotMob 或 Sofascore 设计师自己写的设计复盘，只有一些概念作品集。下文说"没找到"，意思是没找到，不代表不存在。

### FotMob（https://www.fotmob.com/match/4813701）
- **第一屏**：比分、进球人和"关注"按钮组成页头。标签依次是：Facts（概况）、Commentary（文字直播）、Lineup（阵容）、Table（积分榜）、Stats（数据）、Head-to-Head（交锋）。
- **Facts 页是一整条长页面**，顺序是：比赛回顾卡片 → 势头图和核心数据并排 → 事件 → 带评分的阵容 → 教练 → 替补 → 近期战绩 → 全场最佳 → "谁会赢？"投票。右边栏放集锦、球场、裁判和其他比赛。
- **势头图**：平滑的上下对称面积图，主队在横轴上方、客队在下方；进球图标标在进球那一分钟，在横轴上方或下方；横轴写 0'、HT、FT。它和核心数据并排放：控球条，然后是 xG、射门、禁区内触球，再加一个"全部数据"链接。上线时官方叫它"比赛走势图"（https://www.appgefahren.de/?p=333215）。
- **射门图**：放在 Stats 页，可以选全场 / 上半场 / 下半场。球场上方有一条详情栏，用箭头一个个切换射门，显示球员、分钟、射门方式、情形、结果，还有一个球门示意图和 xG / xGOT。
- **阵容**：球场上画出阵型，每个球员带评分。上方一排切换按钮（跑动距离、最高速度、身价、年龄、国家、Fantasy、数据）改变球员点上显示的内容。换人的分钟标在球场上，教练和替补列在下面。
- **事件**：中间一列是分钟，主队事件在一边，客队在另一边，包括进球和助攻、红黄牌（教练吃牌也算）、换人。
- **赛前**：页面标题里写着预测阵容（开赛前约一小时确认）、近期战绩、交锋和投票（https://www.fotmob.com/matches/fc-motown-vs-new-york-city-fc-ii/uite9j17）。

### Sofascore（https://www.sofascore.com/football/match/everton-arsenal/RY）
- **标签**：Lineups（阵容）、Statistics（数据）、Standings（积分榜）、H2H（交锋）、Media（媒体）、AI Insights（AI 洞察）。比赛势头是左栏的一个小组件，带说明图标：绿蓝两色、上下对称的柱状图，标出进球。
- **阵容页**：两层切换（阵容 / 球员数据）。一排按钮（表现、跑动、国籍、年龄、身价、身高、Fantasy）切换球员点上显示的内容。每队阵型旁边有全队平均评分，例如 8.12 对 7.51。另见 https://www.sofascore.com/news/?p=70924。
- **数据页**：先是势头，然后一篇推荐文章，再是事件流。之后是全场最佳（Sofascore 评分旁边放球迷投票）、三个社区投票，以及可以按"全部 / 关键事件"筛选的文字直播。
- **评分**：每个球员从 6.5 分起，算法会看上下文，比如推进传球比安全回传加分多，比赛过程中实时更新（https://sofascore.helpscoutdocs.com/article/50-sofascore-statistical-ratings-explained、https://www.sofascore.com/news/sofascore-rating-breakdown-what-goes-into-calculations/）。
- **势头的计算依据**：危险区域的传球、射门、定位球、反击。文章说它同时面向球迷和分析师（https://www.sofascore.com/news/how-sofascores-attack-momentum-changed-sport-analysis）。
- **AI Insights**：要付费的 Pro 标签，承诺在开赛前最多 3 天给出胜率、结果预测和战术分析。**这是和我们"假如"最接近的竞品。**
- **解释**：页面底部有一块"关于这场比赛"，用文字描述势头图。

### 英超官网（https://www.premierleague.com/en/match/2645265/arsenal-vs-everton/stats 和 …/lineups）
- **页头和标签**：左边一张固定的比分卡（比分、半场比分、进球人、裁判、球场）。标签依次是：Recap（回顾）、Highlights（集锦）、Lineups（阵容）、Stats（数据）、Table（积分榜）、Commentary（文字直播）、Match Info（比赛信息），每个标签都有自己的网址。网站提供英语、西语、阿拉伯语和泰语。
- **回顾**：一篇文字战报，有一节"比赛是怎么发展的"，还有全场最佳投票。
- **数据页**：最上面是势头，红蓝两色上下对称的面积图，标出进球，横轴是 KO / HT / FT。然后是核心数据（控球条和 xG），再往下是分组表格：进攻、控球、防守、体能、纪律。
- **阵容页**：一个横向球场同时画两队，标出阵型和队长，换人分钟写在球员旁边，写了主教练名字，没有评分。
- **和微软有关的**：Matchday Live 号称提供经过核实的比分、数据和报道；myPremierLeague 按你选的球队和球员推送提醒；有一个基于 Azure 的 Copilot "Companion"；还宣布将推出多语言问答和实时数据叠加（https://www.premierleague.com/en/news/4337361/premier-league-launches-new-fan-facing-platforms-as-part-of-digital-transformation、https://www.premierleague.com/en/about/partners/microsoft）。页面顶栏有 "Copilot by Microsoft" 入口。

### 其他
- **Flashscore**：势头是每分钟一根柱子，柱子越高，进球的可能性越大。数据来自 Opta 的模型，给每个控球事件打分，放在数据页（https://www.flashscore.com/news/momentum/W82o7eCa/）。
- **MLS MatchCenter**：标签是阵容、事件流、技术统计、数据、前瞻、视频。在任何地方点球员名字都会弹出球员卡。前瞻页放交锋记录和近期战绩（https://www.mlssoccer.com/news/follow-action-new-way-mlssoccercoms-brand-new-matchcenter）。
- **谷歌**：实时图表，可以关注一支球队，在锁屏上看比分。AI 模式能现场生成交互图，比如讲解阵型（https://www.blog.google/products-and-platforms/products/search/fifa-world-cup-google-tools-2026/）。
- **Opta**：Opta Vision（跑位 + 事件数据）加了阵型变化指标（https://www.statsperform.com/press/stats-perform-to-launch-opta-vision/）；Opta Stream 是托管的多语言比赛中心，会自动生成洞察（https://www.statsperform.com/opta-stream/）。

### 战术和"教练布置了什么"
- 没有一家网站明确讲战术，都只显示阵型、教练名字、换人分钟和教练吃的牌。
- Sofascore 有一个"平均站位"的数据，但没确认页面上有没有这个标签（https://scraperfc.readthedocs.io/en/latest/sofascore.html）。
- **这块是空白，正好留给我们。**

### 普通球迷和分析师
- 没有一家有真正的模式切换。
- 它们的做法是分层：先给简单的核心数据，再给一个"全部数据"链接；文字直播可以只看关键事件；球场上方有切换按钮；还有社区投票。
- Sofascore 在帮助文章里解释各项指标，不是在图上加提示框。

### 最值得借鉴的 10 个做法
1. **上下对称的势头图**：主队在上、客队在下，横轴写 0' / HT / FT，进球图标钉在图上。我们的转折点标记也放在同一张图上。（FotMob、英超、Sofascore）
2. **势头图和核心数据放在同一张卡片里**，一行看完，不用切标签。（FotMob）
3. **页头一直在**：比分、进球人、关注按钮在每个标签都看得到；每个标签有自己的网址，录视频时可以直接跳过去。（FotMob、英超）
4. **第一个标签是概况**（回顾、势头、事件、阵容），细节放到后面的标签。
5. **球场上方加一排切换按钮**：在评分、年龄、跑动等之间切换。可以加一个"谁改变了比赛"按钮，配合转折点和球迷模式用。（FotMob、Sofascore）
6. **一个个切换的详情栏**：用箭头一次次切换射门，详情显示在球场上方。转折点也可以这样切：分钟、起因、证据、核实标记。（FotMob）
7. **解释分层**：先一句"为什么重要"，点一下再看证据。Sofascore 在图旁边配文字说明和说明图标，我们讲转折点时可以照这个来。
8. **"假如"做成一个标签或抽屉，而不是另一个网站。** Sofascore 的预测要付费，英超只有一个通用的 Copilot 框。一个看得见的"假如"，把前后的胜平负放在同一条坐标轴上对比，就是我们的特色。
9. **关注一支球队或一个球员时，页面跟着变**：他的评分、射门和事件钉在时间线上，在球场上高亮。（谷歌锁屏关注、英超 myPremierLeague）
10. **评分对比**：阵型旁边写全队平均评分；全场最佳旁边放球迷投票；再加上我们模型选出的"最关键球员"。（Sofascore）

**视角和语言。** 两种视角用同一份数据：球迷模式把 xG 和逐行数据表收到"全部数据"后面；分析师模式打开英超式的分组表格，点一下就能看到 Opta 的定义。所有 AI 写的文字都要翻译，不只是标签。英超官网提供四种语言，我们的英文 / 中文 / 西文和它是一个水平。

---

## 附录 C：能直接用的开源项目

原始报告。所有仓库都在 2026-10-26 通过 GitHub API 或 npm 实际查过。

**结论：** 我们要的大部分东西只有一个真正对口的库：**Campos**，一个用 React + TypeScript 写的足球图表库。但它很新，还是测试版，所以有风险。其余都是小工具。没找到可以直接用的 FotMob / Sofascore 仿制项目，看过的几个都没有许可证，等于保留所有权利，不能抄。

**1. Campos** — https://github.com/withqwerty/campos
- **能做什么**：React 组件，包括 `Formation`、`ShotMap`、`PassNetwork`、`Heatmap`、`KDE`、`XGTimeline`、`PizzaChart`、`RadarChart`、`PassMap`。文档在 https://campos.withqwerty.com。
- **数据**：11 颗星，2026 年 4 月创建，最后一次提交 2026-07-13，MIT 许可证。npm 包 `@withqwerty/campos-react` 版本 0.1.0-beta.4，每周约 450 次下载，要求 React 18 或 19。安装后约 2.7 MB（这是安装大小，不是打进网页的大小）。
- **和我们的数据**：它用自己的格式，x 和 y 都是 0–100，从左往右进攻。我们的 105×68 米坐标按 x/105×100、y/68×100 换算，y 方向要对照它的文档确认是否要翻转。射门需要 `outcome` 字段，`xg` 可选。
- **接入**：几小时，一个图大约 1–2 小时，时间主要花在把我们的事件转换成它的射门和传球格式。
- **能替代**：我们手画的射门图、传球网络、热区图和阵型球场。
- **风险**：测试版，只有一个维护者，文档是写给 AI 看的，接口可能会变。锁定具体版本，只用在一两个图上。

**2. d3-soccer** — https://github.com/probberechts/d3-soccer
- **能做什么**：D3 插件，球场直接按 105×68 画，有网格热区图、事件散点（带位置、提示框和球队颜色）和比分条，还有 `rectbin` 和 `grid` 两个工具。
- **数据**：78 颗星，BSD-3 许可证，npm 版本 0.3.0（2024 年 12 月），最后一次提交 2025 年 3 月，每周约 66 次下载。包约 170 KB，会带进几个小的 d3 模块。
- **和我们的数据**：坐标最对得上，直接用米，原点在左上角。
- **接入**：几小时。它是 D3 的命令式写法，不是 React，也没有 TypeScript 类型，要放在 `useEffect` 里调用。
- **能替代**：球场绘制、热区图、球场上的事件。没有被放弃，但更新不多。

**3. react-soccer-lineup** — https://github.com/giustini/react-soccer-lineup
- **能做什么**：React + TypeScript 的球场，显示两队首发。按位置（`gk`、`df`、`cm`、`fw`）摆放球员，带号码、名字、颜色、草皮花纹，可以横放或竖放。
- **数据**：58 颗星，最后一次提交 2026-06-13，最后推送 2026-10-17。npm 版本 1.0.0-beta.12，约 150 KB，每周约 260 次下载。
- **许可证有风险**：npm 上写的是 MIT，但 GitHub 仓库里没有 LICENSE 文件，许可证不明确。
- **和我们的数据**：不接受 x/y 坐标，按行摆放，要把阵型转换成一行行；没有事件叠加。
- **接入**：不到 1 小时。
- **能替代**：只是首发阵容的画面，纯外观。要按真实坐标或平均站位来画，就用 Campos 的 `Formation` 或我们自己的 SVG。

**4. simpleheat** — https://github.com/mourner/simpleheat
- **能做什么**：很小的 canvas 热区图，约 10 KB。
- **数据**：957 颗星，BSD-2 许可证，2026-10-26 还有推送，每周约 3.1 万次下载。
- **和我们的数据**：画在我们的 SVG 球场下面或上面，米换算成像素要自己做；没有类型定义，要自己写一个简短的 `.d.ts`。
- **接入**：不到 1 小时。
- **能替代**：把一格一格的热区图换成平滑的。
- **不要用** `heatmap.js`（https://github.com/pa7/heatmap.js）：6.4k 颗星、MIT，但最后一次提交是 2023 年 10 月，基本没人维护了。

**5. Recharts** — https://github.com/recharts/recharts
- **能做什么**：通用的 React 图表库。势头图可以用它的 `BarChart`（每分钟一根柱子），进球和红牌用 `ReferenceDot` 或 `ReferenceLine` 标出来；数据对比条也可以用 `BarChart`。
- **数据**：2.77 万颗星，MIT，2026-10-26 还有推送，每周约 5100 万次下载，版本 3.10，TypeScript 写的，维护得很好。
- **代价**：安装后约 7.4 MB，要注意打包体积。
- **接入**：几小时。
- **结论**：没有专门画足球势头的库。我们自己写一个约 80 行的 SVG 柱状图一样好，除非想白拿提示框和动画，否则不用引入。数据对比条用普通 CSS 就行，不需要库。

**其他图表库。** `@nivo/*`（https://github.com/plouc/nivo）：1.4 万颗星、MIT，最后推送 2026 年 7 月，核心约 250 KB，依赖很重。`@visx/*`（https://github.com/airbnb/visx）：2.1 万颗星、MIT、v4.0，是底层的 SVG 积木。两者都没有球场或势头图，只会加体积、对足球没帮助，这次截止前不用。

**Python 这边**（都不会进浏览器，只能在后台准备数据和图片）：
- `mplsoccer` — https://github.com/andrewRowlinson/mplsoccer。553 颗星，MIT，最后提交 2026-09-14。用 Matplotlib 画球场、射门图、热区图和传球网络。可以在后台生成 PNG 或 SVG，作为任何一个图出问题时的后备。接一个接口大约 1 小时。
- `kloppy` — https://github.com/PySport/kloppy。568 颗星，BSD-3，很活跃（2026-10-24）。读取并统一各家的事件和跑位数据。数据来源多时有用，我们的数据已经很干净，可以不用。
- `socceraction` — https://github.com/ML-KULeuven/socceraction。823 颗星，MIT，活跃（2026-10-18）。SPADL 动作格式加 xT / VAEP 评分，不是这一天要做的事。
- `floodlight` — https://github.com/floodlight-sports/floodlight。134 颗星，MIT，最后提交 2026 年 5 月，主要处理跑位数据，跳过。
- `databallpy` — https://github.com/Alek050/databallpy。106 颗星，MIT，活跃，主要做跑位和事件数据对齐，跳过。
- `soccerdata`（https://github.com/probberechts/soccerdata）是抓数据的工具，GitHub 上显示许可证不明确。有用的仓库里没看到 GPL 的，但看到的其他足球仪表盘都没有许可证。

**要避开或只能参考的**
- 足球网站仿制项目：`nickng852/fotmob-clone`（4 颗星）、`Hbadr13/sofascore-clone`（2 颗星）等都没有许可证，只能看，不能抄。
- npm 上的 `soccer-pitch`（https://github.com/nluna15/soccer-pitch-playground）：0 颗星，许可证不明确，带着 framer-motion 有 1.7 MB，跳过。
- `@football-coach/pitch` 和 `@football-coach/lineup`：npm 上写 MIT、版本 0.0.x，但打不开它们的 GitHub 仓库，无法核实，跳过。
- 老包 `react-native-football-lineup`（2019）和 `11-builder`（2018）：都已经没人维护了。
- `nivo` 和 `visx`：没有足球相关的部分，见上面"其他图表库"。

**只剩约 1 天时，最值得做的 5 个（快、风险低）**
1. **Campos 的 `ShotMap` 和 `PassNetwork`**：每个约 2 小时，锁定 0.1.0-beta.4。先试射门图（坐标换算成 0–100），一小时内搞不定就放弃，继续用我们自己的 SVG。画面提升最大，但有测试版的风险。
2. **simpleheat**：不到 1 小时，在现有球场上画平滑的热区图。BSD-2，安全。
3. **参考 d3-soccer 的球场画法**（可选）：只有需要更好的球场或带提示框的 105×68 事件图时才用；否则就照它的源码画我们自己的线（BSD-3，要注明出处）。
4. **势头柱状图、事件时间线和数据对比条用我们自己的 SVG**，现成的都不如自己写的小组件合适。想要提示框的话，只给势头图加 Recharts。
5. **react-soccer-lineup**：不到 1 小时就能有更好看的阵型图，但前提是能接受 GitHub 上许可证不明确；否则用 Campos 的 `Formation`。

**后台的后备方案**：mplsoccer。没放进上面 5 个是因为接起来要花时间，但任何一个图出问题时，它都是安全的 B 计划。

---

## 附录 D：搜到的 skill（skills.sh，用 `npx skills find` 搜的）

| Skill | 安装量 | 来源 | 说明 |
|---|---|---|---|
| `anthropics/skills@frontend-design` | 100 万 | Anthropic 官方 | 前端设计规范 |
| `vercel-labs/agent-skills@web-design-guidelines` | 78.7 万 | Vercel 官方 | 网页设计检查清单，适合给现在的网站挑毛病 |
| `leonxlnx/taste-skill@design-taste-frontend` | 68.3 万 | 个人 | 前端审美，来源不是官方，慎用 |
| `leonxlnx/taste-skill@redesign-existing-projects` | 45.9 万 | 个人 | 改版现有项目，来源不是官方，慎用 |
| `nextlevelbuilder/ui-ux-pro-max-skill@ui-ux-pro-max` | 41.6 万 | 个人 | 界面和交互，来源不是官方，慎用 |
| `pbakaus/impeccable@impeccable` | 36.3 万 | 个人 | 界面打磨 |

安装命令（装在全局，需要的人自己装）：

```bash
npx skills add anthropics/skills@frontend-design -g -y
npx skills add vercel-labs/agent-skills@web-design-guidelines -g -y
```

momomojun 的电脑上还没有安装任何一个。
