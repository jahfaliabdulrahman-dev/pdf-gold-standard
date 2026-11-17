# استشارة Qwen — أصل المقطع

HarfBuzz **always** outputs glyphs in visual left-to-right order; paragraph direction does not change this. The `direction` flag affects shaping only.

The negative origin you see is a PDFium layout artifact: for an RTL run embedded in an LTR paragraph, `CPVT_Word` positions the run by its **left** edge, but the internal `x_start` values are still accumulated from the run's **right** edge (the natural RTL origin). Subtracting them double-counts the width.

**Safe approach:** record the run's left edge as assigned by the line-layout pass (`CPVT_Line` / word placement) and treat that as the origin. Do not back-compute it from HarfBuzz cluster offsets; use cluster data only for intra-run glyph positioning relative to that recorded edge.
