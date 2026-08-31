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

The qualification uses the exact PWDB artifacts required by Virtual Disease:

- `pwdb_model_configs.csv`;
- `geo.zip`;
- `PWs_csv.zip`.

It applies the following gates against the public VascuQuest cohort surface.

### Q1 — source age and subject identity

- Confirm the source-supported PWDB age states used by the request are `45, 55, 65, 75` years for the 45–75 qualification interval.
- Verify each planned assignment retains the original PWDB canonical subject number.
- Verify the age recorded in each assignment equals the canonical source age for that subject.

### Q2 — deterministic parameterized planning

For every Virtual Disease v1 condition, create each qualification plan twice and require exact equality of run identity, subject selection, severity assignments, per-subject disease specifications, rejections and planner metadata.

### Q3 — progressive real disease execution

The preferred manual route is `notebooks/parameterized_cohort_qualification_colab.ipynb`.

It executes:

1. a smoke gate of **1 subject × 4 disease conditions**;
2. only after all four smoke cases pass, a full gate of **3 subjects × 4 disease conditions**.

The canonical conditions are carotid stenosis, iliac stenosis, fusiform abdominal aortic aneurysm and large-artery stiffening.

Every completed subject is persisted to Google Drive and verified immediately before the next subject is accepted.

### Q4 — full 116-segment persistence

For every completed subject require exactly 116 unique segments, a finite increasing final-cycle time coordinate, finite axial coordinates, finite `A(t,x)`, `Q(t,x)` and `P(t,x)`, positive lumen area, finite `U=Q/A`, and exactly 58 standard materialised Virtual Disease results.

### Q5 — bundle integrity and scientific boundary

Require `valid = true`, a complete frozen subject identity/order at phase completion, full-network segment count 116, `MODELLED` evidence, `clinical_validation = false`, and `designed_counterfactual_not_epidemiological` population interpretation.

### Q6 — completed-checkpoint resume

Re-run each completed cohort with native `resume` and require SHA-256 equality of each subject's `subject_manifest.json` and `full_network.npz` before and after resume.

## Execution routes

### Preferred: Google Colab manual qualification

Open:

```text
notebooks/parameterized_cohort_qualification_colab.ipynb
```

The notebook:

- clones the PR #20 qualification branch and records the exact commit;
- mounts Google Drive;
- checksum-verifies canonical PWDB artifacts and stages them to Colab local SSD;
- persists subject bundles and progress JSON to Drive;
- verifies each subject immediately on completion;
- blocks the 3-subject phase until all four 1-subject smoke cases pass;
- writes the final durable report to:

```text
MyDrive/VascuQuest/parameterized_cohort_qualification/parameterized-cohort-qualification.json
```

### Optional: GitHub Actions full gate

`.github/workflows/parameterized-cohort-release-validation.yml` is deliberately `workflow_dispatch`-only because the full 12-subject numerical qualification is too expensive and opaque for an automatic pull-request gate.

The original reusable Python full-data harness remains at:

```text
tests/full_data/parameterized_cohort_release_validation.py
```

The checkpointed Colab/manual runner is:

```text
tests/full_data/parameterized_cohort_colab_validation.py
```

A passing report qualifies the Parameterized Cohort Engine for reproducible research cohort generation within the current Virtual Disease model context. It does not establish epidemiological representativeness, clinical outcome validity or patient-specific clinical prediction.
