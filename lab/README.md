# lab/140t：Arc 140T 笔记本实验记录

本分支只存放实验手册、结论和测量工具，不放引擎代码。引擎代码的改动走功能分支（目前是
`local-v0.1.43.1-intel-npu`）。只推送到 `jielin99/Strata-codex`，不推上游，不动 `main` 和 tag。

当前目标：让 Strata 在 Windows 11 + Arc 140T 笔记本上**生成（decode）更快**。总体计划和已确认的事实见
`lab/HISTORY.md` 开头。

## 目录

| 路径 | 谁写 | 内容 |
|---|---|---|
| `lab/plans/NN-<名字>.md` | 开发机 | 执行手册，编号从 00 开始 |
| `lab/results/NN-<名字>.md` | 笔记本上的 Codex | 对应手册的结论摘要 |
| `lab/results/NN-<名字>/` | 笔记本上的 Codex | 可公开的结构化数据（tsv、json、md），每个文件不超过 200 KB |
| `lab/tools/` | 开发机 | 测量工具源码，编译到笔记本的 `build-lab-*` 目录 |
| `lab/HISTORY.md` | 开发机 | 每轮一行的履历 |

原始数据（日志、dmp、exe、zip 等）留在笔记本的 `D:\dev\strata-lab\NN-<名字>\`，**不提交**。

## 笔记本的准备（只做一次）

全部用 CMD。引擎所在的 checkout 保持在 `local-v0.1.43.1-intel-npu`，实验分支用独立的 worktree：

```
git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git lab/140t:lab/140t
git -C D:\dev\Strata-intel-npu worktree list
git -C D:\dev\Strata-intel-npu worktree add D:\dev\Strata-lab140t lab/140t
```

如果 `worktree list` 显示 `lab/140t` 已经在别处检出，就直接用那个目录，不要再 add。
worktree 和主 checkout 共用同一份 git 配置，不算隔离。手册里的引擎、模型和 build 目录一律写绝对路径。

## 推送步骤（两边都照做）

1. 确认当前目录在 `lab/140t` 上（`git branch --show-current`），而且 `git status --short` 里没有别人的改动。
2. 先同步：`git fetch git@github.com:jielin99/Strata-codex.git lab/140t`，再 `git rebase FETCH_HEAD`。
3. 只 `git add` 自己负责的路径（开发机：`lab/plans` `lab/tools` `lab/HISTORY.md` `lab/README.md`；
   笔记本：`lab/results`），提交。
4. 推送：`git push git@github.com:jielin99/Strata-codex.git HEAD:lab/140t`，**不加 `--force`**。
5. 推送被拒绝时回到第 2 步，最多重试 3 次，还失败就停下来报告。

## 能提交什么（公开仓库）

**可以**：
- 测量数字的表格，每个数字注明原始文件名和行号（原始文件本身不提交）。
- 引擎日志里的行，但要**逐字段检查**：把路径、提示词和回答内容、异常文本删掉或换成 `<path>`、`<text>`。
- 用到的开关（`STRATA_*`、`SYCL_*`、`UR_*`）和命令行参数，其中路径换成 `<model>`、`<repo>` 这类占位符，
  `--api-key` 的值一律删掉。
- 公开模型文件里的张量清单（名字、类型、形状、字节数）。
- 结论、推断（标「推断」）和没有验证的事项。

**不可以**：原始日志、dmp、exe、pdb、map、zip、带用户名的路径（`C:\Users\...`）、进程列表、
主机名、IP、MAC、安全软件名、完整的环境变量导出、API key。

## 提交前自查（每份手册的最后一步）

1. 对**所有待提交文件的全文**（不只是 diff）、文件名、提交说明，以及 `git log FETCH_HEAD..HEAD` 里还没推送的
   每个提交，做不区分大小写的关键字搜索。关键字有两部分：
   - 固定部分：`Users\`、`Users/`、`AppData`、`api-key`、`api_key`、`Bearer`、`.dmp`、`.pdb`。
   - 本机部分：读 `D:\dev\strata-lab\redact-words.txt`（每行一个词，**这个文件不提交**，由 `plans/00` 生成）。
     里面有当前用户名、计算机名和本机安全软件的名字。安全软件的名字也不要写进任何提交的文件。
2. 检查每个待提交文件的大小不超过 200 KB。
3. 有命中或超限就不提交，先改掉再查一遍。
4. 在结论文件末尾写一行：「自查：按 lab/README.md 的关键字列表扫描，未发现命中」。
   **只能这样写**，不能写「保证没有敏感信息」。

## 结论文件的格式

`lab/results/NN-<名字>.md` 至少包括：

1. 执行环境：日期时间、引擎 checkout 的 HEAD、exe 的大小和修改时间、驱动版本、电源模式、是否刚重启。
2. 每个测量结果的表格，每个数字标出原始文件（`D:\dev\strata-lab\NN-...\` 下的相对路径）和行号。
3. 偏离手册的地方，以及原因。
4. 失败、卡住、崩溃的记录。
5. 推断要标「推断」，没做的事要写「未做」及原因。
6. 自查那一行。

## 共通规则

- 不改引擎代码，也不改 `local-v0.1.43.1-intel-npu` 上已跟踪的文件。只有手册明确写的才编译，而且只编译到新的 `build-lab-*` 目录。
- 服务只监听 `127.0.0.1`。只结束自己启动的进程。开始前 8080 被占用或已有 `strata.exe` 在运行，就停下来问用户。
- 环境变量要「关掉」时，从环境里删除，不要设成 `0`。很多开关只看变量是否存在。
- 要安装或下载东西（模型除外的任何东西），先问用户。
- 写下的每个数字都必须来自这次运行的输出，不估算，不沿用以前的数字。
- 运行 Python 前先 `set PYTHONUTF8=1`，用 `D:\dev\Strata-intel-npu\.venv\Scripts\python.exe`。
