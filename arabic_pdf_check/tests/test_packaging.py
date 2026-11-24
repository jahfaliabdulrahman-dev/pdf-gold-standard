#!/usr/bin/env python3
"""Packaging is a claim: the dependency list is one list, and both licences ship inside the wheel.

Two failures this test exists for:
  · `pyproject.dependencies` and `requirements.txt` drifting into two truths;
  · the CC-BY-SA word list shipping in an MIT-declared wheel without its notice.
It builds the wheel with pip (about two seconds, no install) and reads the archive back, so the claim is
about the artifact a user receives, not about the source tree.
"""
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def requirements() -> list[str]:
    out = []
    with open(os.path.join(REPO, "requirements.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line)
    return out


with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
    project = tomllib.load(fh)["project"]

req = requirements()
deps = list(project.get("dependencies") or [])
check("dependencies-mirror-requirements", req == deps, f"requirements={req} pyproject={deps}")
check("license-expression", project.get("license") == "MIT AND CC-BY-SA-4.0", str(project.get("license")))
notice = os.path.join(REPO, "conformance", "data", "LICENSE-ar_words.txt")
check("notice-exists", os.path.isfile(notice))
text = open(notice, encoding="utf-8").read()
check("notice-names-both-licences", "CC-BY-SA" in text and "MIT" in text, text[:160])

with tempfile.TemporaryDirectory(prefix="wheel-") as tmp:
    r = subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", tmp],
                       cwd=REPO, capture_output=True, text=True, timeout=300)
    wheels = [f for f in os.listdir(tmp) if f.endswith(".whl")]
    check("wheel-built", r.returncode == 0 and len(wheels) == 1, (r.stderr or r.stdout)[-400:])
    if wheels:
        with zipfile.ZipFile(os.path.join(tmp, wheels[0])) as zf:
            names = set(zf.namelist())
            check("wheel-thresholds", "arabic_pdf_check/thresholds.json" in names)
            check("wheel-word-list", "conformance/data/ar_words_50k.txt.gz" in names)
            check("wheel-word-notice", "conformance/data/LICENSE-ar_words.txt" in names)
            licences = [n for n in names if "/licenses/" in n]
            check("wheel-license-files", any(n.endswith("LICENSE-ar_words.txt") for n in licences)
                  and any(n.endswith("/LICENSE") for n in licences), str(sorted(licences)))

print()
if fails:
    print(f"PACKAGING FAILED — {fails}")
    raise SystemExit(1)
print("PACKAGING PASSED — one dependency list, both licences inside the wheel")
