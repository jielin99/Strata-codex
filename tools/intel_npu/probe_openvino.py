"""Enumerate OpenVINO devices and optionally execute a tiny graph on each.

This is a hardware smoke check, not Strata inference or a performance benchmark.
No AUTO/HETERO device selection or CPU fallback is requested.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("openvino-report.json"))
    parser.add_argument("--smoke", action="store_true", help="Run a tiny FP32 MatMul; may JIT-compile on the device")
    args = parser.parse_args()
    report = {"scope": "device enumeration and synthetic MatMul only; not Strata integration", "devices": []}
    try:
        import numpy as np
        import openvino as ov
        from openvino import opset13 as ops
        report["openvino_version"] = ov.__version__
        report["numpy_version"] = np.__version__
        core = ov.Core()
        available = list(core.available_devices)
        report["available_devices"] = available
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["next_step"] = "Return this report first; no packages were installed by this tool."
        write_report(args.output, report)
        print(report["error"])
        return 2

    npu_passed = False
    for device in available:
        item = {"requested_device": device}
        report["devices"].append(item)
        try:
            item["full_name"] = str(core.get_property(device, "FULL_DEVICE_NAME"))
        except Exception as exc:
            item["name_error"] = str(exc)
        if args.smoke:
            try:
                # Small, fixed shapes deliberately avoid model-format and MoE routing issues.
                x = (np.sin(np.arange(64 * 64, dtype=np.float32)) * 0.1).reshape(64, 64)
                weight = (np.cos(np.arange(64 * 64, dtype=np.float32)) * 0.1).reshape(64, 64)
                param = ops.parameter([64, 64], np.float32, name="input")
                product = ops.matmul(param, ops.constant(weight), False, False)
                model = ov.Model([product], [param], "intel_npu_smoke")
                start = time.perf_counter()
                compiled = core.compile_model(model, device)
                item["compile_ms"] = round((time.perf_counter() - start) * 1000, 3)
                raw_devices = compiled.get_property("EXECUTION_DEVICES")
                # The NPU plugin returns a plain string ("NPU"); CPU/GPU return a list. Iterating the string split it
                # into characters (['N', 'P', 'U']) and rejected a valid placement.
                if isinstance(raw_devices, str):
                    raw_devices = [raw_devices]
                execution_devices = [str(value) for value in raw_devices]
                item["execution_devices"] = execution_devices
                # Explicit device selection plus reported placement: no automatic fallback.
                if not execution_devices or any(value.split(".")[0] != device.split(".")[0] for value in execution_devices):
                    raise RuntimeError(f"Unexpected execution device: {execution_devices}")
                request = compiled.create_infer_request()
                start = time.perf_counter()
                result = request.infer({0: x})
                actual = np.array(result[compiled.output(0)], copy=True)
                item["first_infer_ms"] = round((time.perf_counter() - start) * 1000, 3)
                reference = x @ weight
                item["max_abs_error"] = float(np.max(np.abs(actual - reference)))
                item["correct"] = bool(np.isfinite(actual).all() and np.allclose(actual, reference, rtol=0.01, atol=0.005))
                item["smoke_passed"] = item["correct"]
                if device.split(".")[0] == "NPU" and item["correct"]:
                    npu_passed = True
            except Exception as exc:
                item["smoke_passed"] = False
                item["error"] = f"{type(exc).__name__}: {exc}"
        write_report(args.output, report)
        print(f"{device}: {item.get('full_name', '?')}; smoke={item.get('smoke_passed', 'not requested')}")
    report["npu_enumerated"] = any(device.split(".")[0] == "NPU" for device in available)
    report["npu_smoke_passed"] = npu_passed if args.smoke else None
    write_report(args.output, report)
    return 0 if (npu_passed if args.smoke else report["npu_enumerated"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
