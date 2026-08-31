# Virtual Disease v1

## PR 1 status

This document describes the contract-only first implementation stage of the first-party VascuQuest Virtual Disease subsystem.

PR 1 does **not** simulate disease, alter PWDB haemodynamics, create runtime disease datasets, or expose a disease-generation CLI. It freezes the request semantics that later stages must implement without changing established VascuQuest behaviour.

## Frozen v1 conditions

Exactly four condition identities are available:

- `carotid_stenosis`
- `iliac_stenosis`
- `fusiform_abdominal_aortic_aneurysm`
- `large_artery_stiffening`

The catalogue is intentionally closed for v1. Additional conditions require a later scientific amendment and validation programme.

## Population request contract

A future runtime generation request is represented by:

- number of patients;
- exact PWDB age group in years;
- one frozen disease specification;
- deterministic selection seed.

Eligible subjects are obtained from the active VascuQuest `age` quantity. Subjects are selected without replacement and retain their original PWDB `canonical_subject_id` values.

The contract therefore preserves a direct healthy/diseased pairing such as:

```text
PWDB:3275625 / subject 1458
PWDB-VD:<future-run-id> / subject 1458
```

The runtime disease dataset identity is implemented in a later PR; PR 1 only defines the content-addressed request/run fingerprint used to preserve reproducibility.

## Disease specification contract

Disease specifications contain only causal-intervention parameters. They must never contain output waveforms or prescribed haemodynamic results.

The PR 1 catalogue validates parameter names, scalar types, simple anatomical choices, and structural bounds. These bounds are request-syntax guards, not claims of scientific validation. Executable equations, validated numerical domains, and benchmark qualification are deferred to the disease-physics PR.

## Quantity-status contract

Every future runtime quantity must be classified as exactly one of:

- `UNCHANGED_CAUSAL_INPUT`
- `MODEL_PARAMETER_MODIFIED`
- `RECOMPUTED`
- `DERIVED_FROM_RECOMPUTED`
- `NOT_SUPPORTED`

This metadata is separate from the existing VascuQuest `EvidenceClass`; PR 1 does not alter the evidence model.

## Runtime vector naming

Canonical scientific quantity identities remain unchanged. Disease state qualifies only the runtime/source vector label.

Examples:

```text
pressure       -> P__vd_carotid_stenosis
flow_velocity  -> U__vd_carotid_stenosis
luminal_area   -> A__vd_carotid_stenosis
flow_rate      -> Q__vd_carotid_stenosis
```

A future `ScientificResult` will therefore still identify the canonical quantity as `pressure`, while the disease-qualified storage/source label records the runtime disease condition.

## Deterministic selection

Selection first asks the existing VascuQuest session for the exact age cohort. Eligible subject IDs are ranked with SHA-256 using the request seed, the requested number is chosen without replacement, and the chosen IDs are returned in their original canonical cohort order.

This avoids relying on implementation details of a particular Python pseudo-random generator while retaining reproducible pseudo-random cohort selection.

## Explicit PR 1 non-goals

PR 1 contains no:

- cardiovascular solver;
- disease geometry transformation;
- stenosis pressure-loss equation;
- aneurysm transformation;
- stiffness transformation;
- runtime disease backend;
- generated disease waveform;
- generated disease population;
- public disease CLI command.

Those capabilities remain gated behind the later PRs in the five-PR implementation contract.
