# 10：MoE 和稠密 GEMV 内核拆分计时

执行时间：2026-10-17T08:05:28.150275+08:00（`environment.json:2`）。用户确认插电、电源模式最佳性能、实验期间不使用电脑。

- 引擎 `d35f55e49ea390f7121f1d1b4a21c682184e8183`（`environment.json:3`）。
- 引擎 exe：33721856 字节，修改时间 2026-10-17T04:30:43.466328+08:00，SHA256 `1a1e28c4b05b739da3b07f4710df283dc1053588bdd2f9bf0732c7a2396c4d03`（`environment.json:6`、`environment.json:7`、`environment.json:8`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)；驱动 `32.0.101.8826`（`environment.json:14`）。
- 电源模式：最佳性能；可用物理内存 59769090048 字节（`environment.json:13`、`environment.json:11`）。
- 开机时间：2026/10/16 16:15:08（`environment.json:12`）；本轮未发起重启。

构建命令、逐条耗时、退出码、工具大小及 SHA256 见 `10-kern-ablate/build.txt`，每项附原始来源。

## 核对

下面为 check.txt 原样内容：

```text
ka-1.tsv: rule 1 integrity=True; rule 2 same=True
ka-2.tsv: rule 1 integrity=True; rule 2 same=True
Cross-run checksum differences: 0 / 58 aligned keys
Maximum absolute relative us difference (run2/run1 - 1): +0.192930153322 (+19.293015%)
ka-1.tsv:22: q4k	Q4_K	base	1	234.8	37.4%	62.8	1	64e757263c1b5552
ka-2.tsv:22: q4k	Q4_K	base	1	280.1	20.6%	52.6	1	64e757263c1b5552
Per-key us relative differences (run2/run1 - 1):
part	type	variant	n	relative	sources
moe	IQ2_XXS	base	25	+0.068417957263	ka-1.tsv:15, ka-2.tsv:15
moe	IQ2_XXS	engine	25	-0.002442854650	ka-1.tsv:14, ka-2.tsv:14
moe	IQ2_XXS	noact	25	+0.011154011154	ka-1.tsv:18, ka-2.tsv:18
moe	IQ2_XXS	nogrid	25	+0.107125062282	ka-1.tsv:16, ka-2.tsv:16
moe	IQ2_XXS	nosign	25	+0.072472594397	ka-1.tsv:17, ka-2.tsv:17
moe	IQ2_XXS	now	25	+0.093672966311	ka-1.tsv:19, ka-2.tsv:19
moe	IQ2_XXS	slm	25	+0.038042269188	ka-1.tsv:20, ka-2.tsv:20
moe	IQ3_S	base	25	-0.026868437307	ka-1.tsv:8, ka-2.tsv:8
moe	IQ3_S	engine	25	+0.016413373860	ka-1.tsv:7, ka-2.tsv:7
moe	IQ3_S	noact	25	-0.007680320570	ka-1.tsv:11, ka-2.tsv:11
moe	IQ3_S	nogrid	25	+0.002681364517	ka-1.tsv:9, ka-2.tsv:9
moe	IQ3_S	nosign	25	+0.116038953420	ka-1.tsv:10, ka-2.tsv:10
moe	IQ3_S	now	25	+0.093941456773	ka-1.tsv:12, ka-2.tsv:12
moe	IQ3_S	slm	25	+0.116694124108	ka-1.tsv:13, ka-2.tsv:13
q4k	Q4_K	base	1	+0.192930153322	ka-1.tsv:22, ka-2.tsv:22
q4k	Q4_K	base	2	+0.073799025296	ka-1.tsv:27, ka-2.tsv:27
q4k	Q4_K	base	3	+0.147814207650	ka-1.tsv:32, ka-2.tsv:32
q4k	Q4_K	base	4	+0.033333333333	ka-1.tsv:37, ka-2.tsv:37
q4k	Q4_K	engine	1	+0.073984720547	ka-1.tsv:21, ka-2.tsv:21
q4k	Q4_K	engine	2	-0.056917688266	ka-1.tsv:26, ka-2.tsv:26
q4k	Q4_K	engine	3	-0.000222915738	ka-1.tsv:31, ka-2.tsv:31
q4k	Q4_K	engine	4	-0.074404185235	ka-1.tsv:36, ka-2.tsv:36
q4k	Q4_K	noact	1	-0.040837696335	ka-1.tsv:24, ka-2.tsv:24
q4k	Q4_K	noact	2	-0.066739209285	ka-1.tsv:29, ka-2.tsv:29
q4k	Q4_K	noact	3	+0.070245398773	ka-1.tsv:34, ka-2.tsv:34
q4k	Q4_K	noact	4	-0.082527705730	ka-1.tsv:39, ka-2.tsv:39
q4k	Q4_K	noones	1	+0.066572237960	ka-1.tsv:23, ka-2.tsv:23
q4k	Q4_K	noones	2	-0.004476040021	ka-1.tsv:28, ka-2.tsv:28
q4k	Q4_K	noones	3	+0.034240561896	ka-1.tsv:33, ka-2.tsv:33
q4k	Q4_K	noones	4	-0.047042052744	ka-1.tsv:38, ka-2.tsv:38
q4k	Q4_K	now	1	-0.018587360595	ka-1.tsv:25, ka-2.tsv:25
q4k	Q4_K	now	2	+0.143672692674	ka-1.tsv:30, ka-2.tsv:30
q4k	Q4_K	now	3	-0.068714376187	ka-1.tsv:35, ka-2.tsv:35
q4k	Q4_K	now	4	-0.066103379722	ka-1.tsv:40, ka-2.tsv:40
q6k	Q6_K	base	1	+0.005456634118	ka-1.tsv:42, ka-2.tsv:42
q6k	Q6_K	base	2	+0.054129464286	ka-1.tsv:48, ka-2.tsv:48
q6k	Q6_K	base	3	+0.053073315231	ka-1.tsv:54, ka-2.tsv:54
q6k	Q6_K	base	4	-0.004249608589	ka-1.tsv:60, ka-2.tsv:60
q6k	Q6_K	engine	1	-0.005800837899	ka-1.tsv:41, ka-2.tsv:41
q6k	Q6_K	engine	2	+0.038303693570	ka-1.tsv:47, ka-2.tsv:47
q6k	Q6_K	engine	3	+0.090772693173	ka-1.tsv:53, ka-2.tsv:53
q6k	Q6_K	engine	4	+0.009100529101	ka-1.tsv:59, ka-2.tsv:59
q6k	Q6_K	noact	1	-0.009780775717	ka-1.tsv:43, ka-2.tsv:43
q6k	Q6_K	noact	2	+0.022388059701	ka-1.tsv:49, ka-2.tsv:49
q6k	Q6_K	noact	3	+0.029601905410	ka-1.tsv:55, ka-2.tsv:55
q6k	Q6_K	noact	4	-0.024616368286	ka-1.tsv:61, ka-2.tsv:61
q6k	Q6_K	now	1	+0.112884834664	ka-1.tsv:44, ka-2.tsv:44
q6k	Q6_K	now	2	+0.019174898315	ka-1.tsv:50, ka-2.tsv:50
q6k	Q6_K	now	3	-0.003490401396	ka-1.tsv:56, ka-2.tsv:56
q6k	Q6_K	now	4	+0.012978257205	ka-1.tsv:62, ka-2.tsv:62
q6k	Q6_K	pf2	1	-0.024214322514	ka-1.tsv:45, ka-2.tsv:45
q6k	Q6_K	pf2	2	+0.051819438047	ka-1.tsv:51, ka-2.tsv:51
q6k	Q6_K	pf2	3	+0.091189427313	ka-1.tsv:57, ka-2.tsv:57
q6k	Q6_K	pf2	4	+0.024788732394	ka-1.tsv:63, ka-2.tsv:63
q6k	Q6_K	pf4	1	+0.001893361021	ka-1.tsv:46, ka-2.tsv:46
q6k	Q6_K	pf4	2	+0.042516588842	ka-1.tsv:52, ka-2.tsv:52
q6k	Q6_K	pf4	3	+0.107915379130	ka-1.tsv:58, ka-2.tsv:58
q6k	Q6_K	pf4	4	-0.005503890681	ka-1.tsv:64, ka-2.tsv:64
```

## 两次平均计时

单位 µs。单元格括号内为两个原始文件 `ka-1.tsv` / `ka-2.tsv` 的行号，按此顺序；缺失值记为“未测”。

| part | type | n | engine | base | nogrid | nosign | noact | now | slm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| moe | IQ3_S | 25 | 995.10 (7/7) | 958.35 (8/8) | 672.20 (9/9) | 901.75 (10/10) | 894.95 (11/11) | 615.20 (12/12) | 770.90 (13/13) |

| part | type | n | engine | base | nogrid | nosign | noact | now | slm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| moe | IQ2_XXS | 25 | 572.40 (14/14) | 527.55 (15/15) | 422.90 (16/16) | 510.45 (17/17) | 468.80 (18/18) | 382.20 (19/19) | 458.05 (20/20) |

| part | type | n | engine | base | noones | noact | now |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q4k | Q4_K | 1 | 257.90 (21/21) | 257.45 (22/22) | 218.85 (23/23) | 280.65 (24/24) | 133.25 (25/25) |
| q4k | Q4_K | 2 | 332.85 (26/26) | 446.80 (27/27) | 378.95 (28/28) | 266.50 (29/29) | 225.30 (30/30) |
| q4k | Q4_K | 3 | 448.55 (31/31) | 393.05 (32/32) | 347.55 (33/33) | 337.45 (34/34) | 304.95 (35/35) |
| q4k | Q4_K | 4 | 496.90 (36/36) | 472.75 (37/37) | 411.00 (38/38) | 406.60 (39/39) | 389.10 (40/40) |

| part | type | n | engine | base | noact | now | pf2 | pf4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q6k | Q6_K | 1 | 309.40 (41/41) | 349.15 (42/42) | 295.05 (43/43) | 92.65 (44/44) | 383.50 (45/45) | 1638.85 (46/46) |
| q6k | Q6_K | 2 | 372.50 (47/47) | 368.10 (48/48) | 298.10 (49/49) | 173.75 (50/50) | 445.45 (51/51) | 415.55 (52/52) |
| q6k | Q6_K | 3 | 418.05 (53/53) | 415.85 (54/54) | 298.25 (55/55) | 343.20 (56/56) | 474.70 (57/57) | 443.40 (58/58) |
| q6k | Q6_K | 4 | 474.65 (59/59) | 446.15 (60/60) | 308.95 (61/61) | 597.15 (62/62) | 539.10 (63/63) | 525.45 (64/64) |

## 执行记录、偏离和失败

- 只在新目录 build-lab-ka10 编译计划指定工具，未修改引擎或日常配置，未启动服务，未安装或下载依赖。
- 执行计划规定的环境清理、两次测量及超时限制；核对结果不通过时保留原始结果，不重跑。
- 未做其他模型、形状、硬件或后端验证。

没有构建失败、测量超时或崩溃；退出码见 build.txt、ka-exit.txt。
结束时引擎 HEAD、跟踪文件状态、引擎 exe 及配置均与开始时一致（final-check.json）。

原始构建日志、测量记录和执行脚本留在原始目录，未提交。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
