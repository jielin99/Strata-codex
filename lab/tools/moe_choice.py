#!/usr/bin/env python3
"""moe_choice: the checks and the choice of lab/plans/12-moe-slm2.md over one directory of runs.

  python moe_choice.py <dir> <device substring>

<dir> holds, for rounds r = 1..3 and settings s = off, 1, 2 (STRATA_GU_GRID_SLM2 unset, =1, =2):
  mp-<r>-<s>.tsv   moe_probe 200 4, and mp-<r>-<s>.err its stderr
  ngp-<s>.txt      native_grouped_parity (stdout and stderr) with setting s
  mp-exit.txt      exactly one line "<name> <exit code>" per run: warm-off, warm-1, warm-2, the 9 mp-<r>-<s>,
                   ngp-off, ngp-1, ngp-2
  env-strata.txt   the output of `set STRATA_` before the runs
Writes choice.txt (problems, the choice, the weighted times) and medians.tsv (every timed key: the median of the
3 rounds per setting and each setting / off - 1) into <dir>.
Every failed check is a problem: the first line of choice.txt is `problems: <count>`, the exit code is 1 if any,
and with a problem no setting is chosen. Only counts, compares and applies the plan's rule.
"""
import math
import os
import re
import statistics
import sys

SETTINGS = ["off", "1", "2"]
ORDER = [(1, "off"), (1, "1"), (1, "2"), (2, "1"), (2, "2"), (2, "off"), (3, "2"), (3, "off"), (3, "1")]
NAMES = [f"warm-{s}" for s in SETTINGS] + [f"mp-{r}-{s}" for r, s in ORDER] + [f"ngp-{s}" for s in SETTINGS]
ENV_WANT = ["STRATA_Q2_SWAR=1"]
HEX16 = re.compile(r"^[0-9a-f]{16}$")
MP_HEADER = "case\tscope\tlayers\tgroups\tentries\tmem\tphase\tus_per_layer\tGB/s\titers\tchecksum\tgu_checksum"
# the keys moe_probe 200 4 prints (case: groups, entries; scope: layers), 7 x 11 x 2 x 3 = 462
CASES = {"T1": ("10", "10"), "T2": ("17", "20"), "T3": ("25", "30"), "T4": ("30", "40"),
         "G10x1": ("10", "10"), "G10x2": ("10", "20"), "G10x4": ("10", "40")}
SCOPES = {"window": "48", "16/20": "1", "16/42": "8", "17/20": "4", "17/42": "6", "18/20": "3", "18/42": "3",
          "21/20": "6", "21/42": "7", "22/20": "4", "22/42": "6"}
EXPECTED = {(c, sc, ly, g, e, mem, ph) for c, (g, e) in CASES.items() for sc, ly in SCOPES.items()
            for mem in ("dram", "cached") for ph in ("all", "gu", "down")}
WEIGHTS = {"T1": 0.12, "T2": 0.14, "T3": 0.12, "T4": 0.62}   # generation windows by T (analysis/03-window-t.md)
BAR = 0.98


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


def parse_mp(path, device, setting, bad):
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    try:
        h = lines.index(MP_HEADER)
    except ValueError:
        bad.append(f"{name}: header missing")
        return {}, None
    pre = lines[:h]
    want = [r"device: .*", r"driver: .*", r"200 ms per case", r"env STRATA_Q2_SWAR=1"]
    if setting != "off":
        want.append(rf"env STRATA_GU_GRID_SLM2={setting}")
    want.append(r"experts in device memory: \d+ MB \(48 layers x \d+\)")
    if len(pre) != len(want) or not all(re.fullmatch(p, ln) for p, ln in zip(want, pre)):
        bad.append(f"{name}: lines before the header {pre}, want {want}")
    if not pre or not pre[0].startswith("device: ") or device not in pre[0]:
        bad.append(f"{name}: device line {pre[0] if pre else ''!r} lacks {device!r}")
    driver = pre[1] if len(pre) > 1 else None
    rows = {}
    for ln in lines[h + 1:]:
        p = ln.split("\t")
        if len(p) != 12:
            bad.append(f"{name}: {len(p)} columns: {ln!r}")
            continue
        key = tuple(p[:7])
        if key in rows:
            bad.append(f"{name}: repeated key {key}")
            continue
        us = finite_pos(p[7])
        try:
            iters = int(p[9])
        except ValueError:
            iters = 0
        if us is None or iters < 1:
            bad.append(f"{name}: bad row {ln!r}")
            continue
        if p[6] == "all":
            if not (HEX16.match(p[10]) and HEX16.match(p[11])):
                bad.append(f"{name}: bad checksums {ln!r}")
                continue
            rows[key] = (us, p[10] + " " + p[11])
        elif p[10] != "-" or p[11] != "-":
            bad.append(f"{name}: checksum on a phase row {ln!r}")
            continue
        else:
            rows[key] = (us, None)
    if set(rows) != EXPECTED:
        bad.append(f"{name}: {len(EXPECTED - set(rows))} expected keys missing, {len(set(rows) - EXPECTED)} unexpected keys")
    if len(rows) != 462 or sum(1 for r in rows.values() if r[1] is not None) != 154:
        bad.append(f"{name}: {len(rows)} valid rows, {sum(1 for r in rows.values() if r[1] is not None)} with checksums;"
                   " want 462 and 154")
    return rows, driver


def main():
    d, device = sys.argv[1], sys.argv[2]
    out, bad = [], []
    seen = {}
    for ln in read_lines(os.path.join(d, "mp-exit.txt"), bad):
        p = ln.split()
        if len(p) != 2 or p[0] not in NAMES:
            bad.append(f"mp-exit.txt: unexpected line {ln!r}")
        elif p[0] in seen:
            bad.append(f"mp-exit.txt: repeated entry {ln!r}")
        else:
            seen[p[0]] = p[1]
    for n in NAMES:
        if seen.get(n) != "0":
            bad.append(f"mp-exit.txt: {n} -> {seen.get(n)}")
    for r, s in ORDER:
        e = os.path.join(d, f"mp-{r}-{s}.err")
        if not os.path.exists(e) or os.path.getsize(e) != 0:
            bad.append(f"mp-{r}-{s}.err: missing or not empty")
    env = read_lines(os.path.join(d, "env-strata.txt"), bad)
    if env != ENV_WANT:
        bad.append(f"env-strata.txt: {env}, want exactly {ENV_WANT}")
    for s in SETTINGS:
        lines = read_lines(os.path.join(d, f"ngp-{s}.txt"), bad)
        if not lines or lines[-1] != "native_grouped_parity: 0 failures":
            bad.append(f"ngp-{s}.txt: last line {lines[-1] if lines else ''!r}, want 'native_grouped_parity: 0 failures'")
    out.append(f"integrity: {len(NAMES)} exit codes, 9 stderr files, env-strata.txt, 3 ngp files")

    data, drivers = {}, set()
    for r, s in ORDER:
        data[(r, s)], dr = parse_mp(os.path.join(d, f"mp-{r}-{s}.tsv"), device, s, bad)
        if dr:
            drivers.add(dr)
    if len(drivers) != 1:
        bad.append(f"driver lines differ or are missing: {sorted(drivers)}")

    # the same outputs for every setting and round
    keys = set(data[ORDER[0]])
    if any(set(v) != keys for v in data.values()):
        bad.append("key sets differ between the runs")
    ck = [k for k in sorted(keys) if data[ORDER[0]][k][1] is not None]
    diff = [k for k in ck if len({v[k][1] if k in v else None for v in data.values()}) != 1]
    if diff:
        bad.append(f"{len(diff)} keys with different checksums, first {[' '.join(k) for k in diff[:5]]}")
    out.append(f"equal outputs across the 9 runs: {len(ck)} keys with checksum and gu_checksum, {len(diff)} differ")

    # medians of the 3 rounds per setting
    med = {}
    for k in sorted(keys):
        if all(k in data[(r, s)] for r, s in ORDER):
            med[k] = {s: statistics.median(data[(r, s2)][k][0] for r, s2 in ORDER if s2 == s) for s in SETTINGS}
    with open(os.path.join(d, "medians.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("case\tscope\tlayers\tgroups\tentries\tmem\tphase\toff_us\tslm2_1_us\tslm2_2_us\t1/off-1\t2/off-1\n")
        for k, m in med.items():
            f.write("\t".join(k) + f"\t{m['off']:.1f}\t{m['1']:.1f}\t{m['2']:.1f}"
                    f"\t{m['1'] / m['off'] - 1:+.4f}\t{m['2'] / m['off'] - 1:+.4f}\n")

    # the weighted time W per setting and the choice
    out.append("")
    out.append("W = 0.12 t1 + 0.14 t2 + 0.12 t3 + 0.62 t4 (t = median us/layer of T1..T4, window, dram, all):")
    wkey = {}
    for c in WEIGHTS:
        hit = [x for x in med if x[:3] == (c, "window", "48") and x[5] == "dram" and x[6] == "all"]
        if len(hit) != 1:
            bad.append(f"{c} window dram all: {len(hit)} rows")
        else:
            wkey[c] = hit[0]
    W = {}
    for s in SETTINGS:
        t = {c: med[k][s] for c, k in wkey.items()}
        if len(t) == 4:
            W[s] = sum(WEIGHTS[c] * t[c] for c in WEIGHTS)
            out.append(f"  {s}: t1..t4 {t['T1']:.1f} {t['T2']:.1f} {t['T3']:.1f} {t['T4']:.1f}  W {W[s]:.1f}")
    for s in ("1", "2"):
        if s in W and "off" in W:
            out.append(f"  W({s}) / W(off) = {W[s] / W['off']:.4f}")
    # per-round W, recorded only
    if len(wkey) == 4:
        for r, s in ORDER:
            out.append(f"  round {r} {s}: W {sum(WEIGHTS[c] * data[(r, s)][k][0] for c, k in wkey.items()):.1f}")
    ok = [s for s in ("1", "2") if s in W and "off" in W and W[s] < BAR * W["off"]]
    choice = min(ok, key=lambda s: W[s]) if ok and not bad else "none"
    out.insert(0, f"choice: {choice}  (a setting with W < {BAR} x W(off), the smaller W of the two; none with any problem)")

    # recorded only: T3 and G10x2, window, both layouts, all phases
    out.append("")
    out.append("recorded only (median us/layer, off / 1 / 2):")
    for c in ("T3", "G10x2"):
        for mem in ("dram", "cached"):
            for ph in ("all", "gu", "down"):
                hit = [x for x in med if x[0] == c and x[1] == "window" and x[5] == mem and x[6] == ph]
                for x in hit:
                    m = med[x]
                    out.append(f"  {c} {mem} {ph}: {m['off']:.1f} / {m['1']:.1f} / {m['2']:.1f}")
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, "choice.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
