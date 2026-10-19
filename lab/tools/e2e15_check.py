#!/usr/bin/env python3
"""e2e15_check: the checks and the rules of lab/plans/15-xslm.md sections 5 and 6 over one directory of segments.

  python e2e15_check.py <dir> [no-b]     section 5: which switch the A / B / C segments support adding
  python e2e15_check.py <dir> final      section 6: whether the closing segments 10-D0 / 11-D1 let it be written

<dir> holds xslm-choice.txt (section 4; with `no-b`, when section 4 was not run, it is not read and there is no B group)
and the tables the plan's driver writes:
  timing.tsv           one row per bench request: segment request question generated_tokens decode_tps ttft_s
                       drafts_accepted drafts_offered (sources ...) decode_ms source_decode_ms (as results/14-hc-up/)
  decode-requests.tsv  segment request engine_line windows avg_T tokens_per_window ms_per_window verify draft source
  bench-text.tsv       segment request sha256_16 generated_tokens (sha256 of the request's answer text, first 16 hex)
  greedy.tsv           segment prompt sha256_16 completion_tokens finish_reason cached_tokens (sources ...)
  startup.tsv          segment line text (the engine log's startup lines)
  errors.tsv           segment line text (the engine log lines the plan lists as errors; the header only when none)
Segments are named <n>-<group>: A (daily config), B (+ STRATA_MMVQ_XSLM=<choice>, only when xslm-choice.txt chose one),
C (+ STRATA_SH_STREAM=0), and the closing D0 / D1 (section 6), which section 5's rule leaves out.
Writes e2e-choice.txt (section 5) or final-check.txt (`final`) into <dir>. Every failed check is a problem: the first line
is `problems: <count>`, the exit code is 1 if any, and with a problem nothing is added or written. Only counts, compares
and applies the plan's rules.
"""
import csv
import math
import os
import re
import statistics
import sys
import traceback

ORDER_B = ["1-A", "2-B", "3-C", "4-C", "5-B", "6-A", "7-A", "8-B", "9-C"]
ORDER_NO_B = ["1-A", "2-C", "3-C", "4-A", "5-A", "6-C"]
FINAL = ["10-D0", "11-D1"]
REQUESTS = [str(i) for i in range(1, 10)]
HEX16 = re.compile(r"[0-9a-f]{16}")
KNOWN = {"559a75356eb39f09 a6c46dc05f536ef5": "12 (all-resident path)",
         "553ac32f017ae0be 1c1c19249884638f": "13/14 A (device plan path)"}
SWITCH = {"B": None, "C": "STRATA_SH_STREAM=0"}
COLS = {"timing.tsv": ["segment", "request", "generated_tokens", "decode_ms"],
        "decode-requests.tsv": ["segment", "request", "windows", "avg_T", "tokens_per_window", "verify", "draft"],
        "bench-text.tsv": ["segment", "request", "sha256_16", "generated_tokens"],
        "greedy.tsv": ["segment", "prompt", "sha256_16"],
        "startup.tsv": ["segment", "line", "text"],
        "errors.tsv": ["segment", "line", "text"]}


def fnum(s, lo=0.0, strict=True):
    """a finite number > lo (>= lo when not strict), else None"""
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v < lo or (strict and v == lo):
        return None
    return v


def pint(s):
    try:
        v = int(s)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and str(v) == str(s).strip() else None


def table(d, name, bad):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        bad.append(f"{name}: missing")
        return []
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        rows = list(r)
        fields = r.fieldnames or []
    if any(c not in fields for c in COLS[name]):
        bad.append(f"{name}: columns {fields}, want at least {COLS[name]}")
        return []
    return rows


def per_request(name, rows, order, key, bad):
    """{segment: {key value: row}} for the segments in order; repeated or missing keys are problems"""
    out = {s: {} for s in order}
    for r in rows:
        s = r["segment"]
        if s not in out:
            continue
        k = r[key]
        if k in out[s]:
            bad.append(f"{name}: {s} {key} {k} repeated")
        out[s][k] = r
    return out


def segment_numbers(s, t, dd, x, bad):
    """validated per-request numbers of one segment, or None"""
    ok = True
    win, tok, ms, ver, dra, tpw, avt = {}, 0, 0.0, 0.0, 0.0, 0.0, {}
    for q in REQUESTS:
        tr, dr, xr = t.get(q), dd.get(q), x.get(q)
        if tr is None or dr is None or xr is None:
            bad.append(f"{s} request {q}: a row is missing")
            ok = False
            continue
        g1, g2 = pint(tr["generated_tokens"]), pint(xr["generated_tokens"])
        dms, w = fnum(tr["decode_ms"]), pint(dr["windows"])
        at, tw, v, dr_ms = fnum(dr["avg_T"]), fnum(dr["tokens_per_window"]), fnum(dr["verify"]), fnum(dr["draft"], 0.0, False)
        sha = xr["sha256_16"]
        if None in (g1, g2, dms, w, at, tw, v, dr_ms) or not HEX16.fullmatch(sha or "") or g1 != g2:
            bad.append(f"{s} request {q}: tokens {tr['generated_tokens']!r}/{xr['generated_tokens']!r} (must be equal positive"
                       f" integers), decode_ms {tr['decode_ms']!r}, windows {dr['windows']!r}, avg_T {dr['avg_T']!r},"
                       f" tokens/window {dr['tokens_per_window']!r}, verify {dr['verify']!r}, draft {dr['draft']!r},"
                       f" hash {sha!r}")
            ok = False
            continue
        win[q], avt[q] = w, dr["avg_T"]
        tok += g1
        ms += dms
        ver += v * w
        dra += dr_ms * w
        tpw += tw * w
    if not ok:
        return None
    nw = sum(win.values())
    return {"ms_tok": ms / tok, "verify": ver / nw, "draft": dra / nw, "tpw": tpw / nw, "windows": win, "avg_T": avt,
            "nw": nw}


def load(d, order, allowed, bad):
    tabs = {n: table(d, n, bad) for n in COLS}
    for n in ("timing.tsv", "decode-requests.tsv", "bench-text.tsv", "greedy.tsv", "startup.tsv"):
        have = sorted({r["segment"] for r in tabs[n]})
        if any(s not in have for s in order) or any(s not in allowed for s in have):
            bad.append(f"{n}: segments {have}, want all of {order} and none outside {sorted(allowed)}")
    seg = {}
    t = per_request("timing.tsv", tabs["timing.tsv"], order, "request", bad)
    dd = per_request("decode-requests.tsv", tabs["decode-requests.tsv"], order, "request", bad)
    x = per_request("bench-text.tsv", tabs["bench-text.tsv"], order, "request", bad)
    g = per_request("greedy.tsv", tabs["greedy.tsv"], order, "prompt", bad)
    for s in order:
        for name, m in (("timing.tsv", t), ("decode-requests.tsv", dd), ("bench-text.tsv", x)):
            if sorted(m[s]) != sorted(REQUESTS):
                bad.append(f"{name}: {s} has requests {sorted(m[s])}, want 1-9 once each")
        gh = {k: r["sha256_16"] for k, r in g[s].items()}
        if sorted(gh) != ["g1", "g2"] or not all(HEX16.fullmatch(v or "") for v in gh.values()):
            bad.append(f"greedy.tsv: {s} has {gh}, want one g1 and one g2 hash")
        st = [r["text"] for r in tabs["startup.tsv"] if r["segment"] == s]
        wl = [ln for ln in st if "strata verify: window up to" in ln]
        if len(wl) != 1:
            bad.append(f"startup.tsv: {s} has {len(wl)} 'window up to' lines, want 1")
        seg[s] = {"g": gh, "window": wl[0] if len(wl) == 1 else "",
                  "num": segment_numbers(s, t[s], dd[s], x[s], bad),
                  "text": {q: (x[s][q]["sha256_16"], x[s][q]["generated_tokens"]) for q in x[s]}}
    other = sorted({r["segment"] for r in tabs["errors.tsv"]} - set(allowed))
    if other:
        bad.append(f"errors.tsv: error lines under segments {other}, none outside {sorted(allowed)}")
    errs = [r for r in tabs["errors.tsv"] if r["segment"] in order]
    if errs:
        bad.append(f"errors.tsv: {len(errs)} error lines in {sorted({r['segment'] for r in errs})}")
    return seg


def same_answers(seg, order, bad):
    for k in ("g1", "g2"):
        hs = {seg[s]["g"].get(k) for s in order}
        if len(hs) != 1:
            bad.append(f"greedy {k}: hashes differ across {order}: {sorted(str(h) for h in hs)}")
    for q in REQUESTS:
        hs = {seg[s]["text"].get(q) for s in order}
        if len(hs) != 1:
            bad.append(f"bench request {q}: answer hash / tokens differ across {order}: {sorted(map(str, hs))}")


def section5(d, no_b, out, bad):
    choice = "none" if no_b else None
    p = os.path.join(d, "xslm-choice.txt")
    if not no_b and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[0] == "problems: 0":
            m = next((re.match(r"choice: (\S+)", ln) for ln in lines if ln.startswith("choice: ")), None)
            choice = m.group(1) if m else None
    if choice not in ("none", "4", "8", "16"):
        bad.append(f"xslm-choice.txt: no 'problems: 0' and 'choice: ...' line ({choice!r})")
    order = ORDER_B if choice in ("4", "8", "16") else ORDER_NO_B
    groups = sorted({s.split("-")[1] for s in order})
    seg = load(d, order, set(order) | set(FINAL), bad)
    for s in order:
        if "window up to 4 tokens" not in seg[s]["window"] or "100% VRAM resident" in seg[s]["window"]:
            bad.append(f"startup.tsv: {s} {seg[s]['window']!r}, want 'window up to 4 tokens' without '100% VRAM resident'")
    same_answers(seg, order, bad)
    out.append(f"segments: {' '.join(order)} (10-D0 / 11-D1 left out)")
    out.append(f"greedy: g1 {seg[order[0]]['g'].get('g1')}  g2 {seg[order[0]]['g'].get('g2')}")
    num = {s: seg[s]["num"] for s in order}
    add = []
    if all(num.values()):
        same_win = all(len({(num[s]["windows"][q], num[s]["avg_T"][q]) for s in order}) == 1 for q in REQUESTS)
        out.append(f"windows and avg T per request the same in every segment: {same_win} (recorded only)")
        for q in REQUESTS:
            out.append(f"  request {q}: windows " + " ".join(str(num[s]["windows"][q]) for s in order))
        out.append("")
        out.append("segment  ms/token  verify ms/window  draft ms/window  tokens/window  windows")
        for s in order:
            n = num[s]
            out.append(f"  {s:5s} {n['ms_tok']:9.3f} {n['verify']:12.2f} {n['draft']:14.2f} {n['tpw']:13.3f} {n['nw']:8d}")

        def stats(g, k):
            v = [num[s][k] for s in order if s.split("-")[1] == g]
            m = statistics.mean(v)
            return m, (max(v) - min(v)) / m
        out.append("")
        out.append("group means; range = (max - min) / mean over the group's 3 segments")
        for g in groups:
            m, r = stats(g, "ms_tok")
            mv, rv = stats(g, "verify")
            out.append(f"  {g}: ms/token {m:.3f} (range {r:.4f})  verify ms/window {mv:.2f} (range {rv:.4f})")
        passed = []
        for g in [x for x in groups if x != "A"]:
            ma, ra = stats("A", "ms_tok")
            mx, rx = stats(g, "ms_tok")
            noise, delta = max(ra, rx), mx / ma - 1
            res = delta < -noise
            va, vra = stats("A", "verify")
            vx, vrx = stats(g, "verify")
            out.append(f"  {g} vs A: ms/token {delta:+.4f} against the noise {noise:.4f} -> faster and resolved: {res};"
                       f" verify ms/window {vx / va - 1:+.4f} (noise {max(vra, vrx):.4f}, recorded only)")
            if res:
                passed.append((delta, g))
        if passed:   # B and C were measured apart, not together: at most one, the larger gain
            delta, g = min(passed)
            add = [f"STRATA_MMVQ_XSLM={choice}" if g == "B" else SWITCH[g]]
            if len(passed) > 1:
                out.append(f"  both resolved; only {g} ({delta:+.4f}) goes on: the two were not measured together")
    if bad:
        add = []
    out.insert(0, "add: " + (" ".join(add) if add else "none") +
               "  (the switch of the group resolved faster than A by the most: its mean ms/token below A's by more than the"
               " larger range of the two groups; at most one; none with any problem)")
    return "e2e-choice.txt"


def final(d, out, bad):
    p = os.path.join(d, "e2e-choice.txt")
    add = None
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[0] == "problems: 0" and len(lines) > 1 and lines[1].startswith("add: "):
            add = lines[1][5:].split("  ")[0]
    if add is None:
        add = "none"
        out.append("e2e-choice.txt: no 'problems: 0' / 'add: ...' lines; nothing to write")
    order = FINAL if add != "none" else FINAL[:1]
    seg = load(d, order, set(ORDER_B) | set(ORDER_NO_B) | set(order), bad)
    for s in order:
        if "window up to 6 tokens" not in seg[s]["window"]:   # the daily run: prompt lookup on
            bad.append(f"startup.tsv: {s} {seg[s]['window']!r}, want 'window up to 6 tokens'")
        if seg[s]["num"] is None:
            continue
        g = f"{seg[s]['g'].get('g1')} {seg[s]['g'].get('g2')}"
        out.append(f"{s}: ms/token {seg[s]['num']['ms_tok']:.3f}, windows {seg[s]['num']['nw']}, all resident"
                   f" {'100% VRAM resident' in seg[s]['window']}, greedy {g} = {KNOWN.get(g, 'neither 12 nor 13/14 A')}")
    if add != "none":
        same_answers(seg, order, bad)
    write = add != "none" and not bad
    out.insert(0, f"write: {add if write else 'none'}  (e2e-choice.txt's switch, when 11-D1 (with it) ran clean and gave"
                  " 10-D0's greedy and bench answers; none with any problem)")
    return "final-check.txt"


def main():
    d = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else ""
    out, bad = [], []
    name = "final-check.txt" if mode == "final" else "e2e-choice.txt"
    try:
        if mode not in ("", "no-b", "final"):
            raise ValueError(f"unknown mode {mode!r}")
        name = final(d, out, bad) if mode == "final" else section5(d, mode == "no-b", out, bad)
    except Exception:   # a failed run must still leave a fresh file that says so
        bad.append("exception: " + traceback.format_exc().strip().replace("\n", " | "))
        out[:] = ["write: none" if mode == "final" else "add: none"]
    out.insert(0, f"problems: {len(bad)}" + "".join("\n  " + b for b in bad))
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
