# 给写代码的 Agent

先读 [CONTRIBUTING.md](CONTRIBUTING.md)，下面几条是在它之上对 Agent 的额外要求。

## 每一份工作都要有自己的 issue

看板：https://github.com/orgs/neubayarea/projects/1

1. **开工前**，确认这份工作对应看板上的哪个 issue，并且它指派给了让你干活的那位同学。没指派就先认领：
   `gh issue edit <编号> -R neubayarea/Pivot --add-assignee @me`，再把看板上的 Status 改成 In progress。
2. **要做清单以外的事**（顺手修的 bug、补的工具、拆出来的子任务、重构、文档），先给它开一个 issue 并认领到自己这条线，再动手：

   ```bash
   python3 scripts/new_task.py --line B --phase 1 --title "一句话中文标题" \
       --why "这是在做什么、为什么要做" --done "做完是什么样" --from B03 --estimate 1 --apply --start
   ```

   脚本会建好 `Bx1 · …` 这样的 issue，指派给当前 gh 账号，加入看板并填好负责线、阶段和 Status。
   `--line` 填让你干活的那位同学负责的线，`--phase` 填现在所处的阶段。先不加 `--apply` 预览一次。
3. 一个额外任务一个 issue，一个 PR。PR 描述写 `Closes #编号`，分支和提交用这个 ID，例如 `b/Bx1-sim-logging`、`Bx1: …`。
4. 不要把额外的改动塞进别的任务的 PR 里。发现的问题不打算马上做，也照样开 issue，只是不加 `--start`，留在 Ready。
5. 不要改别人线上的 issue 的指派或状态；需要别人配合时，在那个 issue 下留言。

## 开工前先确认没人在做同一件事

#284 曾经被两个人同时做，出了三个 PR（#289、#290、#293）。为了不再撞车：

1. **开工前先查**：这个 issue 有没有人认领、最近有没有人留言、有没有挂着的 PR（`gh issue view <编号> -R neubayarea/Pivot --comments`，再搜一下 `gh pr list -R neubayarea/Pivot --search "<编号>"`）。也看一眼负责这条线的同学手上正在做的 issue 和 PR，是不是同一件事。有人在做，就在 issue 下问，不要直接开工。
2. **开工时在 issue 下留言**：写清楚谁在做、做哪一部分、大概什么时候交。只改指派和看板状态不够，别人不一定会看。
3. **建 issue 时不要去掉指派**。要交给别人做，就在 issue 下 @ 对方，由对方自己认领。
4. **别人那条线上的事**，先在 issue 下 @ 那位同学，等对方确认再动手。

## 写 issue 的方式

标题和「这是在做什么」用通俗中文，让没有计算机背景的同学也看得懂。技术细节写在 PR 里。

## 不要做的事

- 不直接推送到 `main`，不强推，不改看板字段和选项的结构。
- 不把生成的比赛数据（`.pivot-data/`、批量生成的 `*.json.gz` 等）提交进仓库，规则见 [docs/match-data.md](docs/match-data.md)。
- 不把密钥、令牌写进仓库或 issue。Plane 的密钥只在 `~/.config/pivot/plane.env`，不要打印它。
- `docs/plan/tasks.csv` 是原始清单，只有在开会决定改计划时才改；额外任务只在 GitHub 上开，不写进这个文件。
