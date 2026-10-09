# Scientific audit changes — 2026-10-09

## Behavior

Enforce solver-specific spatial biomarker admission at the service boundary. Only named rigid-pipe shear outputs are admitted with pipe-only scope; reduced/unknown backends cannot return spatial biomarkers merely by declaring checked status.

## Scope and remaining evidence

No patient CFD/FSI backend is qualified. Eligibility matches known biomarker names/kinds; opaque artifacts and new names require review. Pipe verification does not imply intracardiac physiological validity.

## Implementation

- `src/cardiflow/eligibility.py`
- `tests/test_biomarker_eligibility.py`
- `src/cardiflow/service.py`

## Verification

Regression tests accompany the changes. Repository test results are recorded in the audit completion report and draft pull request. Software regression checks do not establish numerical, biological, transport or clinical validity.
