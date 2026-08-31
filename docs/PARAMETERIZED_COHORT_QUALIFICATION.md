# Parameterized Virtual Disease Cohort qualification gate

## Purpose

This document records the post-merge real-source qualification gate for the Parameterized Virtual Disease Cohort Engine introduced by PR #19.

The gate does **not** establish clinical validation of Virtual Disease. It qualifies the cohort orchestration and persistence layer against the canonical PWDB source while retaining the existing scientific boundary:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
population interpretation = designed_counterfactual_not_epidemiological
```

## Real-source scope

The qualification workflow acquires and checksum-verifies the exact PWDB artifacts required by Virtual Disease:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

It then performs the following gates against the public merged VascuQuest API.

### Q1 — source age and subject identity

- Confirm the canonical source age states are exactly `25, 35, 45, 55, 65, 75` years.
- Request the qualification interval 45–75 years and require the resolved source-supported ages to be exactly `45, 55, 65, 75`.
- Verify each planned assignment retains the original PWDB canonical subject number.
- Verify the age recorded in each assignment equals the source PWDB age for that subject.

### Q2 — deterministic parameterized planning

For each of the four Virtual Disease v1 conditions, create the same plan twice and require exact equality of:

- content-addressed cohort run ID;
- selected canonical subject IDs;
- assigned disease severities;
- complete per-subject disease specifications;
- recorded rejections and planner metadata.

The planner must create heterogeneous severities inside the requested interval and continue to use the deployed disease transformation as the subject-specific admissibility authority.

### Q3 — real disease execution

Generate three real-source subjects for each condition:

1. carotid stenosis;
2. iliac stenosis;
3. fusiform abdominal aortic aneurysm;
4. large-artery stiffening.

Every subject must execute through the existing Virtual Disease full-network solver and reach periodic convergence.

### Q4 — full 116-segment persistence

For every completed subject, require:

- exactly 116 unique segment IDs;
- finite, strictly increasing final-cycle time coordinate;
- finite axial coordinates;
- finite `A(t,x)`, `Q(t,x)` and `P(t,x)` histories;
- strictly positive lumen area everywhere;
- finite derived cross-sectional mean velocity `U=Q/A`;
- exactly 58 standard materialised Virtual Disease results.

### Q5 — bundle integrity and scientific boundary

Require the public cohort verifier to report:

- `valid = true`;
- `status = COMPLETE`;
- all planned original subject IDs verified in frozen order;
- full-network segment count = 116;
- evidence = `MODELLED`;
- clinical validation = false.

The persistent manifest must continue to state `designed_counterfactual_not_epidemiological`.

### Q6 — completed-checkpoint resume

Re-run every completed cohort with `resume=True` and verify SHA-256 equality of each subject's `subject_manifest.json` and `full_network.npz` before and after resume. A completed subject must therefore be verified and skipped rather than recomputed.

## Machine-readable evidence

The workflow uploads:

```text
parameterized-cohort-qualification.json
```

as the `vascuquest-parameterized-cohort-qualification` GitHub Actions artifact for 90 days.

A passing report qualifies the Parameterized Cohort Engine for reproducible research cohort generation within the existing Virtual Disease model context. It does not convert a modelled cohort into clinical patient data and does not establish epidemiological representativeness or clinical outcome validity.
