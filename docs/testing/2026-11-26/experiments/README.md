# Expanded Recognition Experiment

Date: 2026-11-26

## Results
- Baseline recognition: 89% precision, 16% recall.
- Expanded recognition: 98% precision, 99% recall.
- Original geometry tests: 19/19 passed.
- Expanded geometry tests: 17/19 passed.

## Findings
- Expanded rule coverage improved feature recognition.
- Geometry mismatches occurred in chamfer and boss cases.
- Removing either rule or both did not restore all geometry tests.

## Limitations
- Tested on generated CAD models, not actual HP samples.
- Root cause remains unconfirmed.
- Experimental configuration is not ready for production.

## Next Steps
- Investigate geometry mismatches.
- Improve recognition without compromising geometry.
- Retest before merging.
