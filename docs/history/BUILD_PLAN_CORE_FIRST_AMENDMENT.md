# VascuQuest Build Plan — Core-First Amendment

**Status:** Governing amendment to `BUILD_PLAN.md`  
**Approved by user directive:** 2026-08-25  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical dataset:** PWDB Zenodo record `3275625`

This amendment is part of the executable build plan. It preserves every scientific, provenance, integrity, source-identity, testing, and empirical-validation requirement already frozen in the governing contracts. Where this amendment conflicts with sequencing or scope language in `BUILD_PLAN.md`, this amendment governs. All non-conflicting provisions of `BUILD_PLAN.md` remain binding.

## 1. Reason for amendment

The accepted build plan already states that when a required multi-gigabyte canonical artifact cannot be accessed, implementation may progress on all non-path components while path-resolved v1 support remains explicitly unvalidated. However, later definitions of code-complete v1 still make the production path reader mandatory. That creates an execution contradiction: a capability explicitly allowed to remain deferred would nevertheless block completion of the validated core package.

The canonical PWDB source structure supports a clean separation. Scalar metadata, subject configuration, geometry, and common-site waveform access are available through comparatively lightweight canonical artifacts. Dense path-resolved waveforms are a distinct optional source class stored in multi-gigabyte MATLAB v7.3 files and require the existing empirical Tier-3 gate before their production access strategy can be frozen.

This amendment resolves the contradiction without weakening Batch 8.

## 2. Core v1 scope

Core v1 is the operational package scope that may be code-completed and scientifically validated independently of path-resolved waveform support.

Core v1 includes:

- canonical PWDB `3275625` identity and manifest/schema;
- virtual subjects and deterministic cohorts;
- canonical scalar quantities supported by verified lightweight CSV artifacts;
- source-supported vascular geometry;
- validated common-site waveform access through the selected production representation;
- evidence, validity, provenance, integrity, and source-registration/acquisition behavior;
- public Python facade and application services;
- registered plugin protocols and explicit unavailable-component failures;
- only those built-in scientific methods that satisfy their authoritative-definition and validation gates;
- JSON/CSV exporters;
- CLI/API parity for implemented core capabilities;
- package build/install checks and fast CI;
- release validation against the exact canonical artifacts claimed by core v1.

Core v1 does **not** claim dense path-resolved waveform access.

## 3. Optional path-resolved capability

Path-resolved PWDB support is an optional extension to core v1.

It remains governed by the existing Batch 8 and Batch 9 requirements:

1. Batch 8 Tier-3 empirical ingestion must execute against checksum-verified canonical real artifacts, including a bounded read from a real large path MAT file.
2. Batch 8 must record observed hierarchy/indexing, subject/path alignment, memory behavior, repeated-access behavior, reader dependencies, and justified representation tolerances.
3. The production strategy must be selected from `DIRECT`, `INDEXED`, or `CONVERTED` from measured evidence rather than assumption.
4. `path_reader.py` must not be implemented or declared production-ready before Batch 8 passes.
5. Batch 9 may begin only after Batch 8 passes and the selected strategy is reviewed.
6. Core APIs must never silently substitute common-site waveforms for a requested path-resolved waveform.
7. Until Batch 8 and Batch 9 pass, path requests must fail explicitly with a capability/validation-unavailable error.

The inability to execute Batch 8 in one development environment is therefore a limitation of the optional path capability, not permission to weaken the gate and not a blocker for unrelated core completion.

## 4. Revised execution order

The core execution track is now:

```text
Batches 0-7
    -> Batch 10 application services + Python facade
    -> Batch 11 validated built-in scientific components
    -> Batch 12 exporters
    -> Batch 13 CLI
    -> Batch 14 CI/package/README
    -> Batch 15 core-scope release validation
```

The optional path track is parallel and deferred:

```text
Batch 8 real-source Tier-3 ingestion gate
    -> Batch 9 production path reader
    -> path-scope Tier-4/release validation
```

Batch numbering is retained for traceability. Proceeding from Batch 7 to Batch 10 under this amendment is an approved scope transition, not a skipped validation gate. Batch 8 remains mandatory before Batch 9 and before any path-resolved support claim.

The existing maximum of two fully gated batches per user directive and the maximum of three repository files per internal pass remain unchanged.

## 5. Batch 10 gate under core-first scope

Batch 10 remains responsible for the application services, composition root, and stable `DatasetSession` facade.

Its gate is satisfied when documented Python flows for implemented core capabilities route through one coherent facade, including:

- open/status/capabilities/quantities;
- subjects/subject/select;
- canonical scalar `get`;
- source-supported geometry;
- common-site `waveform`;
- method/model/discovery/export/reproduce dispatch semantics.

Operations whose component is not yet installed or implemented must fail clearly rather than being simulated. Path-resolved waveform requests must likewise fail explicitly while Batch 8/9 remain incomplete.

Batch 10 does not require a path reader to close.

## 6. Dependency consequence

The lightweight core must not acquire SciPy, h5py, or WFDB as unconditional runtime dependencies merely because optional source representations exist.

Reader dependencies are introduced only where an implemented and validated production capability requires them. In particular:

- the existing CSV/common-site core path may remain free of MATLAB/HDF5 dependencies;
- WFDB may remain a validation/optional reader dependency unless selected for a shipped production capability;
- h5py becomes a production dependency for path support only if Batch 8 selects a direct HDF5 strategy;
- SciPy is added only for a shipped conventional-MAT capability that actually requires it.

This does not prohibit reasonable reader dependencies; it prevents optional path machinery from inflating the core install before empirical justification.

## 7. Revised definition of code-complete core v1

Core v1 is code-complete when all applicable non-full-data tests pass and the following exist:

- installable package;
- public Python facade;
- canonical manifest/schema;
- evidence/validity/provenance model;
- local registration/acquisition/integrity layer;
- PWDB subject/scalar metadata backend;
- geometry access;
- validated common-site waveform access;
- five plugin protocols/registry;
- only the built-in scientific components actually claimed by the release and fully validated under their method gates;
- JSON/CSV exporters;
- frozen CLI command tree for implemented core capabilities;
- API/CLI parity;
- explicit path-capability-unavailable behavior while Batch 8/9 remain incomplete;
- fast CI/platform checks;
- package build/install tests.

A production `path_reader.py` is **not** a requirement for code-complete core v1. It becomes a requirement only for a release claiming path-resolved capability.

## 8. Revised validation claims

Validation claims are scope-specific.

### Core validation

A release may be declared validated for **core PWDB v1 scope** only when the exact claimed lightweight/core source artifacts, schema mappings, subject alignment, geometry/common-site waveform mappings, scientific methods, provenance/evidence behavior, API/CLI behavior, and applicable release tests pass on the exact release candidate.

### Path-resolved validation

A release must not claim path-resolved PWDB support until Batch 8 and Batch 9 pass and the applicable real-source Tier-3/Tier-4 path validation is recorded for the exact release candidate.

### Full canonical-dataset validation

A release must not be described as fully validated against the complete 44.3 GB canonical dataset while path-resolved artifacts remain outside the executed validation scope.

README, package metadata, CLI status output, and release notes must state the validation scope accurately.

## 9. Batch 15 interpretation

Batch 15 now validates the capabilities claimed by the release candidate rather than forcing unimplemented optional path scope into the core release.

For a core-only release candidate, Tier-4 validation applies to all canonical artifacts required by the core capability set. The release record must explicitly state that path-resolved artifacts were not part of the validated capability set.

If path support has subsequently passed Batch 8 and Batch 9, Batch 15 additionally validates the claimed path artifacts and path semantics before any expanded release claim.

## 10. Non-regression constraints

This amendment does not authorize any of the following:

- weakening source checksum verification;
- replacing path data with common-site data;
- inferring a path reader from exporter source code alone;
- hiding unavailable capabilities;
- changing evidence classes for convenience;
- relaxing provenance requirements;
- inventing scientific equations or tolerances;
- calling synthetic fixtures canonical-source validation;
- claiming full-dataset validation from a core-only validation run.

The scientific and empirical hard gates remain intact.

## 11. Immediate active batch

With this amendment approved, the next active core batch is **Batch 10 — Application services and Python facade**.

Batch 8 remains open on its separate empirical branch and may be completed later when the required canonical path artifact can actually be read. Batch 9 remains unopened until then.
