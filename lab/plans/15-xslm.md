# 15（最后一轮）：两个 hc 开关加进日常配置 + 稠密内核的激活放进共享内存（`STRATA_MMVQ_XSLM`）+ 共享专家不分叉（`STRATA_SH_STREAM=0`）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\15-xslm\`（下文叫「原始目录」）。
- 结论写到 `lab/results/15-xslm.md`；可公开的数据文件放在 `lab/results/15-xslm/`（下文叫「数据目录」）。

**前提**：`plans/14` 已经执行完，引擎在 `d7123fe1`，`build-sycl-win\strata.exe` 是 35,180,544 字节、SHA256 以 `2ee3648c` 开头；
日常配置 `strata-iq3_xxs.json` 的 `env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`、`STRATA_GU_GRID_SLM2`，
没有 `STRATA_GR_RED_BATCH`、`STRATA_GR_UP_TREE`、`STRATA_MMVQ_XSLM`、`STRATA_SH_STREAM`、`STRATA_VERIFY_ALL_RESIDENT`；
`args` 里有 `--expert-cache auto`、`--spec 4`、`--spec-min-p 0.5`、`--mtp …`，没有 `--suffix-draft`、`--batch`、`--slots`、`--lookup-chain`、`--batch-mtp`；
配置里没有 `"parallel"`（或者它不大于 1）。不是的话停下来报告。

**这是这组实验的最后一轮**（用户 2026-10-19 决定）。开发机的依据见 `lab/analysis/15-prep.md`：
- 第 3 节：用户已同意把 `STRATA_GR_RED_BATCH=1`、`STRATA_GR_UP_TREE=1` 加进日常配置（14 的判断），先做这件事，之后的测量都在新的日常配置上。
- 第 4 节：功能分支新提交 `76b68817` 加了默认关闭的 `STRATA_MMVQ_XSLM=4|8|16`。稠密的 Q6_K（开 SWAR 时）、Q4_K、Q5_K、IQ4_XS 多列内核
  先把窗口的激活整块读进共享内存，每列再从共享内存读（数字是每个工作组的行数）。开发机上实测逐位相同。在 140T 上按内核计时，`xslm_choice.py` 按规则选一个设置，或者不选。
- 第 5 节：端到端。`STRATA_SH_STREAM=0`（引擎已有的开关，共享专家不另开队列；Intel 上默认开，从没测过）作为 C 组顺带测。
  这一节**所有段都加 `--suffix-draft 0`**（只用于测量，日常配置不改它）：关掉提示词查找后，窗口大小只由草稿概率决定（⚠️ 推断：回答相同时窗口数也相同，这一轮第一次核对），1–2% 的差才可能分辨得出。
  `e2e15_check.py` 按事先定的规则判定加不加。
  B、C 是分开测的，判定最多选一个（两个都过时选快得多的那个）。
- 第 6 节：收尾的两段用日常的跑法（开着提示词查找、放得下就全部常驻）：`10-D0` 是第 3 节之后的日常配置，`11-D1` 再加第 5 节选出的开关。
  `11-D1` 跑完没有错误、回答和 `10-D0` 完全相同，第 7 节才把开关写进日常配置。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-xslm`；
第 3 节改一次 `strata-iq3_xxs.json`（先备份）；第 7 节在判定要写时再改一次（先备份）。`STRATA_SH_STREAM` 只认值（`0` 是关），C 组按 `"0"` 写进配置副本。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑；共享 GPU 内存上限仍是 75%。
4. 建原始目录（`mkdir D:\dev\strata-lab\15-xslm`；已存在时停下来问用户）。在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：
   日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、`git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `d7123fe1…`）、
   `git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、`build-sycl-win\strata.exe` 的大小、修改时间和 SHA256
   （预期 35,180,544 字节，SHA256 以 `2ee3648c` 开头）。不符就停下来报告。
5. **运行任何 exe 之前，先在同一个 CMD 里初始化 oneAPI**：
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   ```
   第 2、4、5、7 节的命令都在这个 CMD 里输入。

## 1. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-d7123fe1.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat d7123fe1 HEAD
   ```
   HEAD 应为 `76b68817…`；`diff --stat` 应只有 `sycl/src/kernels/cuda/native_mmvq.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-d7123fe1.exe` 复制回 `build-sycl-win\strata.exe`；第 2、4 节不做，第 3 节照做，
   第 5 节只跑 A、C 两组（按第 5 节「没有 B 组」的顺序），判定命令末尾加 `no-b`（见第 5 节）。

## 2. 工具编译（`build-lab-xslm` 已存在时，先停下来问用户，不要覆盖）
```
set "E=D:\dev\Strata-intel-npu"
set "B=D:\dev\Strata-intel-npu\build-lab-xslm"
set "L=D:\dev\Strata-lab140t\lab\tools"
mkdir %B%
set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
icx %CF% %CI% %L%\mmvq_lab.cpp /Fo%B%\mmvq_lab.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\iq_kernels.dp.cpp /Fo%B%\iq_kernels.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp /Fo%B%\native_mmvq.obj
set "L64=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
icx %L64% %B%\mmvq_lab.obj %B%\iq_kernels.obj %B%\native_mmvq.obj -o %B%\mmvq_lab.exe
```
链接选项和引擎相同（11 的 `a64`）。以每条命令退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。
失败就把报错原文写进结论，第 4 节不做；第 5 节只跑 A、C 两组（按「没有 B 组」的顺序），判定命令末尾加 `no-b`。

## 3. 日常配置加 `STRATA_GR_RED_BATCH=1`、`STRATA_GR_UP_TREE=1`（用户已同意，2026-10-19）
先把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-15.json`，不提交），再只在它的 `env` 里加
`"STRATA_GR_RED_BATCH": "1"`、`"STRATA_GR_UP_TREE": "1"`，其他不动；用 JSON 解析器读一遍；在 `config-change.json` 里记下改前改后的 `env`（只有键名和值）。

## 4. 内核对比（`strata.exe` 不运行时）
环境变量（这一节都用这一组：第 3 节之后日常配置里的 7 个内核开关；各次运行只差 `STRATA_MMVQ_XSLM`）：
```
set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
set STRATA_MMVQ_Q6_SWAR=1
set STRATA_Q2_SWAR=1
set STRATA_GR_UP_EPI=1
set STRATA_GR_DOWN_V2=1
set STRATA_GU_GRID_SLM2=2
set STRATA_GR_RED_BATCH=1
set STRATA_GR_UP_TREE=1
set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP="
cd /d D:\dev\strata-lab\15-xslm
set STRATA_ > env-strata.txt
type env-strata.txt
```
`env-strata.txt` 应该正好是这 7 行（`set STRATA_` 按名字排序列出）。多出来的变量逐个 `set "名字="` 删掉，再重做这一步，直到正好 7 行。

下面「base」是不设 `STRATA_MMVQ_XSLM`，「4」「8」「16」是 `set "STRATA_MMVQ_XSLM=4"` 等。每次运行写一个输出文件（约 33 MB，不提交）。
按下表顺序跑 12 次（3 轮，每轮 4 种设置，顺序轮换），逐行输入，不要改动：
```
type nul > mm-exit.txt
set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-1-base.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-1-base.tsv 2> mm-1-base.err
echo mm-1-base %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=4"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-1-4.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-1-4.tsv 2> mm-1-4.err
echo mm-1-4 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=8"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-1-8.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-1-8.tsv 2> mm-1-8.err
echo mm-1-8 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=16"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-1-16.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-1-16.tsv 2> mm-1-16.err
echo mm-1-16 %ERRORLEVEL% >> mm-exit.txt

set "STRATA_MMVQ_XSLM=4"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-2-4.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-2-4.tsv 2> mm-2-4.err
echo mm-2-4 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=8"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-2-8.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-2-8.tsv 2> mm-2-8.err
echo mm-2-8 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=16"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-2-16.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-2-16.tsv 2> mm-2-16.err
echo mm-2-16 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-2-base.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-2-base.tsv 2> mm-2-base.err
echo mm-2-base %ERRORLEVEL% >> mm-exit.txt

set "STRATA_MMVQ_XSLM=8"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-3-8.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-3-8.tsv 2> mm-3-8.err
echo mm-3-8 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=16"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-3-16.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-3-16.tsv 2> mm-3-16.err
echo mm-3-16 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-3-base.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-3-base.tsv 2> mm-3-base.err
echo mm-3-base %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=4"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm-3-4.bin"
%B%\mmvq_lab.exe 1024 300 all 6 > mm-3-4.tsv 2> mm-3-4.err
echo mm-3-4 %ERRORLEVEL% >> mm-exit.txt

set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm8-base.bin"
%B%\mmvq_lab.exe 256 50 all 8 > mm8-base.tsv 2> mm8-base.err
echo mm8-base %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=4"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm8-4.bin"
%B%\mmvq_lab.exe 256 50 all 8 > mm8-4.tsv 2> mm8-4.err
echo mm8-4 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=8"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm8-8.bin"
%B%\mmvq_lab.exe 256 50 all 8 > mm8-8.tsv 2> mm8-8.err
echo mm8-8 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM=16"
set "MMVQ_LAB_DUMP=D:\dev\strata-lab\15-xslm\mm8-16.bin"
%B%\mmvq_lab.exe 256 50 all 8 > mm8-16.tsv 2> mm8-16.err
echo mm8-16 %ERRORLEVEL% >> mm-exit.txt
set "STRATA_MMVQ_XSLM="
set "MMVQ_LAB_DUMP="
```
最后 4 次（`mm8-*`，1–8 列、时间短）只用来核对 7、8 列也逐位相同（读提示词时会用到），时间不进判定。
一次运行超过 15 分钟没结束就结束这个进程，在结论里写明，继续下一个。⚠️ 11 里每次约 72–84 秒，12 次约 16 分钟，`mm8-*` 4 次约 4 分钟。

判定（用 `D:\dev\Strata-intel-npu\.venv\Scripts\python.exe`，先 `set PYTHONUTF8=1`；照脚本的输出记，不要自己判断）：
```
%E%\.venv\Scripts\python.exe %L%\xslm_choice.py D:\dev\strata-lab\15-xslm 140T
```
脚本写出原始目录的 `xslm-choice.txt` 并打印前几行（脚本出错也会写出 `problems` 不为 0 的文件）。它做的事：
- **问题**（任何一条都使 `choice: none`）：`mm-exit.txt` 正好 16 行、名字不重复、全部是 0；16 个 `.err` 都是空的；`env-strata.txt` 正好是上面 7 行；
  每个 `.tsv` 表头前的行正确（设备含 `140T`、工作集和时间、`env STRATA_MMVQ_Q6_SWAR=1`，非 base 还有 `env STRATA_MMVQ_XSLM=<设置>`），
  26 种情形 × 1–6 列（`mm8-*` 是 1–8 列）各一行、数字有限，16 次的驱动一致；
  **12 个计时的输出文件字节完全相同、4 个 `mm8-*` 的输出文件字节也完全相同，各次的校验和相同**（逐位相同）。
- **时间**：每次运行按本模型每种（形状、类型）的张量个数加权，得到各列数的稠密时间 D1–D6；W = 0.12·D1 + 0.14·D2 + 0.12·D3 + 0.62·D4（权重同 14）。
- **选择**：没有问题、W 中位数最小的那个设置，W 低于 0.95 × W(base)、3 轮每一轮都低于同一轮的 base、
  而且 5 列和 6 列（提示词查找的窗口最长 6）的 D 中位数都不超过 base 的 1.03 倍，为 `choice: <设置>`；否则 `choice: none`。

## 5. 端到端分段（交替）
驱动脚本以 14 用过的为底子（`sycl\serve\server_intel.py`、固定测速提示词、启动日志和请求边界的核对），复制到原始目录再改，改了什么写进结论。和 14 不同的地方：
1. `s.nonce = "fixed15"`。
2. **测速请求的回答要记哈希**：驱动在 `import strata_bench` 之后把 `strata_bench.chat` 换成一个包装：调原函数，把返回值 `text` 的 UTF-8 字节的 SHA256 前 16 位
   和 `usage.completion_tokens` 记下来，再原样返回。`s.warm_up()` 之后清空记录，`s.run_chat()` 之后正好应有 9 条（按请求顺序）。写进 `bench-text.tsv`（见第 8 节）。
3. `decode-requests.tsv` 多一列 `verify`：取对应的 `strata decode timing` 行里 `verify` 后面的数（每窗口毫秒）。
4. 每段的 `startup.tsv` 照 14 记（`expert cache … slots`、`missing from VRAM`、`strata verify: window up to`）；
   `strata verify: window up to` 那一行应是 `window up to 4 tokens`（关掉提示词查找后不再加 2），而且**不能**带 `(100% VRAM resident: zero-doorbell graph)`。
   不是的话停下来报告。
5. 不发 logprobs 请求。

**每段用的配置副本**：把第 3 节改好的 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，原文件这一节不动：
- `cfg-a.json`：`env` 里加 `"STRATA_VERIFY_ALL_RESIDENT": "0"`（两组走同一条路径，理由同 13）；`args` 的末尾加 `"--suffix-draft", "0"`。
- `cfg-b.json`：同 `cfg-a.json`，`env` 里再加 `"STRATA_MMVQ_XSLM": "<第 4 节选出的设置>"`（只在第 4 节 `choice` 不是 `none` 时做）。
- `cfg-c.json`：同 `cfg-a.json`，`env` 里再加 `"STRATA_SH_STREAM": "0"`。

配置的 `env` 会覆盖进程的环境变量（`serve/server.py:2631-2632`），所以开关只写在配置副本里。

| 第 4 节 | 段（按顺序） |
|---|---|
| 选出了设置 | `1-A`、`2-B`、`3-C`、`4-C`、`5-B`、`6-A`、`7-A`、`8-B`、`9-C` |
| `choice: none`（没有 B 组） | `1-A`、`2-C`、`3-C`、`4-A`、`5-A`、`6-C` |

- **任何一段都不要设 `STRATA_VERIFY_DEBUG`**。

每段（同 14）：
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除第 4 节列出的全部 `STRATA_` 变量，然后设 `STRATA_DECODE_TIMING=1`。
2. 记下引擎日志长度；按配置副本启动服务，等就绪；`s.nonce = "fixed15"`；`s.warm_up()`。
3. **贪心请求**（同 `plans/06` 第 3.1 节：`g1`、`g2`），再 `s.run_chat()`（9 个请求，不跑 4K）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进 `errors.tsv`
（列 `segment`、`line`、`text`；一条都没有时只写表头）。

做完以后（先把第 4 节的 `xslm-choice.txt` 留在原始目录，表格都写到原始目录）：
```
set PYTHONUTF8=1
D:\dev\Strata-intel-npu\.venv\Scripts\python.exe D:\dev\Strata-lab140t\lab\tools\e2e15_check.py D:\dev\strata-lab\15-xslm
```
（第 4 节没做时命令末尾加 ` no-b`：不读 `xslm-choice.txt`，按没有 B 组的 6 段判定。）照脚本的输出记，不要自己判断；退出码不是 0 时 `add` 一定是 `none`。
脚本写出 `e2e-choice.txt`，第一行 `problems: N`，第二行 `add: …`。它做的事：
- **问题**（任何一条都使 `add: none`）：各表的列齐全、段名只有本节的段和第 6 节的 `10-D0`、`11-D1`；每段 9 个测速请求各一行、不重复，
  token 数是正整数且 `timing.tsv` 和 `bench-text.tsv` 一致，毫秒、窗口数、平均 T、每窗口 token 数、verify 都是正的有限数，草稿毫秒不是负数；
  每段 `g1`、`g2` 哈希各一个；`window up to 4 tokens`、没有 `100% VRAM resident`；`errors.tsv` 里这些段没有行；
  **所有段的 `g1` 哈希相同、`g2` 哈希相同，9 个测速请求各自的回答哈希和 token 数在所有段之间相同**。
- **记录**：每段的 ms/token（9 个请求的生成总毫秒 ÷ 生成总 token）、每窗口 verify 和草稿毫秒、每窗口 token 数、各请求的窗口数，以及各请求的窗口数和平均 T 是否在所有段之间相同。
- **规则**（事先定的）：组的均值 = 该组 3 段 ms/token 的平均；组的波动 = 3 段的（最大 − 最小）÷ 均值。
  B（或 C）的均值比 A 的小，而且差的比例大于 A 和 B（或 C）两组波动中较大的那个，为「分辨得出、更快」。
  B、C 是分开测的，没测过两个一起开，所以 `add` **最多列一个**：只有一个分辨得出就列它，两个都分辨得出就列快得多的那个。

## 6. 收尾的两段：日常的跑法（`10-D0`、`11-D1`）
这两段用日常的跑法：**不加** `--suffix-draft 0`、**不加** `STRATA_VERIFY_ALL_RESIDENT`（放得下就走全部常驻的路径）。
- `cfg-d0.json`：第 3 节之后的 `strata-iq3_xxs.json` 原样复制，什么都不加。
- `cfg-d1.json`：同 `cfg-d0.json`，`env` 里再加 `e2e-choice.txt` 的 `add` 列出的开关（`STRATA_MMVQ_XSLM` 写成 `"STRATA_MMVQ_XSLM": "<设置>"`，
  `STRATA_SH_STREAM` 写成 `"STRATA_SH_STREAM": "0"`）。`add: none` 时不做 `11-D1`。

按第 5 节「每段」的步骤先跑 `10-D0`，再跑 `11-D1`；表格追加到第 5 节的同一组文件里（段名 `10-D0`、`11-D1`）；
`startup.tsv` 照记（这两段是 `window up to 6 tokens`，带不带 `100% VRAM resident` 都照记）。然后：
```
D:\dev\Strata-intel-npu\.venv\Scripts\python.exe D:\dev\Strata-lab140t\lab\tools\e2e15_check.py D:\dev\strata-lab\15-xslm final
```
照脚本的输出记。脚本写出 `final-check.txt`，第一行 `problems: N`，第二行 `write: …`：
- `e2e-choice.txt` 的 `add` 是一个开关，两段都是 `window up to 6 tokens`，`11-D1` 的 9 个测速请求齐全、数字合规、`errors.tsv` 里这两段没有行，
  而且 `11-D1` 的 `g1`、`g2` 哈希和 9 个测速回答的哈希、token 数都和 `10-D0` 相同时，为 `write: <开关>`；否则 `write: none`。
- 另外记下两段各自的 ms/token、窗口数、是否全部常驻、`g1`/`g2` 哈希是 12 的全部常驻路径（`559a75356eb39f09`、`a6c46dc05f536ef5`）、
  13/14 A 组的 device plan 路径（`553ac32f017ae0be`、`1c1c19249884638f`），还是都不是。单段的 ms/token 只记录，不作判定。

## 7. 日常配置（按 `final-check.txt` 的 `write` 那一行）
- `write: none`：不改，结论里写明（`add` 不是 `none` 而 `write` 是 `none` 时，写明是哪一条没满足）。
- 否则：先把 `strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-15b.json`，不提交），再只在它的 `env` 里加那个开关，写法同第 6 节，其他不动
  （不加 `STRATA_VERIFY_ALL_RESIDENT`，不加 `--suffix-draft`）；用 JSON 解析器读一遍；在 `config-change.json` 里再记下这次改前改后的 `env`。

## 8. 放进数据目录的内容（提交前逐个打开确认：只有数字、设备和驱动信息、开关名、核对结论、哈希，以及路径换成占位符的编译命令）
1. 12 个 `mm-*.tsv`、4 个 `mm8-*.tsv`、`mm-exit.txt`、`env-strata.txt`、`xslm-choice.txt`。`.err` 都是空的话不提交，非空的去掉路径后附上。`.bin` 不提交。
2. `timing.tsv`、`decode.tsv`、`decode-requests.tsv`（多 `verify` 列）、`greedy.tsv`、`greedy-check.txt`、`startup.tsv`、`errors.tsv`、`e2e-choice.txt`、`final-check.txt`，
   以及新的 `bench-text.tsv`（列 `segment`、`request`、`sha256_16`、`generated_tokens`，每段 9 行），格式同 `results/14-hc-up/`；都包括 `10-D0`（和 `11-D1`）。
   提交前在数据目录里重跑一次两条判定命令（`e2e15_check.py <数据目录>`、`e2e15_check.py <数据目录> final`；第 4 节没做时第一条照第 5 节末尾加 ` no-b`），
   输出应和原始目录的一样；不一样就写进结论。
3. `build.txt`、`config-change.json`（第 3 节的改动，第 7 节改了的话也记在里面）。

## 9. 结论 `lab/results/15-xslm.md`
按 README 的「结论文件的格式」写。额外包括：
1. `xslm-choice.txt` 的前 15 行、`e2e-choice.txt` 和 `final-check.txt` 原样贴出。
2. 每组合并的 ms/token、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、草稿接受数之和 / 提供数之和；每段常驻的专家数和 `missing from VRAM` 的个数。
3. 第 3、7 节改了什么（`config-change.json` 的摘要）。
4. 第 5、6 节要求记录的错误行（没有就写「没有」）。
5. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/15-xslm.md` 和 `lab/results/15-xslm/`，推送。

预计耗时：⚠️ 约 1 小时 55 分钟（重编引擎约 6 分钟（14 是 347 秒）；工具编译约 5 分钟；第 4 节约 20 分钟；第 5 节 9 段每段约 5–6 分钟；第 6 节两段约 12 分钟）。
