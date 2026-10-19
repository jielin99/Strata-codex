#!/usr/bin/env python3
"""hc_choice: the checks and the choice of lab/plans/13-hc-q8.md over one directory of runs.

  python hc_choice.py <dir>

<dir> holds, for rounds r = 1..3 and modes m = bf16, q8, bf16d, q8d (gr_bench, gr_bench q8, gr_bench dram,
gr_bench q8 dram):
  gr-<r>-<m>.txt   gr_bench's stdout, and gr-<r>-<m>.err its stderr
  gq-parity.txt    gr_q8_parity (stdout and stderr)
  gr-exit.txt      exactly one line "<name> <exit code>" per run: gq-parity and the 12 gr-<r>-<m>
  env-strata.txt   the output of `set STRATA_` before the runs
Writes hc-choice.txt (problems, the choice, the weighted times) into <dir>.
Every failed check is a problem: the first line of hc-choice.txt is `problems: <count>`, the exit code is 1 if any,
and with a problem nothing is chosen. Only counts, compares and applies the plan's rule.
"""
import math
import os
import re
import statistics
import sys

MODES = ["bf16", "q8", "bf16d", "q8d"]
ORDER = [(1, "bf16"), (1, "q8"), (1, "bf16d"), (1, "q8d"),
         (2, "q8"), (2, "bf16d"), (2, "q8d"), (2, "bf16"),
         (3, "bf16d"), (3, "q8d"), (3, "bf16"), (3, "q8")]
NAMES = ["gq-parity"] + [f"gr-{r}-{m}" for r, m in ORDER]
ENV_WANT = ["STRATA_GR_DOWN_V2=1", "STRATA_GR_UP_EPI=1"]
LABEL = {"bf16": "", "q8": " (Q8_0)", "bf16d": " (16 copies)", "q8d": " (Q8_0) (16 copies)"}
LINE = re.compile(r"fused GR read(?P<label>( \(Q8_0\))?( \(16 copies\))?), (?P<t>\d) tokens: +(?P<us>\S+) us "
                  r"\((?P<gbs>\d+) GB/s of weights\)  checksum (?P<cs>[0-9a-f]{16})  sum (?P<sum>\S+)")
# the BF16 read's checksums at 1-6 tokens: gr_bench's on the 140T in 11 (a64 build) and on the UHD 730 (a3b39b06)
BF16_CS = ["156044a29131637f", "ada635710c63920a", "ac6937afab84574b", "3441f4d29598c269", "94c690071d72f1bc",
           "0cce58250c149197"]
# the Q8_0 read's checksums on the UHD 730 (recorded only: another device may round differently)
Q8_CS_UHD = ["f72c01275654706f", "e11a1f7deebf374a", "d1ffa82a7c5ded8b", "58f4ee1e873b5eee", "e61d53f94ee4f28e",
             "7ce08e4e8a5bc5e1"]
WEIGHTS = [0.12, 0.14, 0.12, 0.62]   # generation windows by T (analysis/03-window-t.md), T 1-4
BAR = 0.98
PARITY_OK = 96                       # gr_q8_parity's lines: 2 checks x 3 inject rows x 2 (pending write) x 8 T


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


def parse_gr(path, mode, bad):
    """{T: (us, checksum)} for T 1..6, or {} with the problems added."""
    name = os.path.basename(path)
    lines = read_lines(path, bad)
    if len(lines) != 6:
        bad.append(f"{name}: {len(lines)} lines, want 6")
    rows = {}
    for i, ln in enumerate(lines):
        m = LINE.fullmatch(ln)
        if not m:
            bad.append(f"{name}: unexpected line {ln!r}")
            continue
        t = int(m["t"])
        us = finite_pos(m["us"])
        try:
            s = float(m["sum"])
        except ValueError:
            s = math.nan
        if m["label"] != LABEL[mode] or t != i + 1 or us is None or not math.isfinite(s) or t in rows:
            bad.append(f"{name}: bad line {ln!r}")
            continue
        rows[t] = (us, m["cs"])
    if sorted(rows) != [1, 2, 3, 4, 5, 6]:
        bad.append(f"{name}: token counts {sorted(rows)}, want 1-6")
    return rows


def main():
    d = sys.argv[1]
    out, bad = [], []
    seen = {}
    for ln in read_lines(os.path.join(d, "gr-exit.txt"), bad):
        p = ln.split()
        if len(p) != 2 or p[0] not in NAMES:
            bad.append(f"gr-exit.txt: unexpected line {ln!r}")
        elif p[0] in seen:
            bad.append(f"gr-exit.txt: repeated entry {ln!r}")
        else:
            seen[p[0]] = p[1]
    for n in NAMES:
        if seen.get(n) != "0":
            bad.append(f"gr-exit.txt: {n} -> {seen.get(n)}")
    for r, m in ORDER:
        e = os.path.join(d, f"gr-{r}-{m}.err")
        if not os.path.exists(e) or os.path.getsize(e) != 0:
            bad.append(f"gr-{r}-{m}.err: missing or not empty")
    env = read_lines(os.path.join(d, "env-strata.txt"), bad)
    if env != ENV_WANT:
        bad.append(f"env-strata.txt: {env}, want exactly {ENV_WANT}")
    par = read_lines(os.path.join(d, "gq-parity.txt"), bad)
    n_ok = sum(1 for ln in par if re.fullmatch(r"(same|ref ) (plain|apply) inj=(bf16|q8|none) T=[1-8]: .* ok", ln))
    if not par or par[-1] != "gr_q8_parity: 0 failures" or n_ok != PARITY_OK or len(par) != PARITY_OK + 1:
        bad.append(f"gq-parity.txt: {n_ok} ok lines of {len(par)}, last {par[-1] if par else ''!r};"
                   f" want {PARITY_OK} ok lines and 'gr_q8_parity: 0 failures'")
    out.append(f"integrity: {len(NAMES)} exit codes, 12 stderr files, env-strata.txt, gq-parity.txt")

    data = {(r, m): parse_gr(os.path.join(d, f"gr-{r}-{m}.txt"), m, bad) for r, m in ORDER}

    # the BF16 read: the known checksums in every run; the Q8_0 read: one checksum per T in every run
    for (r, m), rows in data.items():
        if m in ("bf16", "bf16d"):
            diff = [t for t in rows if rows[t][1] != BF16_CS[t - 1]]
            if diff:
                bad.append(f"gr-{r}-{m}.txt: BF16 checksums differ from the known ones at T {diff}")
    q8cs = {t: {rows[t][1] for (r, m), rows in data.items() if m in ("q8", "q8d") and t in rows} for t in range(1, 7)}
    if any(len(v) != 1 for v in q8cs.values()):
        bad.append(f"Q8_0 checksums differ between runs: {q8cs}")
    same_uhd = all(q8cs[t] == {Q8_CS_UHD[t - 1]} for t in range(1, 7))
    out.append(f"BF16 checksums = the known ones in the 6 BF16 runs; Q8_0 checksums one per T in the 6 Q8_0 runs;"
               f" Q8_0 checksums equal to the UHD 730's (recorded only): {same_uhd}")

    # medians of the 3 rounds per mode and T
    med = {}
    for m in MODES:
        for t in range(1, 7):
            v = [data[(r, m)][t][0] for r in (1, 2, 3) if t in data[(r, m)]]
            if len(v) == 3:
                med[(m, t)] = statistics.median(v)
    out.append("")
    out.append("median us per read (3 rounds), T = 1..6:")
    for m in MODES:
        out.append(f"  {m:6s}" + "".join(f" {med[(m, t)]:8.1f}" if (m, t) in med else "        -" for t in range(1, 7)))
    for a, b in (("q8", "bf16"), ("q8d", "bf16d")):
        if all((x, t) in med for x in (a, b) for t in range(1, 7)):
            out.append(f"  {a}/{b} - 1:" + "".join(f" {med[(a, t)] / med[(b, t)] - 1:+.3f}" for t in range(1, 7)))

    W = {}
    for m in MODES:
        if all((m, t) in med for t in range(1, 5)):
            W[m] = sum(w * med[(m, t)] for w, t in zip(WEIGHTS, range(1, 5)))
    out.append("")
    out.append("W = 0.12 t1 + 0.14 t2 + 0.12 t3 + 0.62 t4 (median us per read):")
    for m in MODES:
        if m in W:
            out.append(f"  {m}: W {W[m]:.1f}")
    for a, b in (("q8", "bf16"), ("q8d", "bf16d")):
        if a in W and b in W:
            out.append(f"  W({a}) / W({b}) = {W[a] / W[b]:.4f}")
    out.append("per-round W (recorded only):")
    for r, m in ORDER:
        rows = data[(r, m)]
        if all(t in rows for t in range(1, 5)):
            out.append(f"  round {r} {m}: W {sum(w * rows[t][0] for w, t in zip(WEIGHTS, range(1, 5))):.1f}")
    ok = "q8d" in W and "bf16d" in W and W["q8d"] < BAR * W["bf16d"]
    choice = "q8" if ok and not bad else "none"
    out.insert(0, f"choice: {choice}  (q8: W(q8d) < {BAR} x W(bf16d), the 16-copy runs; none with any problem)")
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, "hc-choice.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
