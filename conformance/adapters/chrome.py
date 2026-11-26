"""case -> HTML -> Chrome for Testing -> (fix_text_layer -> postprocess -> outline).

`engine="chrome"` is the installed build: the same three stages the four documents go through, with the case
spec standing in for `nav_spec`. `engine="chrome-raw"` stops after Chrome and exists only to price what the
post-processing is worth (E's S6) — it is not a candidate.

The outline is ours: Chrome's print output carries no /Outlines, and `build.py` has always set it from the
document's spec. For a case it is derived from the case's headings, and each heading's page is read from the
PDF's own structure tree (`/Pg` of the H-element), never from a text search — a shaped Arabic string is not
a reliable search key, and a wrong outline page would be a silent lie. If the tree does not carry one
H-element per heading, in order, the build refuses: that is a real finding about the engine, not something
to paper over.
"""
import contextlib
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

import pikepdf
import pymupdf as fitz

import chrome_pin

from . import case_spec, fonts, html

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(PROJ, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(PROJ, "scripts"))     # fix_text_layer lives with the pipeline
FEATURES = os.path.join(HERE, "features.toml")
HEADING_TAGS = {f"/H{i}": i for i in range(1, 7)}


class BuildError(RuntimeError):
    """The engine did not produce the file the case asks for — refused by name, never published."""


def chrome_bin() -> tuple[str, str]:
    """CHROME_PATH and only CHROME_PATH, at the pinned version (the pipeline's own rule)."""
    path = os.environ.get("CHROME_PATH", "")
    if not path or not os.path.exists(path):
        raise BuildError(f"CHROME_PATH is not set: point it at Chrome for Testing {chrome_pin.CHROME_VERSION}")
    got = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
    version = got.split()[-1] if got else ""
    if version != chrome_pin.CHROME_VERSION:
        raise BuildError(f"CHROME_PATH runs «{got or 'an unknown version'}», pinned to {chrome_pin.CHROME_VERSION}")
    return path, version


@contextlib.contextmanager
def _patch(module, name: str, value):
    """Set a module attribute for the duration of a build (the joiner A/B only)."""
    old = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, old)


def launch_args() -> list[str]:
    """The renderer's flags, with the one declared environment exception.

    On the hosted Ubuntu runner Chrome aborts before printing (measured 2026-11-25: `num-invoice-latn` →
    crashpad stack, exit 1) because the runner does not grant unprivileged user namespaces, so Chrome's SUID
    zygote sandbox cannot start. `--no-sandbox` is a real loss of isolation, so it is granted ONLY on Linux
    under `CI` — an ephemeral machine rendering a case this repository wrote — and never on a developer's
    machine. `--disable-dev-shm-usage` covers the runner's small /dev/shm, which crashes the renderer the same
    way. `PDF_GOLD_CHROME_ARGS` is the escape hatch for a one-off run, and it is additive.
    """
    args = ["--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
            "--virtual-time-budget=20000"]
    if sys.platform.startswith("linux") and os.environ.get("CI"):
        args += ["--no-sandbox", "--disable-dev-shm-usage"]
    return args + os.environ.get("PDF_GOLD_CHROME_ARGS", "").split()


def render_case(case: dict, out_pdf: str, engine: str = "chrome") -> dict:
    """Build one case. Returns the producer facts the certificate needs (no timings, no paths)."""
    if engine not in ("chrome", "chrome-raw"):
        raise BuildError(f"engine {engine!r} is not built by this adapter")
    fonts.path(case["font"])                       # refuses a missing/wrong font before Chrome starts
    chrome, version = chrome_bin()
    markup = html.render(case)
    work = tempfile.mkdtemp(prefix="conf-case-")
    try:
        src = os.path.join(work, "case.html")
        raw = os.path.join(work, "raw.pdf")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(markup)
        r = subprocess.run([chrome, *launch_args(), f"--user-data-dir={os.path.join(work, 'profile')}",
                            f"--print-to-pdf={raw}", "file://" + src],
                           capture_output=True, text=True, timeout=240)
        if not os.path.exists(raw) or os.path.getsize(raw) == 0:
            raise BuildError(f"chrome produced no file for {case['id']}: {(r.stderr or r.stdout)[-300:]}")
        producer = {"engine": engine, "engine_version": version, "postprocess": False,
                    "markup_sha256": hashlib.sha256(markup.encode("utf-8")).hexdigest()}
        if engine == "chrome-raw":
            shutil.copyfile(raw, out_pdf)
            producer["outline"] = "none"
            return producer
        from fix_text_layer import process as fix_text_layer       # scripts/ is on sys.path via cli.py
        fixed = os.path.join(work, "fixed.pdf")
        # `CONFORMANCE_NO_JOINERS=1` measures what the invisible U+200B/U+2060 cost: the review asked for an
        # A/B, not a preference. Nothing in the shipping pipeline reads this — it is the measurement switch, and
        # the flag exists in the adapter (never in `fix_text_layer`), so production behaviour cannot drift by it.
        if os.environ.get("CONFORMANCE_NO_JOINERS") == "1":
            import contextlib
            import fix_text_layer as _ftl
            with contextlib.ExitStack() as stack:
                stack.enter_context(_patch(_ftl, "WJ", ""))
                stack.enter_context(_patch(_ftl, "GAP_JOINER", ""))
                fix_text_layer(raw, fixed, strict_widths=True)
        else:
            fix_text_layer(raw, fixed, strict_widths=True)
        # Provenance exactly as build.py sets it: the markup hash the build handed the engine. postprocess
        # copies it into XMP (xmpMM:DocumentID) and removes the raw keys, so every case gets its own id.
        stamped = os.path.join(work, "stamped.pdf")
        with pikepdf.open(fixed) as pdf:
            pdf.docinfo["/SourceFile"] = f"{case['id']}.html"
            pdf.docinfo["/SourceSHA256"] = producer["markup_sha256"]
            pdf.save(stamped)
        import postprocess
        postprocess.apply(stamped, out_pdf, profile="web", features_path=FEATURES,
                          rendered_sha=producer["markup_sha256"], chrome_version=version,
                          doc_spec=case_spec.make(case))
        producer["postprocess"] = True
        producer["outline"] = set_outline(out_pdf, case)
        return producer
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _children(node):
    """The /K children of a structure element: an array, one dictionary, or an MCID integer (a leaf)."""
    k = node.get("/K") if hasattr(node, "get") else None
    if k is None:
        return []
    if isinstance(k, pikepdf.Array):
        return list(k)
    if isinstance(k, pikepdf.Dictionary):
        return [k]
    return []                                   # an MCID integer: the leaf itself, no structure below it


def _first_page(node, inherited=None):
    """The page of a structure element: its own /Pg, an ancestor's, or the first one under it.

    Measured on CfT 157 + our postprocess: an /H1 carries no /Pg at all — the page sits on the /NonStruct
    child that holds the MCID. Reading only the element would report «no page» for every heading.
    """
    if not hasattr(node, "get"):
        return inherited
    ref = node.get("/Pg") or inherited
    if ref is not None:
        return ref
    for child in _children(node):
        got = _first_page(child, ref)
        if got is not None:
            return got
    return None


def _heading_pages(pdf_path: str) -> list[tuple[int, int | None]]:
    """(level, page index) for every H1–H6 element, in structure-tree order (0-based pages)."""
    seen: list[tuple[int, int | None]] = []
    with pikepdf.open(pdf_path) as pdf:
        root = pdf.Root.get("/StructTreeRoot")
        if root is None:
            raise BuildError("no /StructTreeRoot: the engine did not tag the document")
        page_of = {page.objgen: i for i, page in enumerate(pdf.pages)}

        def walk(node, depth=0):
            if depth > 40 or node is None:
                return
            if isinstance(node, pikepdf.Array):
                for child in node:
                    walk(child, depth)
                return
            try:
                tag = str(node.get("/S"))
            except Exception:
                return
            if tag in HEADING_TAGS:
                ref = _first_page(node)
                seen.append((HEADING_TAGS[tag], page_of.get(ref.objgen) if ref is not None else None))
            for child in _children(node):
                walk(child, depth + 1)

        walk(root.get("/K"))
    return seen


def set_outline(pdf_path: str, case: dict) -> str:
    """Write the case's headings as the document outline; refuse if the tree does not carry them in order."""
    want = [(b["level"], b["text"]) for b in case["blocks"] if b["type"] == "heading"]
    if not want:
        return "none (no headings)"
    got = _heading_pages(pdf_path)
    levels = [lvl for lvl, _ in got]
    pages = [p for _, p in got]
    if levels != [lvl for lvl, _ in want] or any(p is None for p in pages):
        raise BuildError(f"{case['id']}: the structure tree carries headings {levels} at pages "
                         f"{pages}, the case declares {[lvl for lvl, _ in want]}")
    toc = [[lvl, text, int(page) + 1] for (lvl, text), page in zip(want, pages)]
    doc = fitz.open(pdf_path)
    doc.set_toc(toc)
    tmp = pdf_path + ".toc.pdf"
    doc.save(tmp, deflate=True, garbage=3)
    doc.close()
    os.replace(tmp, pdf_path)
    return f"{len(toc)} entries"


def text_layer_sha256(pdf_path: str) -> str:
    """sha256 of what PDFium reads — the determinism question that survives /CreationDate drift."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_path)
    h = hashlib.sha256()
    for page in doc:
        h.update(page.get_textpage().get_text_range().encode("utf-8"))
    return h.hexdigest()
