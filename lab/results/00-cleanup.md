# 00：worktree、清理检查和 GitHub 对比

执行时间：2026-10-15T17:15:39.069491+08:00（`evidence.txt:1`）；结束记录时间：2026-10-15T17:16:26.372884+08:00（`evidence.txt:8`）。原始记录均位于 `D:\dev\strata-lab\00-cleanup\`，下文行号相对于该目录。

## 执行环境

| 项目 | 本次结果 | 原始记录 |
|---|---|---|
| 引擎 HEAD | `29825274e3de26b35101d73be2d793315453a6ac` | `evidence.txt:3` |
| Release 程序 | 32693760 字节；修改时间 2026-10-14T14:56:46.468059+08:00 | `evidence.txt:4` |
| 显卡与驱动 | Intel Arc 140T；32.0.101.8826 | `evidence.txt:5` |
| 电源模式 | 平衡 | `evidence.txt:6` |
| 最近启动 | 2026-10-15T02:32:36.500000+08:00；本轮未重启 | `evidence.txt:7` |
| 本机关键字清单 | 已生成，共 20 行 | `evidence.txt:2` |
| 安全检查 | 未发现正在运行的引擎进程或监听中的目标端口 | `evidence.txt:23` |

主目录保持在 `local-v0.1.43.1-intel-npu`；实验 worktree 为 `D:\dev\Strata-lab140t`，分支为 `lab/140t`。没有安装、编译、启动服务或结束进程。

## 对象处理

| 对象 | 文件数 | 字节数 | 结果 | 原始记录 |
|---|---:|---:|---|---|
| `build-sycl-win-dbg` | 0 | 0 | 未处理：不存在 | `evidence.txt:11` |
| `build-sycl-wmp` | 0 | 0 | 未处理：不存在 | `evidence.txt:12` |
| `pecmp.py` | 0 | 0 | 未处理：不存在 | `evidence.txt:13` |
| `bench/results/2026-10-14-community-cpu-qwen3-8-flash-next-iq3-xxs` | 0 | 0 | 未处理：不存在 | `evidence.txt:14` |
| `bench/results/2026-10-14-community-cpu-qwen3-8-flash-next-iq3-xxs-2` | 0 | 0 | 未处理：不存在 | `evidence.txt:15` |
| `bench/results/2026-10-14-community-cpu-qwen3-8-flash-next-iq3-xxs-3` | 0 | 0 | 未处理：不存在 | `evidence.txt:16` |
| 根目录手册匹配项 | 0 | 不适用 | 不存在，未删除 | `evidence.txt:17` |
| 转储源文件匹配项 | 0 | 不适用 | 不存在，未删除 | `evidence.txt:19` |

转储进程编号 23248、23976、24720、26528、744、9436 对应的源文件全部不存在（`evidence.txt:18`）。SHA256 比对未做：源文件缺失，无法判断备份是否与源文件相同，不能写成全部一致。未删除任何备份。
`build-sycl-wmp` 所需 MAP 与程序备份均存在（`evidence.txt:21`），但待删目录不存在。基准结果路径的跟踪检查为空（`evidence.txt:20`）；源目录均不存在，因此没有移动，也没有覆盖目的目录已有内容。
`build-sycl-win` 未作处理；程序大小与修改时间复核相同（`evidence.txt:4`、`evidence.txt:22`）。清理前状态见 `status-before.json`，逐文件清单见 `inventory-before.json`、`move-inventory.json`；本次未发现可删除或可移动的目标，未宣称释放空间。

## 磁盘剩余空间

| 卷 | 清理前（字节） | 清理后（字节） | 原始记录 |
|---|---:|---:|---|
| C: | 231061491712 | 231060676608 | `evidence.txt:9` |
| D: | 242239934464 | 242239922176 | `evidence.txt:10` |

空间差值包含系统和其他进程的同期活动，不能归因于本轮清理。

## 和 GitHub 对比

以下按计划顺序保留命令输出；空输出的代码块留空。远端地址与输出中命中本机关键字的远端标识替换为 `<remote>`。原文留在 `github-compare.json`，仅本地保存。

命令（`github-compare.json:3`）：
```cmd
git -C D:\dev\Strata-intel-npu fetch <remote> local-v0.1.43.1-intel-npu
```
输出：
```text
From <remote>
 * branch              local-v0.1.43.1-intel-npu -> FETCH_HEAD
```

命令（`github-compare.json:8`）：
```cmd
git -C D:\dev\Strata-intel-npu branch -vv
```
输出：
```text
+ lab/140t                  cc9e57b4 (D:/dev/Strata-lab140t) lab: start the lab/140t log for the Arc 140T laptop
* local-v0.1.43.1-intel-npu 29825274 [origin/local-v0.1.43.1-intel-npu] docs: longer contexts on the Arc 140T laptop; 48K k8v4 is the working one
```

命令（`github-compare.json:13`）：
```cmd
git -C D:\dev\Strata-intel-npu rev-parse HEAD FETCH_HEAD
```
输出：
```text
29825274e3de26b35101d73be2d793315453a6ac
29825274e3de26b35101d73be2d793315453a6ac
```

命令（`github-compare.json:18`）：
```cmd
git -C D:\dev\Strata-intel-npu log --oneline FETCH_HEAD..HEAD
```
输出：
```text

```

命令（`github-compare.json:23`）：
```cmd
git -C D:\dev\Strata-intel-npu log --oneline HEAD..FETCH_HEAD
```
输出：
```text

```

命令（`github-compare.json:28`）：
```cmd
git -C D:\dev\Strata-intel-npu diff --stat
```
输出：
```text

```

命令（`github-compare.json:33`）：
```cmd
git -C D:\dev\Strata-intel-npu diff --cached --stat
```
输出：
```text

```

命令（`github-compare.json:38`）：
```cmd
git -C D:\dev\Strata-intel-npu stash list
```
输出：
```text

```

命令（`github-compare.json:43`）：
```cmd
git -C D:\dev\Strata-intel-npu status --short
```
输出：
```text

```

本地引擎 HEAD 与远端相同；双向新增提交、工作区差异、暂存区差异、stash 以及普通状态的输出均为空。没有 pull、合并或改动引擎文件。

## 清理后保留的未跟踪与忽略项

普通未跟踪项为空；忽略项如下（`evidence.txt:24`）。目录只列目录名，不展开，不处理。
```text
!! .venv/
!! __pycache__/
!! build-sycl-win/
!! build-win.log
!! build-win2.log
!! run-iq3_xxs.bat
!! serve/__pycache__/
!! strata-iq3_xxs-A0.log
!! strata-iq3_xxs-B.log
!! strata-iq3_xxs.json
!! strata-iq3_xxs.log
!! sycl/serve/__pycache__/
!! third_party/llama.cpp/
!! tools/__pycache__/
!! tools/intel_npu/reports/
```

## 偏离、失败和未做

读取手册前曾将主目录临时切换到实验分支；读完后立即恢复功能分支，再按手册建立独立 worktree，未改动引擎文件。最初用 PowerShell 读取时中文显示乱码，之后改由 CMD 设置 Python UTF-8 后完整重读；后续执行入口均使用 CMD，系统查询按手册调用 PowerShell。
沙箱内首次 fetch 因 Git 元数据写权限不足失败，授权重试成功；首次进程查询权限不足，授权后重新查询成功。沙箱读取新 worktree 时遇到 Git 所有权保护，后续使用授权环境运行 Git，未修改全局信任配置。没有崩溃或持续卡住。
待清理目标均缺失，按现状记录，未从历史清理记录补填数据。转储哈希校验未做，原因见上。手册没有要求运行性能测试或构建，本轮未做。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
