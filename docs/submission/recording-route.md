# 录制前的展示路径

演示比赛：Tessmouth United 4–3 Vantry Town。此页是操作顺序，配音与字幕仍使用 video-script.md 和 video-captions.srt。

## 先准备

- 只开一个网站窗口，1920 × 1080、100% 缩放。等最后一次部署完成，再运行预热脚本；录制时停止预热和并行检查。
- 起始链接是比赛中心首页，明确清除上次选队和球员（一定带 `lang=en`，否则首页会跟随浏览器语言显示中文）：
  https://pivot.in-stacks.com/?lang=en&mode=analyst&team=none&player=none
- 先把下面的路径走一遍。若翻译显示“暂未就绪”，等待真实译文准备好再录，不能把摘要说成模型已经完成的解释。

## 按这个顺序展示

1. **比赛中心 → 概况：为什么转折。** 先在比赛中心停 2 秒（Live now、Next round），滚到 Results 点 Tessmouth United 4–3 Vantry Town，展示带队徽的比分条（队徽在队名上方、时钟在比分上方），随后滚到转折点①，展示文字解释和数字来源。转折标在 12′，关联进球在 17′：应描述为“势头变化与随后进球的关联”，不能说 17′ 的进球造成了 12′ 的变化。核对标记只表示检查了列出的数字和事件，不代表已经证明因果。
2. **球迷视角和语言。** 选球迷及 Tessmouth United，查看同一时刻的球队视角，切换中文、西语再回英文。使用当前实际显示的核对数量，不把旧稿中的数量当作固定值。
3. **关注球员。** 在概况的 Best player 处点 ☆ Follow 关注 D. Sahaltessen，展示顶部的“D. Sahaltessen's match”时间线和下方的球员焦点（Their shots / Their passing / Heatmap）。不要往下滚到“In the turning points”和故事卡②：那里标题拼错成“Sahltessen”。
4. **假如。** 先在球迷视角看“The biggest what-ifs of this match”列表，点“What if Z. Sadoseno's 17′ goal hadn't counted?”这一行（已存储，立即打开），展示 34% → 50%；再切到分析师视角，展示同一结果的 +16pts、Clear difference、95% 区间和“◆ ranges do not overlap”。不要点 Run simulation，也不要点其他行。
5. **回放。** 使用视频稿的 `from=76` 链接（球场上关注的球员带金色“★ Sahaltessen”标记），暂停后把球场进度条定位到约 73:40，再以 5× 播放，74:02–74:03 左右进球，比分 3–2 → 4–2。先彩排确认进球能落在分配的 9 秒内，录制只保留播放片段。
6. **定位球。** 球迷版概况中的 Set pieces & shots，选择 7′ 的任意球，展示人墙和片段。
7. **赛前和阵容。** 展示近况、下场比赛；确认已选 Tessmouth United，再进入阵容展示对位与教练安排。分析师的换人表只是前后观察，不能说它证明了换人造成的效果。
8. **收尾。** 展示技术与合成数据声明；按 video-script.md 的结束卡录制。

## 若额外展示模拟直播

https://pivot.in-stacks.com/?match=S2026-29-BRI-FAL&live=1&tab=replay&mode=analyst&team=none&player=none&lang=zh

- 分析师：顶部先看最近十分钟的四项指标与趋势，下方是默认开启阵型线和传球线路的战术球场、可筛选事件。球迷：大球场，右侧是势头、三项直观数据和比赛大事。
- “机会质量”只把已经发生的射门重新模拟，不是对剩余比赛的胜率预测。
- 两队名单默认收起；点球场上的球员后会展开其详情。事件列表内部滚动，完整比赛数据位于列表下方。
