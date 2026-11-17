We need answer user in Arabic. User asks: "مقعد STRUCTURE: هل التصميم صار أفضل؟ منطق مكرّر، مصدر ثانٍ للرقم نفسه، كود في غير موضعه.
قواعد: نتائج فقط. كل نتيجة: P0-P3 + file:line + لماذا + الحركة + وسم (مثبت/مرجح). اختم بـ'## Not proven'. عربي.
السياق: إصلاح ToUnicode للمسافة (200F→0020) بشرط cmap+عرض، وnajd_spec يعلن VOCALISED_CLAIM=False.
الفرق: ..."

They provide diff. Need evaluate design improved? Find issues: repeated logic, second source for same number, code in wrong place. Need results only. Each result: P0-P3 + file:line + why + action + tag (مثبت/مرجح). End with ## Not proven. Arabic.

We need analyze diff carefully. Need maybe line numbers approximate from diff. Need identify structural problems. They mention context: ToUnicode space repair (200F→0020) conditional cmap+width, and najd_spec declares VOCALISED_CLAIM=False. We need likely review whether design became better. Need produce findings only.

Need inspect diff. Files:
build.py adds shutil.copyfile raw.kept.pdf after chrome. Potential issue: shutil imported? In build.py maybe already? Not in diff. Also keeping raw file maybe debug artifact, not structure. Could be code in wrong place? But likely not main.

docs/reviews/najd-qwen-consult.md new empty doc (only heading). maybe useless.

najd.html adds card about no vocalised claim. OK.

najd_spec.py:
- REF_LABELS changed one label.
- adds VOCALISED_CLAIM=False, REASON.
- fills PAGE_INK calibrated values and PAGE_WORDS, EXPECTED_LINKS=43. This is calibration data in spec. Potential "second source for same number"? There is EXPECTED pages nav etc? PAGE_WORDS maybe duplicate with verify? Hmm.

postprocess.py adds feature_bidi_space. It repairs ToUnicode by regex replacing <200E/F> with <0020>. But context says repair should be conditional cmap+width. This code lacks width condition and doesn't verify glyph is visible space. It blindly replaces any ToUnicode mapping to U+200F/E? It regex (<[0-9A-Fa-f]{4}>\s*)<200[EF]> in CMap. That will replace any code 200E/200F mapped from 4-hex glyph id. Could alter actual RLM/LRM characters if font intentionally maps controls? It doesn't check glyph width. It also uses font.objgen? In pikepdf, font is object maybe .objgen? Actually pikepdf Object has objgen? It may be tuple? font.objgen? If font is Dictionary, has objgen property? likely yes. But potential bug: /Resources may be indirect? page.obj.get returns maybe Object. get("/Font", {}) or {}. In pikepdf, page.obj.get('/Resources') could be indirect dict; .get works? Maybe. But if Resources absent, {} is Python dict; .get('/Font', {}) OK. But if /Font is pikepdf.Array? not likely.

Regex only matches 4-digit source codes. ToUnicode CMaps may have beginbfchar entries with <0001> <200F>, or beginbfrange. Could be src codes not 4-digit? PDF ToUnicode CMap src codes usually 2 or 4 hex digits depending font? Could be <00>? It only replaces if source code 4 hex. Also could be <200f> lower-case? pattern <200[EF]> only uppercase E/F; not lower-case. It decodes latin-1, re.sub. If stream has Unicode? OK.

Potential issue: It modifies ToUnicode for all fonts in page resources, but if font resource is shared across pages, seen avoids duplicates. But only checks page-level /Resources/Font. If fonts in Form XObject resources (e.g., AcroForm appearances?) not reached. But maybe okay.

It prints only if repaired. No gate? Maybe design: feature should be profile/spec gated? It is applied unconditionally in apply after normalise. Context says "بشرط cmap+عرض" (with cmap+width condition). This implementation lacks width. So P1/P0? If it could corrupt real control char mapping. But maybe no visible harm? It changes Unicode of any glyph mapped to 200E/F to space. If a glyph is invisible zero-width control, should not become space; extraction would add spaces. Since condition absent, risky. P1 maybe.

Also code in wrong place: feature_bidi_space in postprocess.py but maybe should be in build or verify? It's postprocessing so okay. But "منطق مكرّر" perhaps in verify_pdf and najd_spec? Need identify duplicated logic. The vocalised gate in verify_pdf now uses NS.VOCALISED_CLAIM and NS.VOCALISED_REASON. But page card in najd.html also states same claim? Or spec has VOCALISED_PAGES and VOCALISED string. There's duplicated normalization? Need think.

User says: "مقعد STRUCTURE: هل التصميم صار أفضل؟ منطق مكرّر، مصدر ثانٍ للرقم نفسه، كود في غير موضعه." They want findings on structure. Perhaps they expect answer with these categories: repeated logic, second source of same number, misplaced code. Need output results only.

Need infer from diff: "منطق مكرّر" maybe feature_bidi_space duplicates verify logic? Or expected links? Let's parse.

"السياق: إصلاح ToUnicode للمسافة (200F→0020) بشرط cmap+عرض، وnajd_spec يعلن VOCALISED_CLAIM=False."

They ask "هل التصميم صار أفضل؟" likely review this diff. Need produce findings only.

Need line numbers. Need exact line numbers in new files? We can derive from diff hunk headers and counts.

build.py: hunk @@ -154,6 +154,9 @@ def print_pdf() -> None: existing lines 154-159? Added lines after assert at line 156? Let's count: In new file line 154 maybe `capture_output=True...`? Hunk says old 154,6 new 154,9. The shown context:
         capture_output=True, text=True, timeout=240,
     )
     assert os.path.exists(TMP_PDF), f"chrome failed: {r.stderr[-400:]}"
+    # Keep what Chrome actually produced...
+    shutil.copyfile(TMP_PDF, os.path.join(TMPDIR, "raw.kept.pdf"))
     print("[2/4] chrome printed:", TMP_PDF)

Assuming first context line new 154, second 155, third 156, added 157-159? Actually new start 154, context lines: 154 capture_output, 155 ), 156 assert, 157 comment, 158 comment, 159 shutil.copyfile, 160 print. So file:line build.py:159 for copyfile. If line