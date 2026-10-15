#!/usr/bin/env python3
"""List every tensor of local GGUF files: file, name, type, shape, elements, stored bytes.

Reuses tools/quantscope.py's reader pieces, but keeps the shape (quantscope drops it).
The stored bytes are offset differences, so they include alignment padding.

    python lab/tools/gguf_tensors.py OUT.tsv FILE_OR_DIR [FILE_OR_DIR ...]

Also writes OUT.meta.json with the scalar metadata (arrays are summarized by type and length).
Only file names, never directories, go into the output.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import quantscope as qs  # noqa: E402


def read(src: "qs.Source"):
    r = qs.Buffered(src)
    if r.take(4) != b"GGUF":
        raise ValueError(f"{src.name}: not a GGUF file")
    version = r.u32()
    n_tensors, n_kv = r.u64(), r.u64()
    meta = {}
    for _ in range(n_kv):
        key = r.string()
        meta[key] = qs.gguf_value(r, r.u32())
    tensors = []
    for _ in range(n_tensors):
        name = r.string()
        dims = [r.u64() for _ in range(r.u32())]
        ttype, offset = r.u32(), r.u64()
        count = 1
        for d in dims:
            count *= d
        tensors.append({"name": name, "type": qs.GGML_TYPES.get(ttype, f"type#{ttype}"), "dims": dims,
                        "elements": count, "offset": offset})
    align = int(meta.get("general.alignment") or 32)
    data_start = (r.pos + align - 1) // align * align
    order = sorted(tensors, key=lambda t: t["offset"])
    for a, b in zip(order, order[1:] + [None]):
        end = b["offset"] if b else src.size - data_start
        a["bytes"] = end - a["offset"]
    return version, meta, tensors


def small(v):
    if isinstance(v, list):
        kinds = sorted({type(x).__name__ for x in v})
        return {"array_of": kinds, "len": len(v)} if len(v) > 16 else v
    if isinstance(v, (bytes, bytearray)):
        return {"bytes": len(v)}
    return v


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out = sys.argv[1]
    files = []
    for spec in sys.argv[2:]:
        files += [f for f in qs.resolve(spec) if f.name.endswith(".gguf")]
    if not files:
        print("no .gguf files found")
        return 1
    metas = {}
    with open(out, "w", encoding="utf-8", newline="\n") as fo:
        fo.write("file\tname\ttype\tdims\telements\tbytes\n")
        for f in files:
            base = os.path.basename(f.name)
            version, meta, tensors = read(f)
            metas[base] = {"gguf_version": version, "file_bytes": f.size, "n_tensors": len(tensors),
                           "meta": {k: small(v) for k, v in meta.items()}}
            for t in tensors:
                fo.write(f"{base}\t{t['name']}\t{t['type']}\t{'x'.join(map(str, t['dims']))}\t"
                         f"{t['elements']}\t{t['bytes']}\n")
            print(f"{base}: {len(tensors)} tensors, {f.size / 2**30:.2f} GiB")
    with open(os.path.splitext(out)[0] + ".meta.json", "w", encoding="utf-8") as fm:
        json.dump(metas, fm, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
