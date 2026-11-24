"""The child of `conformance.readers.isolate` — one reader, one file, one JSON result.

It calls the SAME `pages_many`/`text_many` the in-process path uses; it is a boundary, not a second reader.
A Python exception is written as `{"ok": false, "error": ...}`; a segfault writes nothing and the parent
reports the exit code. The result goes to the inherited pipe descriptor the parent opened, NOT to a file:
the reader's text must not touch disk, and a reader that prints to stdout cannot corrupt the protocol.
"""
import json
import os
import sys

from conformance.readers import pages_many, text_many


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    name, path, fd = sys.argv[1], sys.argv[2], int(sys.argv[3])
    try:
        got = pages_many(name, [path])
        if got is None or got[0] is None:
            text = text_many(name, [path])[0]
            payload = {"ok": True, "pages": None, "text": text}
        else:
            payload = {"ok": True, "pages": got[0], "text": "\n".join(got[0])}
    except BaseException as exc:                     # noqa: BLE001 — the child must always write a result
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
