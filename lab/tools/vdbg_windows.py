"""vdbg_windows: the per-window lines STRATA_VERIFY_DEBUG=1 writes, as tables.
    python vdbg_windows.py <windows.tsv> <by_t.tsv> <segment>=<engine.log> [<segment>=<engine.log> ...]
The engine prints one line per verify window (sycl/src/core/verify.cpp, Verifier::run):
    verify dbg: T=<T> window: since previous window <ms> ms, staging <ms> ms, gpu <ms> ms
windows.tsv gets one row per such line (segment, its line number in that log, T and the three times); by_t.tsv gets,
per segment and for all segments together, per T: the window count, its share, and the median / min / max gpu ms
(with the median staging and since-previous ms). Every other line of the logs is ignored."""
import re
import statistics
import sys

PAT = re.compile(r"verify dbg: T=(\d+) window: since previous window ([0-9.]+) ms, staging ([0-9.]+) ms, gpu ([0-9.]+) ms")
out_w, out_t, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
rows = []
for sp in specs:
    seg, path = sp.split("=", 1)
    with open(path, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            m = PAT.search(line)
            if m:
                rows.append((seg, n, int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))))

with open(out_w, "w", encoding="utf-8", newline="\n") as f:
    f.write("segment\tline\tT\tsince_prev_ms\tstaging_ms\tgpu_ms\n")
    for r in rows:
        f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]:.1f}\t{r[4]:.1f}\t{r[5]:.1f}\n")

segs = [s.split("=", 1)[0] for s in specs]
groups = [(s, [r for r in rows if r[0] == s]) for s in dict.fromkeys(segs)] + [("all", rows)]
with open(out_t, "w", encoding="utf-8", newline="\n") as f:
    f.write("segment\tT\twindows\tshare\tgpu_median_ms\tgpu_min_ms\tgpu_max_ms\tstaging_median_ms\tsince_prev_median_ms\n")
    for seg, rs in groups:
        total = len(rs)
        for t in sorted({r[2] for r in rs}):
            sel = [r for r in rs if r[2] == t]
            g = [r[5] for r in sel]
            f.write(f"{seg}\t{t}\t{len(sel)}\t{len(sel) / total:.3f}\t{statistics.median(g):.1f}\t{min(g):.1f}\t{max(g):.1f}\t"
                    f"{statistics.median(r[4] for r in sel):.1f}\t{statistics.median(r[3] for r in sel):.1f}\n")
print(f"vdbg_windows: {len(rows)} windows from {len(specs)} log(s) -> {out_w}, {out_t}")
