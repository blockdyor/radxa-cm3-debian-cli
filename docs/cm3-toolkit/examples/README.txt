SYNTHETIC FIXTURE OUTPUT - NOT CM3 EVIDENCE

Every file in this directory is generated from invented fixtures, not measured
CM3 observations. Times/run IDs describe fixture processing only. Baseline and
candidate intentionally use the same invented CPU sample with unknown controls;
the comparison is INCONCLUSIVE, not a performance claim. The inspector example
contains explicitly unavailable fields. JSON provenance.synthetic is true in
all four envelopes; the human summary starts with this warning.

Reproduce offline from repository root:
  python3 tools/cm3-toolkit/report.py --baseline docs/cm3-toolkit/examples/SYNTHETIC-baseline.json --candidate docs/cm3-toolkit/examples/SYNTHETIC-candidate.json

Hardware UNTESTED. Gates G0-G7 NOT EVALUATED.
