#!/usr/bin/env python3
"""addr_check: the checks of lab/plans/11-addr64.md over one directory of runs.

  python addr_check.py <dir> <device substring>

<dir> holds, for runs i = 1..4 built as a64, a32, a32, a64 (with / without -ze-opt-greater-than-4GB-buffer-required):
  gr-<i>-<v>.txt   gr_bench (6 lines, T = 1..6)
  mp-<i>-<v>.tsv   moe_probe 200 4
  mm-<i>-<v>.tsv   mmvq_lab 1024 300 all, and mm-<i>-<v>.bin its MMVQ_LAB_DUMP
  <name>.err       the stderr of each of the 12 runs
  exit.txt         exactly one line "<name> <exit code>" per run (the 6 warm-up runs too)
  env-strata.txt   the output of `set STRATA_`
Writes check.txt (integrity, equal outputs across the builds, run-to-run differences, ratio summary) and averages.tsv
(every timed key: the a64 mean of runs 1 and 4, the a32 mean of runs 2 and 3, a32 / a64 - 1) into <dir>.
Every failed check is a problem: the first line of check.txt is `problems: <count>` and the exit code is 1 if any.
Only counts and compares; it draws no conclusion.
"""
import hashlib
import math
import os
import re
import statistics
import sys

RUNS = [(1, "a64"), (2, "a32"), (3, "a32"), (4, "a64")]
WARM = ["warm-a64-gr", "warm-a64-mp", "warm-a64-mm", "warm-a32-gr", "warm-a32-mp", "warm-a32-mm"]
ENV_WANT = {"STRATA_GR_DOWN_V2=1", "STRATA_GR_UP_EPI=1", "STRATA_MMVQ_Q6_SWAR=1", "STRATA_Q2_SWAR=1"}
GR_RE = re.compile(r"^fused GR read, (\d) tokens: +([0-9.]+) us \(.*\)  checksum ([0-9a-f]{16})  sum (\S+)$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
MP_HEADER = "case\tscope\tlayers\tgroups\tentries\tmem\tphase\tus_per_layer\tGB/s\titers\tchecksum\tgu_checksum"
MM_HEADER = "tensor\ttype\tn_in\tn_out\tcols\tcopies\tus\tGB/s\tchecksum"


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


def parse_gr(path, bad):
    name, rows = os.path.basename(path), {}
    lines = read_lines(path, bad)
    for ln in lines:
        m = GR_RE.match(ln)
        if not m:
            bad.append(f"{name}: unexpected line: {ln!r}")
            continue
        key = ("T" + m.group(1),)
        us = finite_pos(m.group(2))
        try:
            total = float(m.group(4))
        except ValueError:
            total = float("nan")
        if us is None or not math.isfinite(total) or key in rows:
            bad.append(f"{name}: bad, non-finite or repeated row: {ln!r}")
            continue
        rows[key] = (us, m.group(3) + " " + m.group(4))
    if len(lines) != 6 or sorted(rows) != [("T%d" % t,) for t in range(1, 7)]:
        bad.append(f"{name}: {len(lines)} lines, T values {sorted(k[0] for k in rows)}; want 6 lines, T1..T6")
    return rows


def parse_table(path, device, header, ncols, nkey, preamble, bad, row_fn):
    """preamble: regexes the lines before the header must match, one each, in order"""
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    try:
        h = lines.index(header)
    except ValueError:
        bad.append(f"{name}: header missing")
        return {}, None
    pre = lines[:h]
    if len(pre) != len(preamble) or not all(re.fullmatch(p, ln) for p, ln in zip(preamble, pre)):
        bad.append(f"{name}: lines before the header {pre}, want {preamble}")
    if not pre or not pre[0].startswith("device: ") or device not in pre[0]:
        bad.append(f"{name}: device line {pre[0] if pre else ''!r} lacks {device!r}")
    driver = pre[1] if len(pre) > 1 else None
    rows = {}
    for ln in lines[h + 1:]:
        p = ln.split("\t")
        if len(p) != ncols:
            bad.append(f"{name}: {len(p)} columns: {ln!r}")
            continue
        key = tuple(p[:nkey])
        if key in rows:
            bad.append(f"{name}: repeated key {key}")
            continue
        r = row_fn(p)
        if r is None:
            bad.append(f"{name}: bad row {ln!r}")
            continue
        rows[key] = r
    return rows, driver


def mp_row(p):   # case scope layers groups entries mem phase us_per_layer GB/s iters checksum gu_checksum
    us = finite_pos(p[7])
    try:
        iters = int(p[9])
    except ValueError:
        return None
    if us is None or iters < 1:
        return None
    if p[6] == "all":
        if not (HEX16.match(p[10]) and HEX16.match(p[11])):
            return None
        return (us, p[10] + " " + p[11])
    if p[10] != "-" or p[11] != "-":
        return None
    return (us, None)


def mm_row(p):   # tensor type n_in n_out cols copies us GB/s checksum
    us = finite_pos(p[6])
    try:
        cs, n_out, cols = float(p[8]), int(p[3]), int(p[4])
    except ValueError:
        return None
    if us is None or not math.isfinite(cs) or cs >= 1e29 or n_out < 1 or cols < 1:
        return None
    return (us, p[8], n_out * cols * 4)


def main():
    d, device = sys.argv[1], sys.argv[2]
    out, bad = [], []
    # exit codes, stderr, environment
    want = WARM + [f"{t}-{i}-{v}" for i, v in RUNS for t in ("gr", "mp", "mm")]
    seen = {}
    for ln in read_lines(os.path.join(d, "exit.txt"), bad):
        p = ln.split()
        if len(p) != 2 or p[0] not in want:
            bad.append(f"exit.txt: unexpected line {ln!r}")
        elif p[0] in seen:
            bad.append(f"exit.txt: repeated entry {ln!r}")
        else:
            seen[p[0]] = p[1]
    for n in want:
        if seen.get(n) != "0":
            bad.append(f"exit.txt: {n} -> {seen.get(n)}")
    for i, v in RUNS:
        for t in ("gr", "mp", "mm"):
            e = os.path.join(d, f"{t}-{i}-{v}.err")
            if not os.path.exists(e) or os.path.getsize(e) != 0:
                bad.append(f"{t}-{i}-{v}.err: missing or not empty")
    env = read_lines(os.path.join(d, "env-strata.txt"), bad)
    if len(env) != 4 or set(env) != ENV_WANT:
        bad.append(f"env-strata.txt: {env}, want exactly {sorted(ENV_WANT)}")
    out.append(f"integrity: {len(want)} exit codes, 12 stderr files, env-strata.txt")

    data = {"gr": {}, "mp": {}, "mm": {}}
    drivers = set()
    for i, v in RUNS:
        data["gr"][i] = parse_gr(os.path.join(d, f"gr-{i}-{v}.txt"), bad)
        data["mp"][i], dr1 = parse_table(os.path.join(d, f"mp-{i}-{v}.tsv"), device, MP_HEADER, 12, 7,
                                         [r"device: .*", r"driver: .*", r"200 ms per case", r"env STRATA_Q2_SWAR=1",
                                          r"experts in device memory: \d+ MB \(48 layers x \d+\)"], bad, mp_row)
        data["mm"][i], dr2 = parse_table(os.path.join(d, f"mm-{i}-{v}.tsv"), device, MM_HEADER, 9, 5,
                                         [r"device: .*", r"driver: .*", r"working set: 1024 MiB, 300 ms per case",
                                          r"env STRATA_MMVQ_Q6_SWAR=1"], bad, mm_row)
        drivers.update(x for x in (dr1, dr2) if x)
    if len(drivers) != 1:
        bad.append(f"driver lines differ or are missing: {sorted(drivers)}")
    want_rows = {"gr": 6, "mp": 462, "mm": 156}
    for t in data:
        for i, v in RUNS:
            n = len(data[t][i])
            if n != want_rows[t]:
                bad.append(f"{t}-{i}-{v}: {n} valid rows, want {want_rows[t]}")
    for i, v in RUNS:
        nall = sum(1 for r in data["mp"][i].values() if r[1] is not None)
        if nall != 154:
            bad.append(f"mp-{i}-{v}: {nall} rows with checksums, want 154")

    # the same outputs from both builds
    out.append("")
    out.append("equal outputs across the 4 runs (both builds):")
    for t in data:
        keys = set(data[t][1])
        if any(set(data[t][i]) != keys for i, _ in RUNS):
            bad.append(f"{t}: key sets differ between runs")
        ck = [k for k in sorted(keys) if data[t][1][k][1] is not None]
        diff = [k for k in ck if len({data[t][i][k][1] if k in data[t][i] else None for i, _ in RUNS}) != 1]
        if diff:
            bad.append(f"{t}: {len(diff)} keys with different checksums, first {[' '.join(k) for k in diff[:5]]}")
        out.append(f"  {t}: {len(ck)} keys with checksums, {len(diff)} differ")
    shas = []
    for i, v in RUNS:
        p = os.path.join(d, f"mm-{i}-{v}.bin")
        want_size = sum(r[2] for r in data["mm"][i].values())
        if not os.path.exists(p):
            bad.append(f"mm-{i}-{v}.bin: missing")
            shas.append(None)
            continue
        size = os.path.getsize(p)
        if size != want_size or size == 0:
            bad.append(f"mm-{i}-{v}.bin: {size} bytes, want {want_size} (sum of cols x n_out x 4 over the table)")
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        shas.append(h.hexdigest())
        out.append(f"  mm-{i}-{v}.bin: {size} bytes (want {want_size}), sha256 {h.hexdigest()}")
    same_dump = len(set(shas)) == 1 and None not in shas
    if not same_dump:
        bad.append("mmvq_lab dumps differ or are missing")
    out.append(f"  mmvq_lab dumps identical: {same_dump}")

    # run-to-run differences within a build, and the build ratio
    out.append("")
    out.append("largest |difference| between the two runs of the same build (us):")
    avg = []
    for t in data:
        keys = sorted(data[t][1])
        for (a, b, v) in ((1, 4, "a64"), (2, 3, "a32")):
            ds = [(data[t][b][k][0] / data[t][a][k][0] - 1, k) for k in keys if k in data[t][a] and k in data[t][b]]
            if ds:
                m = max(ds, key=lambda x: abs(x[0]))
                out.append(f"  {t} {v} (run {b} / run {a} - 1): {m[0]:+.4f} at {' '.join(m[1])}")
        rs = []
        for k in keys:
            if not all(k in data[t][i] for i, _ in RUNS):
                continue
            m64 = (data[t][1][k][0] + data[t][4][k][0]) / 2
            m32 = (data[t][2][k][0] + data[t][3][k][0]) / 2
            avg.append((t, " ".join(k), m64, m32, m32 / m64 - 1))
            rs.append(m32 / m64 - 1)
        if rs:
            out.append(f"  {t}: a32 / a64 - 1 over {len(rs)} keys: median {statistics.median(rs):+.4f}, "
                       f"min {min(rs):+.4f}, max {max(rs):+.4f}")
    with open(os.path.join(d, "averages.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("tool\tkey\ta64_us\ta32_us\ta32/a64-1\n")
        for t, k, m64, m32, r in avg:
            f.write(f"{t}\t{k}\t{m64:.2f}\t{m32:.2f}\t{r:+.4f}\n")
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, "check.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
