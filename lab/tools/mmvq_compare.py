"""mmvq_compare: put mmvq_lab runs of several builds side by side.
    python mmvq_compare.py <out.tsv> <label>=<run.tsv> [<label>=<run.tsv> ...]
Runs with the same label are repeats of one build (for example base=base-1.tsv base=base-2.tsv nosat=...). For each
(tensor, type, cols) the output has, per label, the median microseconds over its repeats and the GB/s that gives,
then each later label's speed over the first label's (> 1 = faster). A row whose checksums differ between any two
runs is marked in the last column; the inputs are the same synthetic bytes, so a correct change keeps them equal.
The first lines of each run (device, driver, working set, env) are printed so they can be checked to match."""
import statistics
import sys

out, specs = sys.argv[1], sys.argv[2:]
labels, runs = [], []
for sp in specs:
    label, path = sp.split("=", 1)
    if label not in labels:
        labels.append(label)
    rows = {}
    for line in open(path, encoding="utf-8"):
        f = line.rstrip("\r\n").split("\t")
        if len(f) == 9 and f[0] != "tensor":
            key = (f[0], f[1], f[2], f[3], f[4])
            rows[key] = (float(f[6]), float(f[7]), f[8], int(f[5]))
        elif len(f) == 1 and f[0]:
            print(f"{label} {path}: {f[0]}")
    runs.append((label, path, rows))

keys = []
for _, _, rows in runs:
    for k in rows:
        if k not in keys:
            keys.append(k)

hdr = ["tensor", "type", "n_in", "n_out", "cols"]
for lb in labels:
    hdr += [f"{lb}_us", f"{lb}_GB/s", f"{lb}_n"]
hdr += [f"{lb}/{labels[0]}" for lb in labels[1:]] + ["checksums"]
lines = ["\t".join(hdr)]
missing = mismatched = 0
for k in keys:
    rec = [*k]
    us_med = {}
    sums = set()
    for lb in labels:
        got = [rows[k] for l, _, rows in runs if l == lb and k in rows]
        if not got:
            rec += ["-", "-", "0"]
            missing += 1
            continue
        us = statistics.median(g[0] for g in got)
        # GB/s from the median time: the run's own GB/s column is bytes / us, so bytes = GB/s * us
        gbs = statistics.median(g[1] * g[0] for g in got) / us
        us_med[lb] = us
        sums.update(g[2] for g in got)
        rec += [f"{us:.1f}", f"{gbs:.1f}", str(len(got))]
    for lb in labels[1:]:
        rec.append(f"{us_med[labels[0]] / us_med[lb]:.3f}" if lb in us_med and labels[0] in us_med else "-")
    if len(sums) > 1:
        mismatched += 1
    rec.append("same" if len(sums) == 1 else "DIFFER")
    lines.append("\t".join(rec))
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print(f"mmvq_compare: {len(keys)} rows, {missing} label(s) missing a row, {mismatched} row(s) with differing checksums -> {out}")
