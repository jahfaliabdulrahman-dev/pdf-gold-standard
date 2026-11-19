"""The public conformance gate — a gate that does not need to know the document.

The gate in `scripts/verify_pdf.py` is calibrated: every expected number in it came from four documents
this repository builds. It is the right gate for those documents and it is blind to any other file — a
file `render_document` (Path F) produces, a file a customer brings. This package is the other half:

  corpus/     cases described in a neutral JSON schema, and `truth(case)` derived from the case alone
  adapters/   one per engine: case -> the engine's source -> PDF (the installed build is chrome + our stages)
  readers/    the declared reader matrix, each with its version, plus the measured limits and their controls
  checks/     the general checks: metrics, structure, outline, fonts, veraPDF, model boundary
  certificate.py + schema/   a per-file certificate whose verdict is recomputed, never trusted

Nothing here imports `nav_spec`, `report_spec`, `najd_spec`, `gate_policy` or any calibrated constant. What
it does share with the pipeline is the *general* machinery: `pdfops` (what paints, where text lands, the
declared model) and `scripts/verapdf_json.py` (the validator's report reader). One implementation, two
consumers — the alternative is two readers that drift.

Vocabulary that the code keeps distinct, because conflating them is how a gate lies:
  truth      the text the case declares, in logical (reading) order, from the case file only
  output     what a named reader returns for a named file
  metric     a number comparing output to truth under one documented normalization
  defect     a countable property of the output that no normalization may hide (Presentation Forms, PUA,
             U+FFFD, bidi controls, tatweel the source does not carry)
  limit      a defect the *reader* has, proven by a control file the reader itself produced
"""
