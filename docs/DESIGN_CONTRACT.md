# VascuQuest Design Contract

**Status:** Approved pre-engineering contract  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical dataset for v1:** Zenodo record `3275625`  
**Core licence decision:** Apache-2.0  
**Purpose:** Establish the binding scientific, data, provenance, licensing, extensibility, and validation rules that must govern the software-engineering design of VascuQuest.

---

## 1. Mission

VascuQuest is a **research explorer and discovery engine for virtual vascular populations**.

Its first supported scientific substrate is the PWDB healthy-ageing dataset deposited at Zenodo record `3275625`. VascuQuest is not intended to be a thin dataset wrapper, plotting utility, file converter, or MATLAB replacement. Its role is to turn a complex virtual-haemodynamics dataset into a coherent, reproducible, extensible research environment through both a Python API and a command-line interface.

The package must enable researchers to:

- interrogate subjects, arterial locations, physiological parameters, haemodynamics, geometry, waveforms, pulse-wave indices, path-resolved signals, and plausibility information;
- derive scientifically valid quantities from source data;
- construct cohorts and controlled virtual experiments;
- discover relationships, regimes, sensitivities, interactions, outliers, counterexamples, phenotypes, and low-dimensional structure;
- apply external scientific models to the population through explicit research-operator interfaces;
- test algorithms against simulation-derived ground truth;
- reproduce every computational result from machine-readable provenance;
- extend the ecosystem with new datasets, derivations, discovery methods, scientific operators, and output backends without modifying the core package.

The defining product test is:

> **Can VascuQuest help a researcher formulate, interrogate, and reproduce scientific questions against a virtual vascular population without requiring direct knowledge of the original Zenodo archive structure or MATLAB implementation?**

---

## 2. Binding Gate Decisions

The following six decisions were explicitly approved and are binding on the software-engineering design unless later superseded by a documented design amendment.

### Gate 1 — Canonical dataset identity

**Decision:** VascuQuest v1 targets **Zenodo record `3275625` only** as its canonical PWDB source dataset.

Rules:

1. VascuQuest must never assume that another PWDB deposit is byte-wise, schema-wise, or scientifically equivalent to `3275625`.
2. Other PWDB releases may be added later only as separately identified and validated dataset backends or versions.
3. Dataset identity must be explicit in provenance and never inferred merely from local filenames.
4. Every supported source dataset must have a machine-readable manifest containing at minimum:
   - dataset family;
   - upstream record identifier;
   - upstream version where known;
   - DOI or persistent identifier;
   - file inventory;
   - checksums;
   - source URLs or retrievable resource identifiers;
   - VascuQuest schema version;
   - compatibility information.

For v1, no other Zenodo record is canonical by implication.

---

### Gate 2 — Data acquisition policy

**Decision:** VascuQuest must use **selective, capability-driven acquisition** from the authoritative source, verify integrity, cache data locally, and support user-registered copies or institutional mirrors.

Rules:

1. VascuQuest must **not re-host the canonical PWDB dataset** as part of the GitHub repository, Python wheel, or official package distribution.
2. The package must not require a full-dataset download for operations that need only a subset of source files.
3. Data acquisition must be lazy at the file or capability level wherever technically feasible.
4. Every downloaded source artifact must be checksum-verified against the supported dataset manifest.
5. VascuQuest must support registration of an existing local copy so users do not download duplicate data.
6. VascuQuest must permit a user or institution to configure an internal mirror while preserving canonical source identity and provenance.
7. Local derived stores, indexes, caches, converted representations, and analysis products are allowed, but they must remain distinguishable from canonical source artifacts.
8. Cache writes should be atomic and robust against partial downloads or interruption.

Conceptually:

```text
VascuQuest code        -> GitHub / PyPI
Canonical PWDB data    -> authoritative Zenodo record
Dataset manifest       -> version-controlled with VascuQuest
Local research store   -> user-controlled cache/index/derived products
Institutional mirror   -> optional user-controlled source
```

---

### Gate 3 — Scientific truth and provenance model

**Decision:** Every exposed or generated scientific quantity must carry one of five formal evidence classes.

#### `SOURCE`

Stored directly in the supported upstream dataset, with no scientific transformation beyond faithful parsing, dimensional representation, or lossless type normalization.

#### `RECONSTRUCTED`

Exactly reconstructable from source quantities through a deterministic identity or definition whose interpretation is not model-dependent. Example: reconstructing flow rate from velocity and luminal area where the upstream model defines `Q = U * A`.

#### `DERIVED`

Calculated mathematically or algorithmically from source data using an explicit method. Examples may include spectra, gradients, transit times, phase measures, morphology metrics, or other reproducible transformations.

#### `INFERRED`

Estimated statistically from a population or cohort. Examples include regression coefficients, cluster assignments, discovered associations, sensitivity estimates, surrogate relationships, or uncertainty intervals.

#### `MODELLED`

Predicted by an external or internal scientific model whose outputs are not contained in the source dataset. Examples include research operators based on external haemodynamic theories.

Rules:

1. Every scientific result must expose its evidence class programmatically.
2. Provenance must include enough information to reconstruct how the result was produced.
3. Provenance must include, where applicable:
   - canonical dataset identity;
   - source file checksums;
   - subject or cohort identifiers;
   - source fields;
   - units;
   - transformations;
   - algorithm name and version;
   - package version;
   - operator/plugin version;
   - parameters and assumptions;
   - citations;
   - output identity or hash where appropriate.
4. A `MODELLED` or `INFERRED` quantity must never be presented as if it were `SOURCE` truth.
5. The CLI and Python API must expose the same provenance model.
6. Research reports generated by VascuQuest must retain this classification.

This evidence model is a core scientific integrity requirement, not optional metadata.

---

### Gate 4 — Canonical scientific schema

**Decision:** VascuQuest must maintain a **separately versioned canonical scientific schema** while preserving all upstream source values unchanged.

Rules:

1. VascuQuest must never silently edit canonical PWDB source files.
2. Upstream naming, metadata, aliases, unit labels, and known documentation inconsistencies must be mapped into a validated semantic layer.
3. The schema must define, where applicable:
   - canonical variable name;
   - physical meaning;
   - canonical unit;
   - dimensionality;
   - expected axes/dimensions;
   - source file and field mapping;
   - valid aliases;
   - allowed missingness;
   - evidence class;
   - known upstream defect or ambiguity;
   - correction rationale;
   - citations or authoritative source references.
4. Known upstream metadata defects must be recorded explicitly rather than silently repaired.
5. The canonical schema must be machine-readable and version-controlled.
6. A schema change that affects scientific interpretation requires an explicit schema-version change and migration/compatibility policy.
7. Source-level values and canonical interpretation must remain separately inspectable by the user.

Example semantic record:

```yaml
source_field: PWs.units.A
source_value: m3
canonical_quantity: luminal_area
canonical_unit: m^2
status: upstream_metadata_defect
resolution: canonicalized_without_modifying_source
```

The source data remain authoritative observations; VascuQuest's schema is authoritative about VascuQuest's interpretation of those observations.

---

### Gate 5 — Licensing and implementation boundary

**Decision:** The VascuQuest core will be licensed under **Apache-2.0**.

Rules:

1. Only source code that is legally compatible with the VascuQuest core licence may be incorporated into the core repository.
2. Upstream scientific ideas, equations, and published methods may be independently implemented where legally appropriate.
3. Incompatible implementations, including GPL or otherwise restrictive code that would alter the licensing obligations of the permissive core, must remain external or be exposed only through clearly separated optional integrations.
4. VascuQuest must not perform line-by-line translations of incompatible upstream MATLAB implementations into the Apache-2.0 core.
5. Independent implementations must be scientifically validated against authoritative definitions, published results, reference outputs, or independent numerical tests where possible.
6. Third-party integrations must retain their own licence notices and dependency boundaries.
7. A machine-readable or documented licence inventory should accompany the project as it matures.
8. The canonical PWDB dataset is not relicensed by VascuQuest; its upstream dataset licence and citation requirements remain independently applicable.

Engineering rule:

> **Scientific definitions may be reimplemented; incompatible source code is not copied into the permissive core.**

---

### Gate 6 — Mandatory empirical ingestion spike

**Decision:** Production data-backend and storage decisions remain provisional until a representative set of real files from Zenodo record `3275625` has been empirically opened, inspected, validated, and benchmarked.

Before freezing the production backend architecture, the spike must exercise at minimum:

1. one representative tabular CSV artifact;
2. one WFDB subject or representative WFDB waveform record;
3. representative geometry data;
4. `pwdb_data.mat` or the principal unified MAT representation;
5. at least one lazy slice from a large MATLAB v7.3/HDF5 path file.

The spike must measure or establish:

- file readability in supported Python environments;
- actual nested structures and axes;
- subject-index alignment;
- waveform dimensions and sample organisation;
- lazy-access feasibility;
- memory footprint for representative access patterns;
- access latency for representative scientific queries;
- behaviour under partial/corrupt/missing artifacts;
- consistency between source representations where overlap exists;
- unit and metadata behaviour;
- candidate indexing/chunking strategies;
- minimum dependencies required for robust access.

Rules:

1. Interfaces may be designed before the spike.
2. Concrete storage, chunking, cache, and internal conversion choices are not final until the spike is complete.
3. Scientifically valuable source data must not be excluded merely because files are large.
4. The architecture must support selective access rather than assuming whole-file memory loading.
5. Any benchmark conclusion must be recorded with hardware/software context and dataset file identity.

---

## 3. Non-Negotiable Architectural Principles

The following principles follow from the audits and are binding constraints on the forthcoming software architecture.

### 3.1 Scientific library first, CLI second

The CLI must be a front end to the same scientific API available to Python users.

Scientific mathematics and research logic must not live exclusively inside command handlers.

```text
Python API <-> shared scientific domain layer <-> CLI
```

A result obtained through the CLI and the equivalent result obtained through Python must share the same implementation path and provenance semantics.

### 3.2 Small stable core, extensible ecosystem

The VascuQuest core should define scientific contracts rather than absorb every future method.

The architecture must make room for extension classes such as:

- dataset backends;
- scientific variables;
- derivations;
- research operators;
- discovery methods;
- metrics;
- exporters;
- visualizers;
- execution accelerators.

Third-party extensions should use normal Python packaging and entry-point mechanisms or another standards-based plugin mechanism selected during engineering design.

### 3.3 Dataset backend independence

PWDB ageing record `3275625` is backend #1, not the permanent world model.

The scientific domain layer must not depend directly on Zenodo URLs, PWDB filenames, MATLAB struct names, or a particular physical storage format.

Future virtual vascular populations should be attachable through validated backend contracts without rewriting the discovery engine.

### 3.4 Research operators are separate from source truth

External theories and algorithms must enter VascuQuest through explicit operator interfaces.

A research operator should be able to declare at minimum:

- required inputs;
- outputs;
- units;
- assumptions;
- admissible or validated domain;
- citations;
- implementation version;
- evidence class (`MODELLED` by default unless a different classification is scientifically justified).

This prevents model projections from being confused with source observations.

### 3.5 Discovery must remain auditable

The discovery engine may search for:

- associations;
- nonlinearities;
- interactions;
- sensitivities;
- clusters;
- outliers;
- counterexamples;
- matched-subject contrasts;
- low-rank structure;
- age-dependent regimes;
- waveform phenotypes;
- failure domains of research operators.

However, it must not present exploratory output as automatically causal, novel, or confirmatory.

Where relevant, discovery results should preserve:

- cohort definition;
- sample size;
- effect size;
- uncertainty;
- multiplicity treatment;
- validation procedure;
- held-out or resampling information;
- evidence class;
- provenance.

### 3.6 Raw source immutability

Canonical source artifacts must be treated as immutable.

All corrections, normalized representations, indexes, caches, conversions, and derived values belong to separate VascuQuest-managed layers.

### 3.7 Reproducibility is a core feature

VascuQuest must be designed so that a scientific analysis can be serialized into a machine-readable provenance record and rerun against the same compatible dataset version.

The exact reproduction mechanism will be selected during engineering design, but reproducibility must not depend on manually transcribing CLI history.

### 3.8 No mandatory cloud dependency

Core research workflows must work locally after required source artifacts have been acquired.

No telemetry, proprietary service, or mandatory user account should be required for scientific computation.

### 3.9 Commercial and academic use are equally valid targets

The architecture should not assume notebook-only academic workflows.

It must support:

- command-line automation;
- Python scripting;
- reproducible pipelines;
- offline environments;
- configurable data locations;
- institutional mirrors;
- third-party/private extensions;
- deterministic provenance.

### 3.10 Performance choices must follow measured access patterns

No data technology is mandated by this contract.

Candidates such as xarray, HDF5/h5py, Zarr, Parquet, Arrow, DuckDB, pandas, Polars, Dask, JAX, PyTorch, or others may be evaluated, but no dependency should enter the mandatory core merely because it is fashionable or potentially useful.

The production architecture must justify each mandatory dependency against real VascuQuest workloads.

---

## 4. Scientific Object Model Requirements

The final object model is not fixed by this contract, but the architecture must represent the following concepts without exposing users to the historical file layout:

- dataset identity and version;
- virtual subject;
- age and subject-level physiological configuration;
- physiological plausibility state;
- arterial segment and arterial topology;
- arterial geometry;
- measurement site;
- arterial path and spatial coordinate;
- waveform;
- signal type, including pressure, velocity, luminal area, PPG, and reconstructable flow where applicable;
- time and sampling metadata;
- haemodynamic parameter;
- pulse-wave index;
- onset/fiducial timing;
- cohort;
- derivation;
- research operator;
- discovery result;
- provenance record.

The model must preserve physical units and scientific semantics.

---

## 5. Core vs Extension Boundary

### Expected core responsibilities

The VascuQuest core should contain capabilities broadly required for scientific work across supported virtual vascular populations:

- dataset identity and manifests;
- acquisition and integrity verification;
- canonical schema;
- source adapters/backends;
- subject/cohort semantics;
- vascular topology and geometry abstractions;
- waveform/path abstractions;
- units and metadata;
- provenance/evidence classes;
- query and selection primitives;
- derivation protocol;
- research-operator protocol;
- discovery-method protocol;
- validation framework;
- plugin discovery;
- public Python API;
- CLI integration framework.

### Expected extension responsibilities

Specialized capabilities should normally live outside the core unless they become sufficiently universal and stable:

- specialised haemodynamic theories;
- fractional-order models;
- wave-intensity packages;
- domain-specific biomarkers;
- advanced machine-learning stacks;
- symbolic regression;
- causal-discovery frameworks;
- GPU/HPC execution layers;
- proprietary commercial algorithms;
- support for additional virtual populations not yet audited.

The architecture must make these extensions first-class rather than second-class hacks.

---

## 6. Validation and Testing Contract

Scientific correctness has priority over feature count.

The engineering design must provide for at least the following validation layers.

### 6.1 Source integrity tests

- manifest/checksum verification;
- corrupted download detection;
- incomplete archive detection;
- safe extraction behaviour;
- deterministic source registration.

### 6.2 Cross-representation tests

Where the upstream dataset exposes equivalent information in multiple representations, tests should compare them numerically where scientifically appropriate, including combinations of:

- MAT;
- CSV;
- WFDB;
- geometry files;
- path-resolved MAT structures.

### 6.3 Schema tests

- canonical units;
- dimensions;
- aliases;
- field mappings;
- known upstream metadata defects;
- missing-value semantics;
- subject/site/path alignment.

### 6.4 Scientific invariant tests

Where guaranteed by the model or exporter, deterministic identities should be tested. Examples may include quantities such as `Q = U * A` where applicable.

### 6.5 Reference-result tests

Independent implementations of published or upstream methods should be checked against reference definitions or outputs where legally and scientifically appropriate.

### 6.6 Provenance tests

Equivalent deterministic workflows should produce compatible provenance records and identify the same source artifacts and algorithm versions.

### 6.7 Plugin contract tests

Third-party extensions should be testable against public protocol conformance suites without access to private VascuQuest internals.

### 6.8 CI fixture policy

Routine continuous integration must use compact, legally redistributable or generated scientific fixtures rather than downloading the full 44+ GB source dataset.

Full-source validation should be separated from lightweight CI and may run as release or scheduled validation infrastructure.

---

## 7. Security and Trust Boundary

VascuQuest is research software but must observe normal software-supply-chain discipline.

Required design considerations:

- verified source downloads;
- safe archive extraction;
- atomic file operations;
- no implicit execution of arbitrary `.py` files as research operators;
- explicit plugin installation as a trust decision;
- no mandatory telemetry;
- no hidden remote computation;
- clear distinction between trusted core and installed third-party extensions.

---

## 8. Naming and Product Identity

The project name is **VascuQuest**.

Preferred identifiers:

```text
Project:       VascuQuest
Repository:    KNOWDYN/VascuQuest
Python import: vascuquest
CLI:           vascuquest
```

Working tagline:

> **Scientific exploration and discovery for virtual vascular populations.**

The name is intentionally broader than PWDB so future validated vascular datasets and research extensions can join the ecosystem without forcing a project rename.

---

## 9. Explicit Non-Goals for Initial Engineering

The first engineering design must not assume that VascuQuest will:

- mirror the canonical PWDB dataset;
- bundle the source dataset in PyPI;
- require users to install MATLAB;
- translate the entire upstream MATLAB codebase;
- include every published cardiovascular algorithm in the core;
- make clinical or diagnostic claims;
- infer human causality automatically from virtual-population associations;
- guarantee scientific novelty from automated discovery;
- require GPU or cluster infrastructure;
- choose a permanent internal storage representation before the empirical ingestion spike;
- support every historical PWDB release in v1.

---

## 10. Entry Criteria for Formal Software-Architecture Design

With this contract approved, VascuQuest may now enter formal software-engineering design.

The following distinction is important:

### Gates closed by this contract

- canonical v1 dataset identity;
- acquisition policy;
- evidence/provenance model;
- canonical schema policy;
- core licence boundary;
- mandatory empirical validation policy.

### Empirical work still required before backend freeze

The ingestion spike defined in Gate 6 must be completed before concrete production storage/backends are treated as final.

Therefore the engineering process may now design:

- package boundaries;
- public protocols;
- domain interfaces;
- plugin system;
- provenance representation;
- manifest/schema structures;
- testing architecture;
- CLI/API relationship;
- extension contracts.

But it must keep specific storage/chunking/backend choices provisional until the ingestion spike reports measured evidence.

---

## 11. Design Amendment Rule

This contract is intentionally stronger than an informal architecture note.

Any future change to one of the six binding gate decisions or the non-negotiable principles must be recorded as a **Design Contract Amendment** containing:

1. the original rule;
2. the proposed replacement;
3. scientific and engineering justification;
4. compatibility impact;
5. migration implications;
6. approval date.

Implementation convenience alone is not sufficient justification for weakening scientific provenance, source integrity, or licensing boundaries.

---

## 12. Approval State

The six pre-engineering decisions have been explicitly selected as follows:

| Gate | Decision |
|---|---|
| Canonical dataset | **A — Zenodo 3275625 only for v1** |
| Acquisition | **B — selective verified acquisition + local registration/mirrors** |
| Scientific truth/provenance | **B — SOURCE / RECONSTRUCTED / DERIVED / INFERRED / MODELLED** |
| Canonical schema | **B — versioned semantic schema; raw source immutable** |
| Licensing | **A — Apache-2.0 permissive core with explicit licence boundaries** |
| Empirical architecture gate | **B — mandatory representative real-data ingestion spike before backend freeze** |

**Decision:** VascuQuest is approved to proceed from discovery/audit into formal software-engineering design under this contract.

---

## 13. Upstream References

Primary source dataset:

- PWDB healthy-ageing dataset, Zenodo record `3275625`: https://zenodo.org/records/3275625

PWDB project and publication ecosystem:

- Project site: https://peterhcharlton.github.io/pwdb/
- Official source repository: https://github.com/peterhcharlton/pwdb
- Charlton PH et al. *Modeling arterial pulse waves in healthy aging: a database for in silico evaluation of hemodynamics and pulse wave indexes.* American Journal of Physiology - Heart and Circulatory Physiology, 2019. DOI: 10.1152/ajpheart.00218.2019

These references explain the scientific source but do not override VascuQuest's explicit dataset-version, schema, provenance, and licensing rules above.
