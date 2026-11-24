// PDFKit text extraction, one process for many files.
//
// Preview and every macOS-native viewer read with PDFKit, so it is a tier-1 reader: `PDFDocument.string`
// is what a user's copy-paste goes through. One Swift compile per batch keeps 54 cases under two seconds;
// a process per file would cost more than the build itself.

import Foundation
import PDFKit

let v = ProcessInfo.processInfo.operatingSystemVersion
let stamp = "PDFKit \(v.majorVersion).\(v.minorVersion).\(v.patchVersion)"

var texts: [String: String] = [:]
var pages: [String: [String]] = [:]
for path in CommandLine.arguments.dropFirst() {
    if let doc = PDFDocument(url: URL(fileURLWithPath: path)) {
        texts[path] = doc.string ?? ""
        // The same reading, page by page: a checker that names a page must not invent one.
        pages[path] = (0..<doc.pageCount).map { doc.page(at: $0)?.string ?? "" }
    } else {
        texts[path] = ""          // unreadable: an empty string is a measurement, not a crash
        pages[path] = []
    }
}

let payload: [String: Any] = ["version": stamp, "texts": texts, "pages": pages]
let data = try JSONSerialization.data(withJSONObject: payload, options: [])
FileHandle.standardOutput.write(data)
