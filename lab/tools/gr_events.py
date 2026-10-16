"""gr_events.py: write a copy of the engine's fused_gr.dp.cpp in which fused_gr_read_multi (and the down launcher it
calls) records the sycl::event of every kernel it submits, so lab/tools/gr_events_bench.cpp can read each kernel's
own execution time from a profiling queue. The engine's file is not changed; the copy is compiled in its place.

    python gr_events.py <engine>/sycl/src/kernels/cuda/fused_gr.dp.cpp <out>/fused_gr_events.cpp

From the start of launch_down_v2 (when the file has it and it comes first) or of fused_gr_read_multi to the end of
fused_gr_read_multi, every `st->submit(...)` and `st->parallel_for<...>(...)` call becomes `lab_ev(<the call>)`,
which appends its event to strata::kernels::g_lab_ev (the bench resets g_lab_nev before each read). The script
stops with an error when the file is not laid out as expected, instead of writing a partial patch.
"""
import re
import sys


def wrap_calls(body):
    """Wrap every st->submit( / st->parallel_for< call of `body` in lab_ev( ... )."""
    out, k, n = [], 0, 0
    pat = re.compile(r"st->(submit\(|parallel_for<)")
    while True:
        m = pat.search(body, k)
        if m is None:
            out.append(body[k:])
            return "".join(out), n
        j = m.start()
        q = j
        if m.group(1).startswith("parallel_for"):   # skip the template argument list <...>
            depth = 0
            q = body.index("<", j)
            while True:
                c = body[q]
                depth += (c == "<") - (c == ">")
                q += 1
                if depth == 0:
                    break
        p = body.index("(", q if q > j else j)   # the call's own opening parenthesis
        depth, q = 0, p
        while True:
            c = body[q]
            depth += (c == "(") - (c == ")")
            if depth == 0:
                break
            q += 1
        out.append(body[k:j] + "lab_ev(" + body[j:q + 1] + ")")
        k = q + 1
        n += 1


def main(src_path, out_path):
    s = open(src_path, encoding="utf-8").read()
    i_read = s.find("bool fused_gr_read_multi(const FusedGrArgs* a, int n_tok, float* xn_scratch, void* stream")
    if i_read < 0:
        sys.exit("gr_events.py: fused_gr_read_multi not found")
    i_v2 = s.find("void launch_down_v2(sycl::queue* st, const GrMulti& m)")
    start = i_v2 if 0 <= i_v2 < i_read else i_read
    end = s.find("\n}\n", i_read)
    ns = s.find("namespace strata::kernels {\n")
    if end < 0 or ns < 0 or ns > start:
        sys.exit("gr_events.py: unexpected layout")
    body, n = wrap_calls(s[start:end])
    if n == 0:
        sys.exit("gr_events.py: no launch sites")
    decl = ("sycl::event g_lab_ev[16];   // gr_events.py: the kernels of the last read, in submission order\n"
            "int g_lab_nev = 0;\n"
            "static inline void lab_ev(sycl::event e) { if (g_lab_nev < 16) g_lab_ev[g_lab_nev++] = e; }\n")
    at = ns + len("namespace strata::kernels {\n")
    patched = s[:at] + decl + s[at:start] + body + s[end:]
    open(out_path, "w", encoding="utf-8").write(patched)
    print("gr_events.py: %d launch sites recorded -> %s" % (n, out_path))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
