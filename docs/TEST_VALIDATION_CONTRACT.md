# VascuQuest 1.0 test and validation contract

## 1. Purpose

Testing and validation in VascuQuest are scientific controls, not only software-quality checks. A passing unit test does not automatically validate a scientific claim, and an expensive end-to-end run is not automatically superior evidence when a closed-form/manufactured reference case directly tests the method.

This document defines the v1.0 validation hierarchy and release evidence policy.

## 2. Core principles

1. Validate the claim actually made.
2. Use the least expensive evidence that is scientifically sufficient.
3. Preserve real-source evidence where source fidelity is the claim.
4. Use analytical/manufactured reference cases where mathematical correctness is the claim.
5. Never replace a required real-source gate with mocks merely to save compute.
6. Never require expensive whole-population solver reruns to validate pure post-processing unless the post-processing claim genuinely depends on them.
7. Validation is scope-specific; no certificate may be generalized beyond its stated boundary.
8. Scientific and software regressions are separate concerns and both matter.

## 3. Validation layers

VascuQuest 1.0 uses several complementary validation layers.

### Layer A — unit/contract tests

Fast deterministic tests verify:

- domain-object invariants;
- argument validation;
- subject/cohort alignment;
- units and coordinate requirements;
- explicit failure behavior;
- serialization/reconstruction;
- CLI/API contract behavior;
- deterministic method outputs on small fixtures.

These tests run without downloading large PWDB artifacts.

### Layer B — analytical/manufactured scientific references

Methods with known mathematical behavior are tested against constructed inputs with known answers.

Examples:

- statistics: known sample means/variances, paired differences, regression coefficients, seeded bootstrap/permutation behavior;
- mechanics: pressure-area waveforms with known strain/compliance/distensibility/stiffness relationships;
- Fourier/spectral: exact sinusoids/harmonics with known amplitudes/phases/frequency bins;
- impedance: constructed pressure/flow signals with known ratio;
- wave separation/intensity: manufactured forward/backward components under the declared equations;
- plotting: deterministic figure geometry, layer counts, figure-spec serialization, and legend collision invariants.

For these methods, a manufactured reference is often stronger evidence than an expensive population run because the expected answer is known exactly.

### Layer C — subsystem integration tests

Integration tests verify that the methods consume actual VascuQuest scientific objects rather than only anonymous arrays. They check:

- `ScientificResult`/`Waveform` handling;
- dataset identity preservation;
- subject/cohort context;
- location compatibility;
- evidence/method/provenance propagation;
- portable JSON result loading;
- Python/CLI equivalence at the method boundary.

### Layer D — source/physics qualification evidence

Where the claim depends on external source fidelity or mechanistic solver behavior, dedicated source/physics evidence is required.

This includes:

- canonical PWDB checksum/source validation;
- healthy baseline reconstruction qualification;
- Virtual Disease solver/physics qualification;
- parameterized cohort qualification;
- HEMOSPACE path-reader qualification against the authoritative exporter/storage contract.

These certificates retain their original scope and are not replaced by new v1 analytics tests.

## 4. Preserved core PWDB evidence

The original core release established real-source validation over the canonical artifacts used by the lightweight public core, including subject alignment, geometry inventory, common-site waveform inventory, representative public API reads, and `Q=U*A` reconstruction.

VascuQuest 1.0 preserves that core rather than rewriting it. The v1 analysis program must not invalidate or silently weaken those contracts.

Changes to source readers, canonical schema, quantity/location semantics, acquisition/integrity logic, or core derivation behavior would require renewed source-facing validation appropriate to the change.

## 5. HEMOSPACE path-reader qualification

The HEMOSPACE path reader has status:

```text
QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT
```

The qualification is based on:

- canonical artifact identity/checksum manifest;
- authoritative PWDB exporter logic;
- MATLAB-v7.3/HDF5 representation semantics;
- an executed regression fixture reproducing struct/cell/object-reference storage;
- all four supported path families, including the split-foot case.

The qualification does **not** claim that the v1 build freshly downloaded and scanned every byte of every multi-gigabyte path artifact.

See [`HEMOSPACE_PATH_QUALIFICATION.md`](HEMOSPACE_PATH_QUALIFICATION.md).

## 6. Virtual Disease qualification

Virtual Disease retains its dedicated evidence and qualification documents. New analytics do not reopen or redefine the disease physics.

Validation scopes include, where documented:

- healthy baseline reconstruction metrics/gates;
- disease geometry/physics transforms;
- boundary/junction/loss behavior;
- NumPy/JAX backend behavior within declared qualification evidence;
- solver execution identity;
- parameterized cohort/bundle reproducibility.

All disease outputs remain `MODELLED`; passing solver tests does not constitute clinical validation.

## 7. Statistics qualification

The v1 statistics layer is qualified method-by-method against deterministic reference cases and semantic invariants.

Required tests include, as applicable:

- descriptive mean/std/min/max/count;
- deterministic quantiles;
- seeded bootstrap reproducibility;
- seeded permutation reproducibility;
- paired alignment by canonical subject ID;
- independent-cohort behavior;
- known effect-size calculations;
- normality/variance-test call contracts;
- correlation/partial-correlation reference behavior;
- known linear regression coefficients;
- explicit failure of rank-deficient designs;
- robust-regression convergence on bounded fixtures;
- multiplicity correction properties;
- designed-population warnings for empirical probabilities.

Statistical tests verify implementation correctness, not that every research dataset satisfies the assumptions of the statistical method. Method assumptions remain the researcher's responsibility and must be documented/exposed.

## 8. Vascular mechanics qualification

Mechanics tests use manufactured pressure/area waveforms with known relationships.

Required invariants include:

- compatible dataset/subject/location;
- aligned time coordinates;
- no silent interpolation;
- finite/physically admissible denominators where required;
- correct evidence (`DERIVED`);
- stable method identity and units.

Reference checks cover the implemented v1 metrics:

- area strain;
- diameter strain;
- area compliance;
- area distensibility;
- pressure-area slope;
- Peterson modulus;
- beta stiffness index;
- Bramwell-Hill-type wave speed under its declared assumptions;
- pressure-area loop integral.

This qualification does not convert the subsystem into an FSI solver or validate three-dimensional wall mechanics.

## 9. Spectral/wave qualification

Manufactured signals must test:

- frequency-bin placement;
- harmonic amplitude and phase;
- FFT normalization convention;
- PSD/CSD/coherence behavior;
- transfer function on known input-output pairs;
- pressure-flow impedance magnitude/phase;
- characteristic-impedance summary behavior;
- forward/backward wave decomposition under declared assumptions;
- wave-intensity component consistency;
- STFT dimensions/frequency-time coordinates;
- wavelet transform parameter/shape behavior;
- spectral entropy and harmonic-energy descriptors;
- reflection magnitude behavior.

Additional hard tests:

- reject nonuniform sampling when the method requires uniform sampling;
- reject incompatible time bases;
- require co-location for local pressure-flow methods;
- permit cross-site CSD/coherence/transfer only for the same subject with aligned time coordinates;
- guard zero/near-zero spectral denominators according to method definition.

## 10. Plotting qualification

The plotting layer is validated as a deterministic representation engine, not as a source of scientific values.

Tests must establish:

- correct panel/layer/inset construction;
- preservation of all observations in large-cohort scatter/series layers;
- rasterization does not thin data;
- explicit transformations are represented in the figure specification;
- SVG/PDF/PNG rendering where dependencies support it;
- figure-spec serialization;
- legends are outside the scientific plotting region;
- legends do not collide with axes, tick labels, axis labels, titles, insets, or neighboring panels;
- legend spacing remains compact rather than using an arbitrary large reserved margin.

A rendered figure image is not used as the sole authority for numerical regression; layout geometry/specification tests are preferred when possible.

## 11. CLI validation

CLI tests verify:

- frozen/declared top-level command groups;
- `--version` returns `1.0.0`;
- help surfaces exist for core, disease, HEMOSPACE, stats, mechanics, spectral, and plot groups;
- machine output is parseable and free of decorative contamination;
- usage errors return the appropriate Typer/Click code;
- domain exceptions map to the stable VascuQuest exit codes;
- CLI research commands load native VascuQuest result JSON rather than bypassing scientific metadata.

## 12. Package/dependency validation

Core import/install must work without the optional research/plot/path/JAX extras.

Optional dependency tests verify explicit behavior when capabilities are absent and successful capability import/use when the corresponding extra is installed.

The core dependency set remains NumPy, platformdirs, and Typer. Optional extras must not become accidental unconditional imports.

## 13. GitHub Actions policy

VascuQuest should not spend CI minutes on computationally expensive runs that do not improve the evidence for the changed code.

For v1 analytical/documentation work:

- prefer fast unit/contract/manufactured-reference tests;
- use `[skip ci]` when intentionally avoiding unnecessary workflow runs during staged branch construction;
- do not rerun the full disease solver or download the complete PWDB archive merely because post-processing code changed;
- trigger heavier validation only when the scientific claim actually depends on it.

This is a cost discipline, not permission to skip required evidence.

## 14. Release gate for v1.0

Before release, the candidate must satisfy:

1. package version/CITATION/README/changelog consistency;
2. current documentation consistency;
3. fast core regression;
4. new `analysis`/`stats`/`mechanics`/`spectral`/`plot` tests;
5. CLI surface regression;
6. confirmation that no v1 analytics change modified core PWDB, HEMOSPACE semantics, or qualified Virtual Disease physics;
7. preservation/reference of the existing subsystem qualification evidence;
8. manual review/merge according to repository policy.

A release gate may reuse trustworthy immutable qualification evidence where the qualified subsystem was not changed.

## 15. Interpretation boundary

No passing test suite authorizes claims of:

- clinical diagnosis/prognosis;
- treatment efficacy;
- patient-specific risk;
- epidemiological prevalence;
- patient digital-twin validity;
- three-dimensional CFD/FSI fidelity;
- untested scientific methods.

Validation language must remain as precise as the tests and evidence that support it.
