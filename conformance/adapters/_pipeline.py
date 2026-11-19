"""The stages after `fix_text_layer`, shared by every adapter — one definition, so two engines cannot drift.

`fix_text_layer` itself stays with the adapter that calls it: Chrome's path has a measurement switch
(`CONFORMANCE_NO_JOINERS`) and WeasyPrint's does not, and a switch that moves between modules is a switch that
silently changes production. What is shared is what comes after: the provenance stamp, `postprocess.apply`, and
the outline. E3b's candidate is defined as "the shipping stages, unchanged", and this module is what makes that
claim checkable rather than a copied block.
"""
import os

import pikepdf

from . import case_spec

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(HERE, "features.toml")


def finish(fixed: str, out_pdf: str, case: dict, producer: dict, workdir: str) -> str:
    """`fixed` -> `out_pdf` through the shipping stages. Returns the outline verdict for the producer facts."""
    # Provenance exactly as build.py sets it: the markup hash the build handed the engine. postprocess copies it
    # into XMP (xmpMM:DocumentID) and removes the raw keys, so every case gets its own id.
    stamped = os.path.join(workdir, "stamped.pdf")
    with pikepdf.open(fixed) as pdf:
        pdf.docinfo["/SourceFile"] = f"{case['id']}.html"
        pdf.docinfo["/SourceSHA256"] = producer["markup_sha256"]
        pdf.save(stamped)
    import postprocess
    postprocess.apply(stamped, out_pdf, profile="web", features_path=FEATURES,
                      rendered_sha=producer["markup_sha256"], chrome_version=producer["engine_version"],
                      doc_spec=case_spec.make(case))
    producer["postprocess"] = True
    from .chrome import set_outline                     # one outline writer for every engine
    producer["outline"] = set_outline(out_pdf, case)
    return producer["outline"]
