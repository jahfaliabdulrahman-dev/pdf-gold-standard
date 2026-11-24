"""The child of `conformance.readers.isolate` — one reader, one file, one JSON result.

It calls the SAME `pages_many`/`text_many` the in-process path uses; it is a boundary, not a second reader.
A Python exception is written as `{"ok": false, "error": ...}`; a segfault writes nothing and the parent
reports the exit code. Nothing is read from stdin and nothing is printed on stdout: the result goes to the
path the parent named, so a reader that prints to stdout cannot corrupt the protocol.
"""
import json
import sys

from conformance.readers import load


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    name, path, out_path = sys.argv[1:4]
    try:
        mod = load(name)
        got = mod.pages_many([path]) if hasattr(mod, "pages_many") else None
        if got is None or got[0] is None:
            text = mod.text_many([path])[0] if hasattr(mod, "text_many") else mod.text(path)
            payload = {"ok": True, "pages": None, "text": text}
        else:
            payload = {"ok": True, "pages": got[0], "text": "\n".join(got[0])}
    except BaseException as exc:                     # noqa: BLE001 — the child must always write a result
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
