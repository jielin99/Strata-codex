#!/usr/bin/env python3
"""xslm_choice: the checks and the choice of lab/plans/15-xslm.md section 4 over one directory of runs.

  python xslm_choice.py <dir> <device substring>

<dir> holds, for rounds r = 1..3 and settings c = base (STRATA_MMVQ_XSLM unset), 4, 8, 16 (STRATA_MMVQ_XSLM=c):
  mm-<r>-<c>.tsv   mmvq_lab 1024 300 all 6, mm-<r>-<c>.err its stderr, mm-<r>-<c>.bin its MMVQ_LAB_DUMP
  mm8-<c>.tsv      mmvq_lab 256 50 all 8 once per setting (1-8 columns, for the bitwise check only), .err, .bin likewise
  mm-exit.txt      exactly one line "<name> <exit code>" per run (NAMES below)
  env-strata.txt   the output of `set STRATA_` before the runs (the daily config's seven kernel switches)
Writes xslm-choice.txt (problems, the choice, the weighted times) into <dir>. Every failed check is a problem: the first
line is `problems: <count>`, the exit code is 1 if any, and with a problem nothing is chosen. Only counts, compares and
applies the plan's rule.

The weighted time: per column count T, D_T = sum over the model's dense (shape, type) cases of (tensors of that shape
and type, lab/results/01-decode-bound/tensors.tsv) x (us per call); W = 0.12 D_1 + 0.14 D_2 + 0.12 D_3 + 0.62 D_4
(generation windows by T, analysis/03-window-t.md, as plans 14's hcup_choice.py). The chosen setting's median D_5 and
D_6 (windows the prompt lookup makes, up to 6 tokens) must not exceed base's by more than 3%.
"""
import csv
import hashlib
import math
import os
import re
import statistics
import sys
import traceback

SETS = ["base", "4", "8", "16"]
ORDER = [(1, "base"), (1, "4"), (1, "8"), (1, "16"),
         (2, "4"), (2, "8"), (2, "16"), (2, "base"),
         (3, "8"), (3, "16"), (3, "base"), (3, "4")]
NAMES = [f"mm-{r}-{c}" for r, c in ORDER] + [f"mm8-{c}" for c in ["base", "4", "8", "16"]]
ENV_WANT = ["STRATA_GR_DOWN_V2=1", "STRATA_GR_RED_BATCH=1", "STRATA_GR_UP_EPI=1", "STRATA_GR_UP_TREE=1",
            "STRATA_GU_GRID_SLM2=2", "STRATA_MMVQ_Q6_SWAR=1", "STRATA_Q2_SWAR=1"]   # the daily config's after section 3
MM_HEADER = "tensor\ttype\tn_in\tn_out\tcols\tcopies\tus\tGB/s\tchecksum"
COLS = 6
WEIGHTS = [0.12, 0.14, 0.12, 0.62]   # T 1-4
BAR = 0.95
LONG_BAR = 1.03   # D_5, D_6
TENSORS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "01-decode-bound", "tensors.tsv")


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


def tensor_counts(bad):
    """{(type name, n_in, n_out): tensors} over the GGUF's 2-D quantized tensors"""
    names = {12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 20: "IQ4_NL", 21: "IQ3_S", 23: "IQ4_XS", 42: "Q2_0"}
    cnt = {}
    if not os.path.exists(TENSORS):
        bad.append(f"{TENSORS}: missing")
        return cnt
    with open(TENSORS, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            d = r["dims"].split("x")
            if len(d) == 2 and r["type"] in names.values():
                k = (r["type"], int(d[0]), int(d[1]))
                cnt[k] = cnt.get(k, 0) + 1
    return cnt


def parse_mm(path, device, c, bad, cols=COLS, ws="working set: 1024 MiB, 300 ms per case"):
    """{(tensor, type, n_in, n_out, cols): (us, checksum, output bytes)}"""
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    want = [r"device: .*", r"driver: .*", re.escape(ws),
            re.escape("env STRATA_MMVQ_Q6_SWAR=1")] + ([] if c == "base" else [re.escape(f"env STRATA_MMVQ_XSLM={c}")])
    try:
        h = lines.index(MM_HEADER)
    except ValueError:
        bad.append(f"{name}: header missing")
        return {}, None
    pre = lines[:h]
    if len(pre) != len(want) or not all(re.fullmatch(p, ln) for p, ln in zip(want, pre)):
        bad.append(f"{name}: lines before the header {pre}, want {want}")
    if not pre or device not in pre[0]:
        bad.append(f"{name}: device line {pre[0] if pre else ''!r} lacks {device!r}")
    rows = {}
    for ln in lines[h + 1:]:
        p = ln.split("\t")
        if len(p) != 9:
            bad.append(f"{name}: {len(p)} columns: {ln!r}")
            continue
        try:
            key = (p[0], p[1], int(p[2]), int(p[3]), int(p[4]))
            cs = float(p[8])
        except ValueError:
            bad.append(f"{name}: bad row {ln!r}")
            continue
        us = finite_pos(p[6])
        if key in rows:
            bad.append(f"{name}: repeated key {key}")
            continue
        if us is None or not math.isfinite(cs) or cs >= 1e29 or not 1 <= key[4] <= cols:
            bad.append(f"{name}: bad row {ln!r}")
            continue
        rows[key] = (us, p[8], key[3] * key[4] * 4)
    return rows, pre[1] if len(pre) > 1 else None


def sha_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    d, device = sys.argv[1], sys.argv[2]
    out, bad = [], []
    try:
        return run(d, device, out, bad)
    except Exception:   # a failed run must still leave a fresh file that says so
        bad.append("exception: " + traceback.format_exc().strip().replace("\n", " | "))
        out[:] = ["choice: none  (the check failed)"]
        out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
        with open(os.path.join(d, "xslm-choice.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        print("\n".join(out))
        return 1


def run(d, device, out, bad):
    seen = {}
    for ln in read_lines(os.path.join(d, "mm-exit.txt"), bad):
        p = ln.split()
        if len(p) != 2 or p[0] not in NAMES:
            bad.append(f"mm-exit.txt: unexpected line {ln!r}")
        elif p[0] in seen:
            bad.append(f"mm-exit.txt: repeated entry {ln!r}")
        else:
            seen[p[0]] = p[1]
    for n in NAMES:
        if seen.get(n) != "0":
            bad.append(f"mm-exit.txt: {n} -> {seen.get(n)}")
        e = os.path.join(d, n + ".err")
        if not os.path.exists(e) or os.path.getsize(e) != 0:
            bad.append(f"{n}.err: missing or not empty")
    env = read_lines(os.path.join(d, "env-strata.txt"), bad)
    if env != ENV_WANT:
        bad.append(f"env-strata.txt: {env}, want exactly {ENV_WANT}")

    cnt = tensor_counts(bad)
    data, drivers = {}, set()
    for r, c in ORDER:
        data[(r, c)], drv = parse_mm(os.path.join(d, f"mm-{r}-{c}.tsv"), device, c, bad)
        drivers.add(drv)
    keys0 = set(data[ORDER[0]])
    cases = {(k[1], k[2], k[3]) for k in keys0}
    if len(keys0) != 26 * COLS or len(cases) != 26:
        bad.append(f"{NAMES[0]}.tsv: {len(keys0)} rows over {len(cases)} cases, want 26 cases x {COLS} columns")
    for rc in ORDER[1:]:
        if set(data[rc]) != keys0:
            bad.append(f"mm-{rc[0]}-{rc[1]}.tsv: its cases differ from {NAMES[0]}.tsv")
    missing = sorted(c for c in cases if c not in cnt)
    if missing:
        bad.append(f"cases with no tensor count: {missing}")
    complete = len(keys0) == 26 * COLS and len(cases) == 26 and all(set(data[rc]) == keys0 for rc in ORDER)

    # bitwise: every run's checksums and its whole dump equal round 1 base's
    ref_cs = {k: v[1] for k, v in data[ORDER[0]].items()}
    want_size = sum(v[2] for v in data[ORDER[0]].values())
    digests = {}
    for r, c in ORDER:
        diff = [k for k, v in data[(r, c)].items() if ref_cs.get(k) != v[1]]
        if diff:
            bad.append(f"mm-{r}-{c}.tsv: {len(diff)} checksums differ from {NAMES[0]}.tsv, first {diff[0]}")
        p = os.path.join(d, f"mm-{r}-{c}.bin")
        if not os.path.exists(p):
            bad.append(f"mm-{r}-{c}.bin: missing")
            continue
        size = os.path.getsize(p)
        if size != want_size or size == 0:
            bad.append(f"mm-{r}-{c}.bin: {size} bytes, want {want_size}")
        digests[(r, c)] = sha_of(p)
    same = len(set(digests.values())) == 1 and len(digests) == len(ORDER)
    if not same:
        bad.append("the 12 dumps are not all the same bytes")
    d8, cs8 = {}, {}
    keys8 = {k[:4] + (t,) for k in keys0 for t in range(1, 9)}   # the timed runs' cases, 1-8 columns each
    for c in SETS:
        rows8, drv8 = parse_mm(os.path.join(d, f"mm8-{c}.tsv"), device, c, bad, 8, "working set: 256 MiB, 50 ms per case")
        drivers.add(drv8)
        if len(rows8) != 26 * 8 or set(rows8) != keys8:
            bad.append(f"mm8-{c}.tsv: {len(rows8)} rows, want {NAMES[0]}.tsv's 26 cases x 8 columns")
        cs8[c] = {k: v[1] for k, v in rows8.items()}
        p = os.path.join(d, f"mm8-{c}.bin")
        size8 = sum(v[2] for v in rows8.values())
        if not os.path.exists(p) or os.path.getsize(p) != size8 or size8 == 0:
            bad.append(f"mm8-{c}.bin: missing or not {size8} bytes")
            continue
        d8[c] = sha_of(p)
    same8 = len(d8) == 4 and len(set(d8.values())) == 1 and all(cs8[c] == cs8["base"] for c in SETS)
    if not same8:
        bad.append("the 4 one-to-eight-column dumps (mm8-*) are not all the same bytes, or their checksums differ")
    if len(drivers) != 1:
        bad.append(f"driver lines differ across the 16 runs: {sorted(str(x) for x in drivers)}")
    out.append(f"bitwise: 12 dumps the same bytes {same} (sha256 {sorted(set(digests.values()))[0][:16] if digests else '-'}"
               f", {want_size} bytes each); checksums the same in every run; 1-8 columns (mm8-*) the same {same8}")

    def dsum(rows, t, types=None):
        return sum(cnt.get((k[1], k[2], k[3]), 0) * v[0] for k, v in rows.items()
                   if k[4] == t and (types is None or k[1] in types)) / 1000.0

    if not complete:   # the times below need every run's every row (the gaps are problems above)
        out.insert(0, "choice: none  (the runs' tables are incomplete)")
        out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
        with open(os.path.join(d, "xslm-choice.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        print("\n".join(out))
        return 1
    W = {}
    for r, c in ORDER:
        W[(r, c)] = sum(w * dsum(data[(r, c)], t) for w, t in zip(WEIGHTS, range(1, 5)))
    Wm = {c: statistics.median(W[(r, c)] for r in (1, 2, 3)) for c in SETS}
    out.append("")
    out.append("W = 0.12 D1 + 0.14 D2 + 0.12 D3 + 0.62 D4 (ms; D_T = tensors x us summed over the 26 cases):")
    for c in SETS:
        out.append(f"  {c:4s}: median W {Wm[c]:.3f}  ({Wm[c] / Wm['base']:.4f} x base)  rounds " +
                   " ".join(f"{W[(r, c)]:.3f}" for r in (1, 2, 3)))
    out.append("")
    out.append("median D_T by type (ms), T = 1..6 (recorded only):")
    for ty in ("Q4_K", "Q5_K", "Q6_K", "IQ4_XS", "IQ3_S", "IQ4_NL", "Q2_0"):
        for c in SETS:
            vals = [statistics.median(dsum(data[(r, c)], t, {ty}) for r in (1, 2, 3)) for t in range(1, COLS + 1)]
            out.append(f"  {ty:6s} {c:4s}: " + " ".join(f"{v:7.3f}" for v in vals))
    out.append("")
    out.append("median us per case (recorded only): tensor type n_in n_out cols / base 4 8 16")
    for k in sorted(keys0, key=lambda k: (k[0], k[1], k[4])):
        out.append("  " + " ".join(map(str, k)) + " / " +
                   " ".join(f"{statistics.median(data[(r, c)][k][0] for r in (1, 2, 3)):.1f}" for c in SETS))
    best = min(("4", "8", "16"), key=lambda c: Wm[c])
    every = all(W[(r, best)] < W[(r, "base")] for r in (1, 2, 3))
    longer = {t: statistics.median(dsum(data[(r, best)], t) for r in (1, 2, 3)) /
              statistics.median(dsum(data[(r, "base")], t) for r in (1, 2, 3)) for t in (5, 6)}
    ok = Wm[best] < BAR * Wm["base"] and every and all(v <= LONG_BAR for v in longer.values())
    choice = best if ok and not bad else "none"
    out.insert(0, f"choice: {choice}  (the setting of the smallest median W, if below {BAR} x W(base) and below base's W"
                  f" in each round; none with any problem); best {best} {Wm[best] / Wm['base']:.4f} x base,"
                  f" every round below base: {every}; D5, D6 x base {longer[5]:.4f}, {longer[6]:.4f} (at most {LONG_BAR})")
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, "xslm-choice.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out[:12]))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
