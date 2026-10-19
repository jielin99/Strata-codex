#!/usr/bin/env python3
"""lp_extract: the logprobs replies of lab/plans/13-hc-q8.md as one compact table.

  python lp_extract.py <out.tsv> <segment>=<dir> [<segment>=<dir> ...]

Each <dir> holds lp-<prompt>.json: a non-streamed /v1/chat/completions reply asked with "logprobs": true and
"top_logprobs": 20. sycl/serve/server_intel.py puts the thinking tokens' entries under logprobs.reasoning_content and
the answer's under logprobs.content; both are written, thinking first (the order they were generated in). One row per
generated token: segment, prompt, channel (r = thinking, c = answer), position in the whole sequence, the token, its
bytes, its logprob and the top 20 as a JSON list of [token, bytes, logprob] (JSON-escaped, so tabs and newlines stay in
one cell). Exit 1 when a file is missing or is not such a reply, has no entries, or an entry has fewer than 20
alternatives. Only reformats; the comparison is made on the dev machine.
"""
import json
import os
import sys

PROMPTS = ["g1", "g2", "q0", "q1", "q2"]
TOP = 20


def main():
    out, bad, rows = sys.argv[1], [], []
    for arg in sys.argv[2:]:
        seg, d = arg.split("=", 1)
        for p in PROMPTS:
            path = os.path.join(d, f"lp-{p}.json")
            try:
                with open(path, encoding="utf-8") as f:
                    r = json.load(f)
                ch = r["choices"][0]
                lp = ch["logprobs"]
                seq = [("r", c) for c in lp.get("reasoning_content") or []] + [("c", c) for c in lp.get("content") or []]
            except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
                bad.append(f"{seg} {p}: {type(e).__name__} {e}")
                continue
            if not seq:
                bad.append(f"{seg} {p}: no logprobs")
                continue
            short = 0
            for i, (k, c) in enumerate(seq):
                top = [[t["token"], t.get("bytes"), t["logprob"]] for t in c.get("top_logprobs") or []]
                short += len(top) < TOP
                rows.append("\t".join([seg, p, k, str(i), json.dumps(c["token"], ensure_ascii=False),
                                       json.dumps(c.get("bytes")), repr(c["logprob"]), json.dumps(top, ensure_ascii=False)]))
            if short:
                bad.append(f"{seg} {p}: {short} of {len(seq)} entries with fewer than {TOP} alternatives")
            rows.append("\t".join([seg, p, "end", str(len(seq)), json.dumps(ch.get("finish_reason")), "null", "nan", "[]"]))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("segment\tprompt\tchannel\tpos\ttoken\tbytes\tlogprob\ttop\n" + "".join(r + "\n" for r in rows))
    for b in bad:
        print(b)
    print(f"lp_extract: {len(rows)} rows, {len(bad)} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
