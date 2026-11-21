"""Command line: `check` (blind), `verify` (reference), `manifest` (thresholds and their provenance)."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
THRESHOLDS = os.path.join(HERE, "thresholds.json")


def load_thresholds() -> dict:
    with open(THRESHOLDS, encoding="utf-8") as fh:
        return json.load(fh)


def check_command(a) -> int:
    from . import blind, markdown
    try:
        report = blind.check(a.pdf, load_thresholds())
    except Exception as exc:
        print(f"REFUSED — {type(exc).__name__}: {exc}")
        return 2
    text = markdown.render_blind(report)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(text)
    if not a.out and not a.md:
        print(text)
    else:
        print(f"خطر النسخ: {report['risk']['level']} · الثقة: {report['risk']['confidence']} · "
              f"القرّاء: {', '.join(report['readers'])}")
        if a.out:
            print(f"JSON: {a.out}")
        if a.md:
            print(f"Markdown: {a.md}")
    return 0


def verify_command(a) -> int:
    from conformance import certificate
    from . import markdown
    try:
        truth = open(a.truth, encoding="utf-8-sig").read()   # a BOM is not a character of the text
    except OSError as exc:
        print(f"REFUSED — the truth file cannot be read: {exc}")
        return 2
    try:
        cert = certificate.certify(a.pdf, truth_text=truth, truth_name=os.path.basename(a.truth))
    except (certificate.CertError, RuntimeError) as exc:
        print(f"REFUSED — {exc}")
        return 2
    text = markdown.render_reference(cert)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(cert, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(text)
    if not a.out and not a.md:
        print(text)
    else:
        print(certificate.human_summary(cert))
    return 0 if cert["verdict"] == "PASS" else 1


def manifest_command(a) -> int:
    from conformance.readers import available, declared, limitations
    ok, missing = available()
    payload = {"thresholds": load_thresholds(), "readers": {}, "missing_readers": missing}
    for name, mod in ok.items():
        version = mod.version()
        limits, refused, controls = limitations.usable(name, version)
        held, refused_d, controls_d = declared.usable(name, version)
        payload["readers"][name] = {
            "version": version,
            "limits": [lim["id"] for lim in limits],
            "limits_refused": refused,
            "behaviours": [e["id"] for e in held],
            "behaviours_refused": refused_d,
            "controls": [c.get("detail") for c in controls + controls_d],
        }
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"written: {a.out}")
    else:
        print(text)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="arabic-pdf-check", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="blind: named signals and a risk level, no source text")
    c.add_argument("pdf")
    c.add_argument("-o", "--out", default=None, help="write the JSON report here")
    c.add_argument("--md", default=None, help="write the Arabic Markdown report here (else printed)")
    v = sub.add_parser("verify", help="reference: a certificate/2 against a UTF-8 truth text")
    v.add_argument("pdf")
    v.add_argument("--truth", required=True, help="the UTF-8 text the file must reproduce")
    v.add_argument("-o", "--out", default=None, help="write the certificate JSON here")
    v.add_argument("--md", default=None, help="write the Arabic Markdown certificate here (else printed)")
    m = sub.add_parser("manifest", help="the thresholds, the readers and the controls they rest on")
    m.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return check_command(a)
    if a.cmd == "verify":
        return verify_command(a)
    return manifest_command(a)


if __name__ == "__main__":
    sys.exit(main())
