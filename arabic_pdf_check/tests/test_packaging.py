#!/usr/bin/env python3
"""Packaging is a claim: the dependency set is one set, the licence is readable from it, and both licences ship.

Three failures this test exists for:
  · `pyproject.dependencies`/extras and `requirements.txt` drifting into two truths;
  · an AGPL package (PyMuPDF today) reaching the SHIPPED dependency set — a customer who installs the checker
    must never be handed an AGPL obligation they did not ask for;
  · the CC-BY-SA word list shipping in an MIT-declared wheel without its notice.
It builds the wheel with pip (about two seconds, no install) and reads the archive back, so the claim is about
the artifact a user receives, not about the source tree.
"""
import importlib.metadata as md
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

fails = []
# Copyleft is refused in the shipped set — AGPL because network use is the obligation the product cannot pass
# on, and plain GPL because a closed product cannot ship it either (this repository already refused `qalam` for
# being GPL-3). LGPL is a different obligation (relinking) and is explicitly out, as is AGPL inside GPL's arm.
# A name deny-list would be a word list the next package walks past, so the test reads the installed METADATA —
# the licence itself, not the name — and both spells the common forms: `GPLv3`, `GPL-3.0`,
# `GNU General Public License v3.0` all match, `LGPL-2.1` and `GNU Lesser General Public License` do not.
AGPL = re.compile(r"agpl|affero", re.I)
GPL = re.compile(r"(?<![la])(?:\bgpl\b|gpl-?v?[23])"
                 r"|(?<![Ll]esser )(?<![Aa]ffero )general public license", re.I)


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


def licence_of(meta) -> tuple[list[str], str]:
    """ALL the licence statements a distribution carries: (texts, source).

    Every source is read, not the first one that answers: a `License-Expression` of «MIT» can sit above a
    classifier that says something else, and "else" would let the first hide the second. `source` is the list of
    fields that were non-empty, or `"UNKNOWN"` when all three are silent.
    """
    texts, sources = [], []
    expr = (meta.get("License-Expression") or "").strip()
    if expr:
        texts.append(expr)
        sources.append("License-Expression")
    lic = (meta.get("License") or "").strip()
    if lic:
        texts.append(lic)
        sources.append("License")
    cls = [c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
    if cls:
        texts.append(", ".join(cls))
        sources.append("classifier")
    return texts, (", ".join(sources) if sources else "UNKNOWN")


def dist_name(requirement: str) -> str:
    return re.split(r"[\s<>=!~;\[(@]", requirement.strip(), maxsplit=1)[0]


def normalise(name: str) -> str:
    """PEP 503: `pdfminer.six`, `pdfminer_six` and `pdfminer-six` are one distribution, not three scans."""
    return re.sub(r"[-_.]+", "-", name).lower()


def closure(roots: list[str]) -> dict[str, list[str]]:
    """{name: [who required it]} over the INSTALLED metadata — bounded by what is installed, not by the network."""
    seen, why = set(), {}
    queue = [dist_name(r) for r in roots]
    for name in queue:                      # the ROOTS are part of the closure: a licence gate that skips the
        why.setdefault(normalise(name), ["(direct)"])  # packages we choose cannot see the one we added
    while queue:
        name = queue.pop(0)
        key = normalise(name)
        if key in seen:
            continue
        seen.add(key)
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            why.setdefault(key, []).append("not installed here")
            continue
        for req in (dist.requires or []):
            if "extra ==" in req or "extra==" in req:
                continue          # an OPTIONAL requirement of a dependency is not installed by `pip install` of it
            child = dist_name(req)
            why.setdefault(normalise(child), []).append(name)
            queue.append(child)
    return why


with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
    project = tomllib.load(fh)["project"]

req = requirements()
deps = list(project.get("dependencies") or [])
extras = {name: list(spec) for name, spec in (project.get("optional-dependencies") or {}).items()}
flat_extras = [item for spec in extras.values() for item in spec]
check("requirements-are-dependencies-plus-extras", sorted(req) == sorted(deps + flat_extras),
      f"requirements={req} declared={deps + flat_extras}")
check("extras-are-disjoint-from-dependencies", not (set(deps) & set(flat_extras)),
      f"both: {sorted(set(deps) & set(flat_extras))}")
check("license-expression", project.get("license") == "MIT AND CC-BY-SA-4.0", str(project.get("license")))

# The documented install is the shipped set: a README that points a customer at the PRODUCER's list hands them
# an AGPL package they did not ask for, and no test below would notice — the wheel is still clean.
checker_readme = open(os.path.join(REPO, "arabic_pdf_check", "README.md"), encoding="utf-8").read()
check("checker-readme-does-not-install-the-producer-list",
      "pip install -r requirements.txt" not in checker_readme)
check("checker-readme-documents-the-mupdf-extra", ".[mupdf]" in checker_readme)

# The licence claim, read from the INSTALLED metadata of the whole closure, not from a name list. Two rules:
#   · a direct dependency with unreadable licence metadata FAILS — the list is ten lines we own, and an unknown
#     licence there is an unknown obligation in the artifact we ship;
#   · a transitive one WARNS — it is the dependency author's omission, not ours, and it is printed for doc 11.
# A dependency whose metadata says nothing is not a known-good dependency. The override table is the escape
# hatch, and it is pinned to the VERSION: a bump fails again and forces a fresh look at the new metadata.
LICENCE_OVERRIDES: dict[str, tuple[str, str, str]] = {
    # name: (version, SPDX, where it was read)
}
who = closure(deps)
# One distribution, one scan: `who` is keyed by PEP 503, so `Pillow`/`pillow` cannot be two keys, two metadata
# reads, or 21 distributions in a count of 20. The parent lists keep the spelling the requirement used, for the
# message a human reads.
directs = [dist_name(d) for d in deps]
agpl, gpl, unknown, scanned = [], [], [], 0
for name in sorted(who):
    if "not installed here" in who[name] and len(who[name]) == 1:
        continue
    try:
        meta = md.metadata(name)
        version = md.version(name)
    except md.PackageNotFoundError:
        continue
    scanned += 1
    texts, source = licence_of(meta)
    override = LICENCE_OVERRIDES.get(name)
    if source == "UNKNOWN":
        if override and override[0] == version:
            texts, source = [override[1]], f"override ({override[2]})"
        else:
            unknown.append(f"{name} {version}")
    joined = " | ".join(texts)
    if AGPL.search(joined):
        agpl.append(f"{name}: {joined[:60]}")
    elif GPL.search(joined):
        gpl.append(f"{name}: {joined[:60]}")
check("no-agpl-in-the-installed-closure", not agpl, "; ".join(agpl))
check("no-gpl-in-the-installed-closure", not gpl, "; ".join(gpl))
# The expression itself is the gate, so it is proved against the five spellings before it is trusted.
SPELLINGS = {("GPL-3.0", True), ("GPLv3", True), ("GNU General Public License v3.0", True),
             ("LGPL-2.1", False), ("AGPL-3.0", False)}
check("gpl-expression-catches-the-five-spellings",
      all(bool(GPL.search(text)) == want for text, want in SPELLINGS),
      str({text: bool(GPL.search(text)) for text, _ in SPELLINGS}))
check("every-distribution-declares-its-licence", not unknown,
      f"no licence metadata (add a pinned override): {unknown}")
print(f"     licences read for {scanned} installed distribution(s) reachable from {len(directs)} direct "
      f"dependencies, extras excluded")
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
            check("wheel-word-list", "conformance/data/ar_words_wiki50k.txt.gz" in names)
            check("wheel-word-list-baseline", "conformance/data/ar_words_50k.txt.gz" in names)
            check("wheel-word-notice", "conformance/data/LICENSE-ar_words.txt" in names)
            licences = [n for n in names if "/licenses/" in n]
            check("wheel-license-files", any(n.endswith("LICENSE-ar_words.txt") for n in licences)
                  and any(n.endswith("/LICENSE") for n in licences), str(sorted(licences)))
            # The artifact, not the source tree: what a `pip install` of this wheel will pull in.
            meta_name = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
            requires = []
            if meta_name:
                requires = [line.split(":", 1)[1].strip()
                            for line in zf.read(meta_name).decode("utf-8").splitlines()
                            if line.startswith("Requires-Dist:")]
            hard = [r for r in requires if "extra ==" not in r]
            check("wheel-no-agpl-hard-requirement", not any("pymupdf" in r.lower() for r in hard), str(hard))
            check("wheel-extra-declares-mupdf",
                  any("pymupdf" in r.lower() and 'extra == "mupdf"' in r for r in requires), str(requires))

print()
if fails:
    print(f"PACKAGING FAILED — {fails}")
    raise SystemExit(1)
print("PACKAGING PASSED — one dependency set, no AGPL in the shipped closure, both licences inside the wheel")
