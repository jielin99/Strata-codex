#!/usr/bin/env python3
"""hcup_choice: the checks and the choice of lab/plans/14-hc-up.md over one directory of runs.

  python hcup_choice.py <dir> <device substring>

<dir> holds:
  gev-<r>-<c>.txt  gr_events_bench 300 for rounds r = 1..3 and settings c = base, rb (STRATA_GR_RED_BATCH=1),
                   tree (STRATA_GR_UP_TREE=1), both; gev-<r>-<c>.err its stderr
  gap-base.txt, gap-rb.txt, gap-tree.txt   gr_apply_parity under base, rb and both (both: bitwise base, recorded)
  gb-base.txt, gb-rb.txt, gb-both.txt      gr_bench under base, rb and both
  gq-both.txt      gr_q8_parity under both
  ev-exit.txt      exactly one line "<name> <exit code>" per run (NAMES below)
  env-strata.txt   the output of `set STRATA_` before the runs (the daily hc switches only)
Writes hcup-choice.txt (problems, the choice, the medians) into <dir>. Every failed check is a problem: the first line
is `problems: <count>`, the exit code is 1 if any, and with a problem nothing is chosen. Only counts, compares and
applies the plan's rule.
"""
import math
import os
import re
import statistics
import sys

SETS = {"base": [], "rb": ["STRATA_GR_RED_BATCH=1"], "tree": ["STRATA_GR_UP_TREE=1"],
        "both": ["STRATA_GR_RED_BATCH=1", "STRATA_GR_UP_TREE=1"]}
ORDER = [(1, "base"), (1, "rb"), (1, "tree"), (1, "both"),
         (2, "rb"), (2, "tree"), (2, "both"), (2, "base"),
         (3, "tree"), (3, "both"), (3, "base"), (3, "rb")]
NAMES = (["gap-base", "gap-rb", "gap-tree", "gb-base", "gb-rb", "gb-both", "gq-both"] +
         [f"gev-{r}-{c}" for r, c in ORDER])
ENV_WANT = ["STRATA_GR_DOWN_V2=1", "STRATA_GR_UP_EPI=1"]
DAILY = ["env STRATA_GR_UP_EPI=1", "env STRATA_GR_DOWN_V2=1"]
HEADER = "T\tspan_us\tkernels\tk0_us\tk1_us\tk2_us\tk3_us\tk4_us\tgaps_us\tbad"
MAX_BAD = 30   # of 300 iterations: more left out than this is a problem
KERNELS = ["norm", "down", "reduce", "up"]
# gr_bench's BF16 checksums at 1-6 tokens (rounds 11-13 on the 140T, and the dev machine): the default read
BF16_CS = ["156044a29131637f", "ada635710c63920a", "ac6937afab84574b", "3441f4d29598c269", "94c690071d72f1bc",
           "0cce58250c149197"]
GB_LINE = re.compile(r"fused GR read, (\d) tokens: +(\S+) us \(\d+ GB/s of weights\)  checksum ([0-9a-f]{16})  sum (\S+)")
GAP_LINE = re.compile(r"apply ([01]) inject ([01]) T ([1-8])  outputs [0-9a-f]{16}  R [0-9a-f]{16}")
GAP_KEYS = {(a, i, t) for a in "01" for i in "01" for t in "12345678"}          # gr_apply_parity's 32 cases
GQ_LINE = re.compile(r"(same|ref ) (plain|apply) inj=(bf16|q8|none) T=([1-8]): mixed (\S+) inject (\S+) rs (\S+) "
                     r"lo (\S+) R (\S+) ok")
GQ_KEYS = {(c, a, j, t) for c in ("same", "ref ") for a in ("plain", "apply") for j in ("bf16", "q8", "none")
           for t in "12345678"}                                                    # gr_q8_parity's 96 cases
GQ_BOUND = 1e-4                                                                    # gr_q8_parity's kBound
WEIGHTS = [0.12, 0.14, 0.12, 0.62]   # generation windows by T (analysis/03-window-t.md), T 1-4
BAR = 0.90


def finite_pos(s):
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) and v > 0 else None


def read_lines(path, bad):
    if not os.path.exists(path):
        bad.append(f"{os.path.basename(path)}: missing")
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return [ln.rstrip("\r") for ln in f.read().split("\n") if ln.rstrip("\r") != ""]


def parse_gev(path, c, device, bad):
    """{T: (span, [norm, down, reduce, up])} for T 1..6."""
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    want = [r"device: .*"] + [re.escape(x) for x in DAILY + [f"env {e}" for e in SETS[c]]] + [re.escape(HEADER)]
    head = lines[:len(want)]
    if len(head) != len(want) or not all(re.fullmatch(p, ln) for p, ln in zip(want, head)):
        bad.append(f"{name}: lines before the data {head}, want {want}")
    if not head or device not in head[0]:
        bad.append(f"{name}: device line {head[0] if head else ''!r} lacks {device!r}")
    rows = {}
    data = lines[len(want):]
    if len(data) != 6:
        bad.append(f"{name}: {len(data)} data lines, want 6")
    for i, ln in enumerate(data):
        p = ln.split("\t")
        vals = [finite_pos(x) for x in p[1:2] + p[3:7]]
        gap = nbad = None
        try:
            gap = float(p[8]) if len(p) == 10 else None
            nbad = int(p[9]) if len(p) == 10 else None
        except ValueError:
            pass
        if (len(p) != 10 or p[0] != str(i + 1) or p[2] != "4" or p[7] != "-" or any(v is None for v in vals)
                or gap is None or not math.isfinite(gap) or nbad is None or not 0 <= nbad <= MAX_BAD):
            bad.append(f"{name}: bad line {ln!r}")
            continue
        rows[i + 1] = (vals[0], vals[1:])
    return rows


def parse_gb(path, bad):
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    cs = {}
    for i, ln in enumerate(lines):
        m = GB_LINE.fullmatch(ln)
        try:
            sum_ok = m is not None and math.isfinite(float(m.group(4)))
        except ValueError:
            sum_ok = False
        if not m or int(m.group(1)) != i + 1 or finite_pos(m.group(2)) is None or not sum_ok:
            bad.append(f"{name}: bad line {ln!r}")
            continue
        cs[i + 1] = m.group(3)
    if len(lines) != 6 or sorted(cs) != [1, 2, 3, 4, 5, 6]:
        bad.append(f"{name}: {len(lines)} lines, want 6 for T 1-6")
    return cs


def main():
    d, device = sys.argv[1], sys.argv[2]
    out, bad = [], []
    seen = {}
    for ln in read_lines(os.path.join(d, "ev-exit.txt"), bad):
        p = ln.split()
        if len(p) != 2 or p[0] not in NAMES:
            bad.append(f"ev-exit.txt: unexpected line {ln!r}")
        elif p[0] in seen:
            bad.append(f"ev-exit.txt: repeated entry {ln!r}")
        else:
            seen[p[0]] = p[1]
    for n in NAMES:
        if seen.get(n) != "0":
            bad.append(f"ev-exit.txt: {n} -> {seen.get(n)}")
    for r, c in ORDER:
        e = os.path.join(d, f"gev-{r}-{c}.err")
        if not os.path.exists(e) or os.path.getsize(e) != 0:
            bad.append(f"gev-{r}-{c}.err: missing or not empty")
    env = read_lines(os.path.join(d, "env-strata.txt"), bad)
    if env != ENV_WANT:
        bad.append(f"env-strata.txt: {env}, want exactly {ENV_WANT}")

    # bitwise: base and rb the same in every gr_apply_parity case (a problem if not); base and both (gap-tree) recorded
    gap = {c: read_lines(os.path.join(d, f"gap-{c}.txt"), bad) for c in ("base", "rb", "tree")}
    for c, lines in gap.items():
        keys = [GAP_LINE.fullmatch(ln) for ln in lines[1:]]
        if len(lines) != 33 or not lines[0].startswith("device: ") or device not in lines[0] or not all(keys) or \
                {k.groups() for k in keys if k} != GAP_KEYS:
            bad.append(f"gap-{c}.txt: want a {device} device line and the 32 cases (apply, inject, T) once each")
    if gap["base"] != gap["rb"]:
        bad.append("gap-rb.txt differs from gap-base.txt (STRATA_GR_RED_BATCH=1 should be bitwise)")
    tree_diff = sum(1 for a, b in zip(gap["base"][1:], gap["tree"][1:]) if a != b)
    gb = {c: parse_gb(os.path.join(d, f"gb-{c}.txt"), bad) for c in ("base", "rb", "both")}
    for c in ("base", "rb"):
        diff = [t for t, v in gb[c].items() if v != BF16_CS[t - 1]]
        if diff:
            bad.append(f"gb-{c}.txt: checksums differ from the default read's at T {diff}")
    both_diff = [t for t, v in gb["both"].items() if v != BF16_CS[t - 1]]
    par = read_lines(os.path.join(d, "gq-both.txt"), bad)
    gq = [GQ_LINE.fullmatch(ln) for ln in par[:-1]]
    gq_ok = all(gq) and len(gq) == 96 and {(m[1], m[2], m[3], m[4]) for m in gq} == GQ_KEYS
    for m in gq:
        if m:
            for x in m.groups()[4:]:
                try:
                    v = float(x)
                except ValueError:
                    v = math.nan
                gq_ok = gq_ok and math.isfinite(v) and 0 <= v <= GQ_BOUND
    if not par or par[-1] != "gr_q8_parity: 0 failures" or not gq_ok:
        bad.append(f"gq-both.txt: want the 96 cases once each, every error finite and <= {GQ_BOUND}, and"
                   f" 'gr_q8_parity: 0 failures' (last line {par[-1] if par else ''!r})")
    bitwise_both = tree_diff == 0 and not both_diff and len(gap["tree"]) == 33 and len(gb["both"]) == 6
    out.append(f"bitwise: gr_apply_parity base = rb {gap['base'] == gap['rb']}; base = both {tree_diff == 0}"
               f" ({tree_diff} of 32 cases differ); gr_bench base and rb = the default read's checksums; both differs at"
               f" T {both_diff}")
    out.append(f"bitwise both: {bitwise_both}")

    data = {(r, c): parse_gev(os.path.join(d, f"gev-{r}-{c}.txt"), c, device, bad) for r, c in ORDER}
    med = {}
    for c in SETS:
        for t in range(1, 7):
            rows = [data[(r, c)][t] for r in (1, 2, 3) if t in data[(r, c)]]
            if len(rows) == 3:
                med[(c, t)] = (statistics.median(x[0] for x in rows),
                               [statistics.median(x[1][k] for x in rows) for k in range(4)])
    out.append("")
    out.append("median us (3 rounds): span / norm down reduce up, T = 1..6")
    for c in SETS:
        for t in range(1, 7):
            if (c, t) in med:
                s, k = med[(c, t)]
                out.append(f"  {c:4s} T{t}: {s:7.1f} / " + " ".join(f"{x:6.1f}" for x in k))
    W = {}
    for c in SETS:
        if all((c, t) in med for t in range(1, 5)):
            W[c] = sum(w * med[(c, t)][0] for w, t in zip(WEIGHTS, range(1, 5)))
    out.append("")
    out.append("W = 0.12 s1 + 0.14 s2 + 0.12 s3 + 0.62 s4 (median span in us):")
    for c in SETS:
        if c in W:
            out.append(f"  {c}: W {W[c]:.1f}" + (f"  ({W[c] / W['base']:.4f} x base)" if "base" in W else ""))
    out.append("per-round W (recorded only):")
    for r, c in ORDER:
        rows = data[(r, c)]
        if all(t in rows for t in range(1, 5)):
            out.append(f"  round {r} {c}: W {sum(w * rows[t][0] for w, t in zip(WEIGHTS, range(1, 5))):.1f}")
    ok = "both" in W and "base" in W and W["both"] < BAR * W["base"]
    choice = "e2e" if ok and not bad else "none"
    out.insert(0, f"choice: {choice}  (e2e: W(both) < {BAR} x W(base); none with any problem)")
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, "hcup-choice.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
