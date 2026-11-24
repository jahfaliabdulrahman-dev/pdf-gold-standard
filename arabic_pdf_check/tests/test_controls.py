#!/usr/bin/env python3
"""The control cache: check reads it, refresh writes it, a raising control is a one-line refusal.

The measured defect (audit 2026-11-24): every `check` launched Chrome and Swift, cost 3.4 s and left three
temp dirs. The fix is a stored result keyed by (reader, live version, control script SHA, repo fingerprint,
platform, schema); the check path never runs a control. This test drives the three modes with a fake control.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance.readers import controls_runner as cr          # noqa: E402
from conformance.readers import limitations                    # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


entry = {"id": "fake-control", "reader": "mupdf", "control_script": "fake.py",
         "reader_version_measured": "2.1", "claim": "a test"}
controls_dir = os.path.join(REPO, "conformance", "readers", "controls")

with tempfile.TemporaryDirectory(prefix="controls-cache-") as tmp:
    os.environ["ARABIC_PDF_CHECK_CACHE"] = tmp
    real = cr.run_control
    calls = {"n": 0}

    def fake_run(e, d):
        calls["n"] += 1
        return {"reproduces": True, "detail": {"ok": True}}

    cr.run_control = fake_run
    try:
        out = cr.control_data(entry, controls_dir, "mupdf", "2.1", mode="refresh")
        check("refresh:runs", calls["n"] == 1 and out["reproduces"] is True, str(calls))
        files = [f for f in os.listdir(cr.cache_root()) if f.endswith(".json")]
        check("refresh:stored-one", len(files) == 1, str(files))

        # From here on, the live runner must NOT be called by the cached path.
        cr.run_control = lambda e, d: (_ for _ in ()).throw(AssertionError("cached path ran the control"))
        cached = cr.control_data(entry, controls_dir, "mupdf", "2.1", mode="cached")
        check("cached:serves", cached["reproduces"] is True)
        check("cached:no-live", calls["n"] == 1, str(calls))

        # A different live version is a different key: the cache must not serve it.
        try:
            cr.control_data(entry, controls_dir, "mupdf", "9.9", mode="cached")
            check("cached:version-key", False, "served a result for another version")
        except cr.ControlRefused as exc:
            check("cached:version-key", "controls --refresh" in str(exc), str(exc))

        # A raising control in refresh is stored as a refusal; cached then refuses with a line.
        os.environ["ARABIC_PDF_CHECK_CACHE"] = os.path.join(tmp, "refusal")
        cr.run_control = lambda e, d: (_ for _ in ()).throw(cr.ControlRefused("boom"))
        try:
            cr.control_data(entry, controls_dir, "mupdf", "2.1", mode="refresh")
            check("refresh:refusal-raises", False, "no exception")
        except cr.ControlRefused:
            check("refresh:refusal-raises", True)
        try:
            cr.control_data(entry, controls_dir, "mupdf", "2.1", mode="cached")
            check("cached:refusal", False, "served a refusal as a measurement")
        except cr.ControlRefused as exc:
            check("cached:refusal", "does not reproduce" in str(exc) or "controls --refresh" in str(exc),
                  str(exc))

        # A registry whose control raises must refuse by name, not escape as a traceback.
        os.environ["ARABIC_PDF_CHECK_CACHE"] = os.path.join(tmp, "registry")
        cr.run_control = real
        original = limitations.control_data
        limitations.control_data = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            ok, refused, _ = limitations.usable("mupdf", "2.1", mode="live")
            check("registry:one-line", not ok and any("control failed — RuntimeError" in r for r in refused),
                  "; ".join(refused))
        finally:
            limitations.control_data = original
    finally:
        cr.run_control = real

print()
if fails:
    print(f"CONTROLS CACHE FAILED — {fails}")
    raise SystemExit(1)
print("CONTROLS CACHE PASSED — refresh stores, cached serves, a raising control is a one-line refusal")
