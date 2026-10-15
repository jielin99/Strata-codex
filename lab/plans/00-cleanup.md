# 00：建立 worktree、清理测试残留、和 GitHub 对比

先读 `lab/README.md`，遵守里面的共通规则、提交范围和推送步骤。全部用 CMD。
原始记录写到 `D:\dev\strata-lab\00-cleanup\`；结论写到 `lab/results/00-cleanup.md`，再提交推送。

## 1. worktree
按 `lab/README.md` 的「笔记本的准备」做一次。之后的提交都在 `D:\dev\Strata-lab140t` 里做。

## 1.5 本机关键字清单（不提交）
生成 `D:\dev\strata-lab\redact-words.txt`，每行一个词，提交前自查要用它（见 README）：
- `echo %USERNAME%` 和 `echo %COMPUTERNAME%` 的输出。
- 本机安全软件的产品名：PowerShell `Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | Select -Expand displayName`。
  另外把 `tasklist` 里明显属于安全或 VPN 客户端的进程名（不含 `.exe`）也加进去。
- 这个文件**只放在 strata-lab 下，不复制到 worktree，不提交**；结论里也不写它的内容，只写「已生成，共 N 行」。

## 2. 开始前记录
- `git -C D:\dev\Strata-intel-npu status --short`，以及 `git -C D:\dev\Strata-intel-npu status --short --ignored`（`build-sycl-win\`、`.venv\` 这类目录只写目录名）。
- C: 和 D: 的剩余空间。
- 如果有 `strata.exe` 在运行，停下来问用户。

## 3. 删除
路径必须**逐字一致**才删。`D:\dev\Strata-intel-npu\build-sycl-win\`（没有后缀）是正在用的 Release 版，**绝对不能动**。
每个对象删除前，先记录大小和文件数。

| 对象 | 说明 | 删除前要确认 |
|---|---|---|
| `D:\dev\Strata-intel-npu\build-sycl-win-dbg\` | 第 2 轮 /Zi 编译用的目录，链接失败，没有用了 | 只记录大小 |
| `D:\dev\Strata-intel-npu\build-sycl-wmp\` | 第 3 轮 MAP 编译用的目录 | `D:\dev\strata-lab\map-20261015-0933\new\strata.map` 和 `new\strata.exe` 都存在 |
| 仓库根目录的 `CODEX-RUNBOOK-140T*.md`（有几个删几个）、`pecmp.py` | 以前手工传过来的手册和脚本 | `git -C D:\dev\Strata-intel-npu ls-files` 里没有它们 |
| 仓库根目录的 `strata-stall-*.dmp`，共 6 个：23248、23976、24720、26528、744、9436 | 备份在 `D:\dev\strata-lab\map-20261015-0933\dmp-old\` | 逐个比 SHA256，**全部相同**才删；有任何一个不同或缺失，就一个都不删，并写进结论 |

## 4. 移动（不删除）
仓库根目录下的 `bench\results\2026-10-14-community-cpu-qwen3-8-flash-next-iq3-xxs\`、`...-2\`、`...-3\` 三个未跟踪目录：
- 先确认 `git -C D:\dev\Strata-intel-npu ls-files bench/results/2026-10-14-*` 为空。
- 列出每个目录里的文件名和大小（记到原始记录里）。
- 再整体移到 `D:\dev\strata-lab\bench-results-20261014\`。

## 5. 和 GitHub 对比（只看不改，不 pull）
```
git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
git -C D:\dev\Strata-intel-npu branch -vv
git -C D:\dev\Strata-intel-npu rev-parse HEAD FETCH_HEAD
git -C D:\dev\Strata-intel-npu log --oneline FETCH_HEAD..HEAD
git -C D:\dev\Strata-intel-npu log --oneline HEAD..FETCH_HEAD
git -C D:\dev\Strata-intel-npu diff --stat
git -C D:\dev\Strata-intel-npu diff --cached --stat
git -C D:\dev\Strata-intel-npu stash list
git -C D:\dev\Strata-intel-npu status --short
```

## 6. 结论 `lab/results/00-cleanup.md`
按 `lab/README.md` 的「结论文件的格式」写，内容包括：
- 每个对象的处理结果：删除、移动或未处理，以及大小、文件数、SHA256 比对是否一致。
  dmp 的哈希值不用写进结论，只写「6 个全部一致」或者哪个不一致。
- 清理前后 C: 和 D: 的剩余空间。
- 第 5 节每条命令的输出原文。如果输出里有带用户名的路径，换成 `<path>`。
- 清理后仓库根目录还剩哪些未跟踪的和被忽略的项，只列出来，不处理。

然后按 README 做提交前自查，并推送。**这也是第一次验证笔记本能不能推送**：推送失败就把报错原文告诉用户，然后停下。
