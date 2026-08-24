# VascuQuest Test and Validation Contract

**Status:** Test, scientific-validation, and release-gate contract for implementation  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`, `SCIENTIFIC_MODEL.md`, `API_PLUGIN_CONTRACT.md`, `CLI_CONTRACT.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Define the minimum test architecture, fixtures, scientific validation rules, tolerance policy, CI/release split, and acceptance gates required to make VascuQuest scientifically trustworthy without making routine development depend on the full 44.3 GB dataset.

---

## 1. Objective

VascuQuest is research software. A passing test suite must establish more than that functions execute: it must establish that source identity, scientific meaning, units, evidence class, provenance, selection semantics, plugin boundaries, and CLI/API equivalence have not been corrupted.

The test strategy must nevertheless remain practical for ordinary development.

V1 therefore uses four validation tiers:

1. **Fast CI** — deterministic unit, domain, contract, CLI, and synthetic/generated-format fixture tests suitable for every change.
2. **Canonical fixture validation** — representative canonical excerpts and cross-representation scientific checks retained separately from parser-mechanics fixtures.
3. **Empirical ingestion spike** — real-source validation required before production large-file backend/storage choices are frozen.
4. **Full-dataset release validation** — explicit validation against the canonical dataset before a release is declared fully validated for PWDB `3275625`.

No tier is allowed to substitute for another merely because it is easier to run.

---

## 2. Core testing principles

The following are binding.

1. Scientific correctness has priority over feature count.
2. Routine CI must not download or materialize the full canonical dataset.
3. Full-source tests must use verified canonical artifacts, never silently modified copies.
4. Test tolerances must be justified by representation precision, documented conversion, numerical method properties, or measured reference differences.
5. No global arbitrary floating-point tolerance may be used as a universal scientific pass criterion.
6. Exact identities, classifications, schemas, checksums, selections, and provenance fields must be tested exactly where exactness is expected.
7. Approximate numerical comparison is used only where the scientific/data representation genuinely permits numerical variation.
8. A parser test must not silently become a scientific-method validation test.
9. A plugin protocol test does not certify the scientific validity of the plugin.
10. A test must fail clearly when its scientific prerequisite is unavailable rather than silently weakening the assertion.
11. Source, reconstructed, derived, inferred, and modelled outputs must be tested according to their actual evidence class.
12. No test may rewrite an authoritative mathematical definition merely to match current implementation output.

---

## 3. Validation tiers

### Tier 1 — Fast CI

Runs on every pull request/change set.

Must include:

- pure domain/value-object tests;
- schema parsing/validation against packaged resources;
- manifest validation;
- evidence/provenance semantics;
- selection/cohort semantics;
- public exception mapping;
- plugin registry/protocol conformance;
- API behavior using fake/minimal backends;
- CLI parsing/output/exit-code tests;
- source-adapter mechanics tests using synthetic/generated fixtures;
- import-boundary checks where practical.

Tier 1 must be small enough that developers can run it repeatedly without access to Zenodo or the full dataset.

Tier 1 proves code and parser mechanics; it does not by itself prove fidelity to the real PWDB scientific content.

### Tier 2 — Canonical fixture validation

Runs when retained canonical excerpts are available and during release preparation.

Must include representative canonical excerpts for the source classes needed by v1, where lawful and practical, including as appropriate:

- CSV source tables;
- common-site waveform representation(s);
- geometry representation;
- MATLAB structures used by the v1 backend;
- cross-representation overlap.

Tier 2 verifies source-to-canonical scientific mapping against known real-source excerpts rather than generated parser fixtures.

Tier 2 may run in normal CI when its retained excerpts remain small; it remains conceptually distinct from Tier 1 so generated parser data are never mistaken for evidence of PWDB source fidelity.

### Tier 3 — Empirical ingestion spike

Runs against real canonical source artifacts as required by `DATA_ENGINEERING.md`.

This tier is mandatory before production large-path reader/storage choices become final.

It verifies actual file structures, lazy/bounded access, subject alignment, source-format behavior, cross-representation consistency, and representative performance/memory behavior.

### Tier 4 — Full-dataset release validation

Runs against the complete set of required canonical artifacts for the release scope.

It validates the package against the real supported population and is separated from ordinary CI because of data volume and runtime.

A release may be built without Tier 4 on every commit, but it must not be labelled fully validated for the complete canonical dataset unless the applicable Tier 4 suite passes for that release candidate or exact code revision.

---

## 4. Test repository structure

The implementation should use a simple test layout such as:

```text
tests/
    unit/
    contracts/
    adapters/
    scientific/
    cli/
    integration/
    fixtures/
```

Full-source/spike tests may live under a separately marked area such as:

```text
tests/full_data/
```

or be activated through explicit pytest markers.

The exact directory names may vary, but ordinary tests and full-source tests must remain separable.

Do not create one test directory for every production module merely to mirror the source tree.

---

## 5. Test framework and minimal tooling

V1 should use **pytest** as the primary test runner.

Additional testing tools may be added only when they solve a concrete problem.

Expected minimum categories are:

- pytest;
- coverage reporting;
- static type checking selected during implementation;
- lint/format tooling selected during implementation.

Property-based testing is optional and should be used only where it materially improves confidence in invariants, parsing, or serialization. It is not a blanket requirement.

No heavyweight simulation-testing framework is required.

---

## 6. Test data classes

VascuQuest tests use four data classes.

### 6.1 Synthetic fixtures

Hand-built minimal data used to test domain/application behavior.

Synthetic fixtures must be obviously synthetic and must not be presented as PWDB reference values.

### 6.2 Canonical excerpts

Small faithfully retained excerpts from canonical source artifacts, where licensing and practical extraction permit.

Each canonical excerpt must record:

- source artifact identity/checksum;
- extraction procedure;
- subject/site/path selection;
- whether values are byte-preserved or transformed for fixture use;
- fixture creation version/script where applicable.

### 6.3 Generated format fixtures

Small files generated specifically to exercise a file parser or failure mode.

These validate parser mechanics only unless separately tied to authoritative scientific values.

### 6.4 Full canonical artifacts

Verified source files from Zenodo record `3275625` used only in Tier 3/4 validation.

They are never committed to the repository unless their upstream licensing, size, and project policy explicitly permit it; the current design assumes they remain external.

---

## 7. Fixture discipline

Fixtures must remain small and purpose-specific.

Rules:

1. A fixture contains only the information required to test the intended behavior.
2. Test data must not silently encode an undocumented scientific assumption.
3. Canonical excerpts retain source identity metadata.
4. Generated fixtures are not used as proof of PWDB source equivalence.
5. A fixture must not be mutated in place by a test.
6. Fixture regeneration must be deterministic where practical.
7. Binary fixtures require a documented provenance note or generation script.
8. Large fixtures that materially slow ordinary CI require explicit justification.

---

## 8. Manifest and source-identity tests

The packaged canonical manifest must be tested exactly.

Tests must establish at least:

- record ID is `3275625`;
- canonical DOI matches the design/data contract;
- exactly the supported 16 canonical artifact identities are present for v1;
- filenames are unique;
- checksum algorithm/value are present;
- artifact IDs are unique;
- capability mappings reference valid artifact IDs;
- source locators are syntactically valid configuration values;
- human-readable size metadata never substitutes for authoritative byte counts where byte counts are used for validation.

Manifest tests are exact comparisons, not floating-point tests.

---

## 9. Acquisition/integrity tests

The data layer must be tested for:

- successful streamed acquisition using a controlled test source;
- incomplete download never promoted to verified path;
- checksum success;
- checksum mismatch rejection;
- atomic promotion after verification;
- cleanup/quarantine behavior for failed artifacts;
- offline-mode refusal to access the network;
- registered-source discovery;
- partial registered datasets;
- mirror/source precedence;
- no mutation of registered external source files;
- interrupted/resumed transfer behavior only when the implementation claims resume support.

Network tests in routine CI should use local/fake HTTP infrastructure rather than depend on Zenodo availability.

Live Zenodo checks belong to explicit integration/release validation and must not make ordinary CI flaky.

---

## 10. Archive safety tests

Archive handling tests must include:

- valid extraction;
- path traversal rejection;
- absolute-path member rejection where applicable;
- incomplete extraction state;
- repeated extraction determinism;
- derived/extracted content separation from immutable source archive;
- no accidental deletion of canonical archive when derived extraction is cleaned.

Security tests should use generated malicious archive fixtures rather than real malicious external downloads.

---

## 11. Schema tests

The versioned canonical scientific schema must be validated mechanically.

Tests must cover:

- unique canonical quantity identities;
- valid canonical units/dimensional metadata;
- explicit dimensionless marking;
- valid categories;
- source-field mappings;
- allowed aliases;
- known upstream defect records;
- valid source/canonical unit relationships;
- expected coordinate/location applicability;
- missingness policy metadata where defined;
- schema version presence;
- collision prevention for operator-scoped versus canonical quantities.

A schema change that changes scientific interpretation must cause an intentional schema-version change test failure until the version/migration policy is updated.

---

## 12. Domain-model tests

Pure domain tests must not require filesystem/network access.

They must establish at least:

- dataset identity equality/inequality;
- subject identity includes dataset identity;
- virtual subjects are represented independently of source storage;
- cohort selection is deterministic;
- duplicate cohort membership is rejected in ordinary cohorts;
- site, segment, path, and path-position identities remain distinct;
- quantity identity is semantic rather than display-name based;
- evidence class is one of exactly five allowed values;
- validity/admissibility state is separate from evidence class;
- missing/unavailable/not-applicable/invalid/not-evaluated states remain distinguishable where represented;
- result metadata survives serialization round trips.

---

## 13. Subject and cohort validation

Tests must verify that:

- canonical subject identifiers map deterministically;
- cohort filtering does not silently drop missing values;
- plausibility filtering is explicit;
- cohort provenance preserves normalized selection criteria;
- age selection does not imply longitudinal-person identity;
- repeated identical selections produce the same ordered subject identifiers;
- CLI `--where field=value` and equivalent Python selection produce the same cohort membership.

Where source alignment depends on authoritative generation/export ordering rather than an explicit identifier field, the alignment rule must have a dedicated regression test.

---

## 14. Source-adapter tests

Each source adapter must be tested independently from the public scientific API.

Tests must establish:

- expected source structure is recognized;
- unexpected structure fails explicitly;
- source fields are traceable;
- numeric parsing is deterministic;
- missing-value representations are handled as declared;
- source units/labels are retained;
- canonical mappings are correct;
- subject/site/path indices are validated;
- raw parser/library objects do not escape the adapter boundary.

Adapters must not be validated only through end-to-end tests because that makes source-mapping failures hard to localize.

---

## 15. CSV tests

Representative CSV tests must cover:

- header-based mapping;
- column-order independence where appropriate;
- numeric parsing;
- explicit missing values;
- unexpected/missing required columns;
- subject identifier handling;
- canonical schema mapping;
- preservation of source column names for provenance.

CSV tests must not infer meaning from column position when source names exist.

---

## 16. WFDB tests

Representative WFDB tests must cover:

- record open/read;
- signal names;
- sample frequency metadata;
- units;
- signal length;
- missing/padding behavior where present;
- subject mapping;
- canonical waveform construction;
- failure on malformed or inconsistent record metadata.

The test validates the VascuQuest adapter around the selected maintained WFDB library. VascuQuest is not required to re-test the entire external library.

---

## 17. MATLAB/HDF5 tests

Representative MATLAB tests must distinguish source format families observed in the real dataset.

Tests must cover:

- expected struct/cell/object-reference conversion;
- shape/dtype mapping;
- nested field extraction;
- subject/site/path indexing;
- source metadata retention;
- bounded slice reads for HDF5-backed large-path structures where supported;
- no mandatory whole-file materialization for a slice-capable implementation;
- explicit failure on unsupported/unexpected layout.

A compact generated HDF5 fixture may test mechanics, but real-source Tier 3 validation is required before declaring the path backend production-ready.

---

## 18. Geometry tests

Geometry validation must establish only what the source actually provides.

Tests must verify:

- subject-to-geometry alignment;
- segment identities;
- source topology/connectivity fields where available;
- source-provided lengths/radii or other confirmed geometric quantities;
- unit mapping;
- no fabricated 3D coordinates, curvature, torsion, wall thickness, or other absent anatomy;
- geometry values are not conflated with non-geometric model/boundary parameters stored nearby.

---

## 19. Waveform tests

Waveform tests must verify:

- canonical signal identity;
- subject identity;
- location identity;
- sample/time coordinate consistency;
- unit metadata;
- evidence class;
- source provenance;
- missing/padding semantics;
- no mutation of source-backed samples by consumers/plugins;
- equivalent Python and CLI retrieval behavior.

No filtering, resampling, interpolation, or normalization may occur inside the source parser unless it is documented as a lossless representation step.

---

## 20. Cross-representation validation

Where PWDB exposes overlapping information through CSV, MAT, and/or WFDB representations, VascuQuest must compare the overlapping scientific content.

The comparison must establish, where applicable:

- subject identity agreement;
- site/signal naming agreement;
- sampling metadata agreement;
- unit agreement or documented upstream discrepancy;
- shape/length agreement;
- representative numerical equivalence under a justified tolerance;
- consistent canonical quantity mapping;
- consistent evidence classification.

One representation must not be designated the numerical truth merely because its parser was implemented first.

When representations intentionally differ because of documented conversion/export behavior, the test records and validates that difference rather than forcing equality.

---

## 21. Numerical tolerance policy

There is **no single project-wide scientific tolerance**.

Each approximate numerical assertion must state or inherit a documented rationale from one of:

1. exact source/export precision;
2. known decimal/text serialization precision;
3. floating-point roundoff implied by a deterministic operation;
4. authoritative published/reference-method tolerance;
5. measured cross-representation difference established by the ingestion spike;
6. algorithm-specific validation criterion defined by the owning scientific method.

Rules:

- exact integer/string/identifier checks use exact equality;
- exact deterministic metadata transformations use exact equality;
- tolerance values must be named or documented near the test/validation helper;
- increasing a tolerance to make a regression pass requires justification and review;
- percentage-only tolerances must not be used when absolute error near zero is scientifically material;
- tolerance comparisons must handle NaN/missing semantics explicitly rather than relying on library defaults.

---

## 22. Authoritative deterministic identities

An identity may be tested as an exact scientific invariant only when its meaning is authoritative for the supported source/model.

For v1, the previously audited PWDB exporter/model relationship that permits reconstructing flow rate from flow velocity and luminal area may be tested as the registered reconstruction:

```text
flow_rate = flow_velocity * luminal_area
```

This test is valid only in the contexts where the source definitions make the relationship applicable and the units/dimensions are compatible.

The reconstructed result must be classified `RECONSTRUCTED`, not `SOURCE` merely because the relation is exact.

No additional haemodynamic equation becomes a core invariant unless its authoritative definition and scope are separately established.

---

## 23. Unit and dimensional tests

Tests must verify:

- canonical unit identity;
- dimensional compatibility of source-to-canonical mapping;
- rejection of incompatible units;
- explicit treatment of dimensionless quantities;
- traceability of upstream unit-label defects;
- method input/output dimension checks;
- unit conversion behavior once the implementation policy is frozen.

The known upstream luminal-area metadata inconsistency must have a regression test ensuring that the raw source label remains inspectable while VascuQuest canonical interpretation remains area (`m^2`) where authoritative evidence establishes that interpretation.

The test must not modify the source metadata in place.

---

## 24. Evidence-class tests

Tests must establish that evidence classification follows the operation, not the code path.

Required cases include:

- parsed canonical source value -> `SOURCE`;
- registered exact reconstruction -> `RECONSTRUCTED`;
- deterministic scientific transformation -> declared `DERIVED` or other justified class;
- statistical population estimate -> normally `INFERRED`;
- external research-model output -> normally `MODELLED`;
- source input passed through an operator workflow does not automatically become `MODELLED` unless the operator produces a new model result;
- numerical agreement between a model result and a source value does not change either evidence class.

---

## 25. Provenance tests

Provenance tests must verify both completeness and determinism where expected.

Required assertions include:

- canonical dataset identity present;
- source artifact/checksum links present where applicable;
- schema version present;
- subject/cohort/location selection preserved;
- method/component identity/version preserved;
- normalized parameters preserved;
- assumptions/citations preserved when required;
- random seed/state preserved when relevant;
- evidence class preserved;
- validity/admissibility warnings preserved;
- equivalent deterministic workflows produce semantically equivalent provenance;
- provenance lineage is acyclic for completed results;
- large arrays are referenced rather than duplicated unnecessarily in provenance.

Exact serialized byte equality is required only when the serialization contract promises deterministic ordering/encoding. Otherwise semantic equality is sufficient.

---

## 26. Derivation validation

Every built-in derivation must have:

1. definition/source citation;
2. unit/dimension tests;
3. normal-case numerical tests;
4. boundary/invalid-input tests;
5. evidence-class test;
6. provenance test;
7. reference or independently checkable result where feasible.

A derivation with a mathematical definition must be tested against the authoritative definition, not against a copy of the same implementation logic in the test.

Tests must not duplicate implementation code line-for-line as the oracle.

---

## 27. Research-operator validation

Built-in research operators must be tested at two distinct levels.

### Protocol level

- descriptor validity;
- declared inputs/outputs;
- parameter validation;
- evidence class;
- admissibility metadata;
- provenance;
- mutation protection.

### Scientific level

The operator's own package/module must supply validation appropriate to its formulation, such as:

- dimensional consistency;
- limiting/special-case behavior where authoritative;
- independent/reference calculations;
- regression against published/validated outputs;
- declared-domain tests.

The VascuQuest core test suite does not rederive external theory merely to test the plugin protocol.

No operator is considered scientifically validated solely because its protocol tests pass.

---

## 28. Discovery-method validation

Discovery methods must test, where applicable:

- exact cohort preservation;
- declared missing-data policy;
- deterministic output for fixed deterministic inputs;
- explicit random-state behavior;
- validation/resampling metadata;
- multiplicity handling when the method claims it;
- effect/association metadata when the method produces them;
- exploratory versus confirmatory status where applicable;
- evidence classification;
- prevention of human-causal wording in core result semantics.

Statistical-method tests should use standard reference datasets or analytically/simple independently checkable cases when feasible, without turning core CI into a comprehensive statistics-package certification suite.

---

## 29. Plugin protocol conformance tests

VascuQuest must provide reusable conformance tests/helpers for each public plugin category.

They should test:

- zero-argument factory shape;
- returned component protocol conformance;
- descriptor fields;
- unique/canonical qualified ID syntax;
- integer protocol major version;
- declared input/output metadata;
- serializable parameters;
- read-only input expectations;
- structured result metadata;
- provenance contribution;
- deterministic handling of incompatible versions and duplicate IDs.

Conformance helpers must be usable by third-party developers without access to private VascuQuest internals.

---

## 30. Plugin registry tests

Registry tests must cover:

- built-in component registration;
- installed entry-point discovery;
- lazy loading where implemented;
- duplicate ID rejection;
- unsupported protocol version rejection;
- disabled component behavior;
- missing/broken optional plugin isolation;
- deterministic registry ordering for presentation where promised;
- no arbitrary `.py` path loading;
- no silent shadowing of built-in IDs.

---

## 31. API tests

Public API tests must validate behavior rather than internal call structure.

At minimum:

- `open_dataset()` returns a session/facade;
- opening does not force full acquisition;
- metadata/status calls are lightweight;
- subject/cohort objects are lightweight;
- quantity/waveform retrieval returns structured results;
- derivation/modelling/discovery dispatch uses registered components;
- export retains required metadata;
- strict reproduction rejects unavailable/incompatible component versions;
- stable public errors are raised for expected failures;
- internal backend objects are not required by normal user code.

---

## 32. CLI tests

CLI tests must exercise Typer only as the interface adapter.

Required cases include:

- global help/version;
- command help;
- dataset default identity resolution;
- `stdout` contains only primary result;
- `stderr` contains diagnostics/progress/errors;
- valid JSON output;
- valid JSONL output;
- CSV rejection when a result cannot be represented faithfully;
- non-interactive confirmation behavior;
- `--yes` behavior;
- 1 GiB large-download confirmation policy;
- `--offline` behavior;
- exact exit-code mapping;
- `--debug` traceback behavior;
- selection grammar `--where field=value`;
- method parameter grammar `--param name=value`;
- explicit exporter selection;
- no scientific calculation implemented uniquely in CLI code.

---

## 33. API/CLI parity tests

For each stable scientific CLI capability, at least one test must compare it with the equivalent Python/API operation.

Parity means:

- same canonical dataset resolution;
- same subject/cohort selection;
- same scientific values within the appropriate comparison policy;
- same units;
- same evidence class;
- semantically equivalent provenance;
- same validity/admissibility state;
- CLI formatting differences only at presentation boundary.

The CLI must never require a separate scientific oracle.

---

## 34. Error and failure-path tests

Expected failures require first-class tests.

At minimum:

- missing artifact;
- offline missing capability;
- checksum mismatch;
- malformed archive;
- malformed CSV/WFDB/MAT fixture;
- schema mismatch;
- incompatible units;
- invalid selection;
- unavailable location;
- inadmissible operator input;
- numerical method failure;
- plugin load failure;
- plugin protocol mismatch;
- duplicate plugin ID;
- missing plugin during reproduction;
- corrupt derived cache;
- interrupted acquisition state.

Tests must verify both Python exception type and CLI exit-code mapping where the failure is exposed through both interfaces.

---

## 35. Serialization tests

Machine-readable metadata/result serialization must test:

- round-trip preservation of stable metadata;
- evidence class;
- dataset identity;
- units/dimensions;
- coordinates where applicable;
- warnings/validity;
- provenance;
- plugin/component identity;
- normalized parameters;
- stable handling of missing states;
- no accidental embedding of backend-specific objects.

JSON serialization must reject or explicitly encode unsupported nonportable objects rather than silently stringifying them into irreproducible forms.

---

## 36. Reproducibility tests

Reproduction tests must cover:

- exact deterministic rerun with same available versions;
- missing source artifact reporting;
- missing plugin reporting;
- component-version mismatch;
- schema-version mismatch;
- changed random seed producing a distinct provenance record;
- explicit rerun-under-current-version behavior generating new provenance;
- no silent substitution of dataset, method, or plugin version.

A reproduction test does not require byte-identical numerical output when the owning scientific method documents platform-level nondeterminism; the expected reproducibility level must be explicit.

---

## 37. Cache and persistence tests

Tests must verify separation among:

- canonical source artifacts;
- temporary/work files;
- derived/indexed/converted stores;
- user results;
- state/registration metadata.

Required cases include:

- source cleanup cannot delete user results;
- derived cleanup cannot delete canonical external registrations;
- failed derived store can be rebuilt;
- derived-store identity changes when material source checksum/schema/builder version changes;
- incomplete concurrent build is not treated as valid;
- atomic finalization where promised.

---

## 38. Concurrency tests

V1 concurrency testing is limited to local process/file safety.

It must cover representative cases where two processes attempt to:

- acquire the same artifact;
- verify/use an artifact while another process is downloading it;
- build the same derived store;
- clean stale temporary state.

The goal is preventing corrupted state, not benchmarking parallel scalability.

No distributed-lock or cluster test infrastructure is required.

---

## 39. Import-boundary tests

Architecture dependency rules should be mechanically checked where practical.

At minimum, tests/static checks must prevent:

- `domain` importing `ports`, `services`, concrete backends, data adapters, or CLI;
- `ports` importing concrete adapters;
- `services` depending on PWDB file-layout internals;
- `cli` becoming imported by scientific layers;
- `bootstrap.py` accumulating scientific/parser logic.

A lightweight import-linter/static check is acceptable if justified; otherwise targeted tests/code-review checks are sufficient for v1.

Do not add a complex architectural analysis framework solely for this purpose.

---

## 40. Performance and memory validation

Performance tests are evidence-gathering guards, not microbenchmark competitions.

Routine CI should test only obvious regressions that can be measured reliably, such as:

- metadata/session opening does not trigger large acquisition;
- one-subject fixture access does not materialize all fixture subjects;
- lazy/streaming interfaces do not force unnecessary copies in controlled cases.

Real path-file access latency, memory footprint, indexing, and chunking decisions belong to the ingestion spike.

Hard numeric performance thresholds must be based on measured representative workloads and hardware context, not invented in this document.

---

## 41. Mandatory ingestion-spike validation

Tier 3 must execute the requirements already defined in `DATA_ENGINEERING.md` and record evidence sufficient to choose production access strategies.

It must include real canonical-source checks for at least:

- one representative metadata CSV;
- one WFDB waveform record;
- representative geometry;
- `pwdb_data.mat`;
- at least one bounded slice from a large path MAT file.

The spike must validate:

- actual structures/shapes/dtypes;
- subject/site/path indexing semantics;
- source units/metadata;
- selective/lazy access reality;
- representative memory behavior;
- representative first/repeated access behavior;
- source-format failure behavior;
- cross-representation consistency;
- resumable/range acquisition behavior if the implementation intends to support it.

A production path backend cannot be marked complete until this tier passes for the chosen strategy.

---

## 42. Full-dataset release validation

Tier 4 validates the release candidate against the complete source scope it claims to support.

At minimum it must verify:

- all required canonical artifacts are present and checksum-valid;
- all 4,374 canonical simulation identities are accounted for according to validated source semantics;
- source tables map consistently to canonical subjects;
- declared measurement sites/signals are discoverable;
- representative waveforms across subject/age/configuration space can be read;
- geometry alignment holds across representative/all feasible subjects as appropriate;
- path data are readable for each supported path family;
- plausibility metadata remains available;
- canonical schema mappings do not produce unexpected unmapped required fields;
- no systematic cross-representation mismatch exceeds its justified tolerance;
- standard research operations complete without hidden full-memory materialization where bounded access is expected.

Tier 4 may be split into parallel jobs operationally, but scientific pass/fail criteria remain unified.

---

## 43. Full-dataset sampling versus exhaustive checks

Not every expensive numerical comparison must be exhaustive if a representative sampling strategy is scientifically and technically sufficient.

Rules:

- identity/checksum/file-inventory checks are exhaustive;
- subject-count/alignment checks are exhaustive where practical;
- parser/readability checks should cover all structural variants;
- expensive waveform numerical comparisons may use deterministic stratified samples when exhaustive comparison adds little information;
- sampling criteria must be recorded and reproducible;
- any detected structural inconsistency escalates to broader/exhaustive investigation before release.

This avoids pretending that “more iterations” automatically means better validation.

---

## 44. CI platform matrix

The package must be tested on Linux, Windows, and macOS for supported Python environments.

To keep CI practical:

- Linux may carry the full supported Python-version matrix;
- Windows and macOS must at least test the lowest and highest supported Python versions, or an equivalent boundary matrix;
- tests that are inherently platform-independent need not be duplicated excessively;
- platform-specific filesystem/path/atomic-operation behavior must be tested on the relevant platform.

The exact supported Python versions are frozen in package metadata/build planning, not guessed independently by this contract.

---

## 45. CI network policy

Fast CI should be network-independent by default.

Tests must use:

- local fixtures;
- fake/local HTTP servers;
- fake plugin distributions/entry points where practical.

Explicit live-source jobs may access Zenodo for integration/release purposes, but a transient public-network failure must not masquerade as a scientific regression in ordinary CI.

---

## 46. Coverage policy

Coverage is a diagnostic, not the scientific acceptance criterion.

V1 should track coverage and prevent severe accidental regression, but it must not chase 100% line coverage by writing low-value tests.

Critical scientific/data/provenance paths require direct tests regardless of aggregate coverage percentage.

A high coverage number does not compensate for missing reference/invariant tests.

---

## 47. Regression-test rule

Every confirmed defect that could recur must receive a regression test when technically feasible.

A regression test should reproduce the smallest scientifically faithful failure case.

Bug fixes must not weaken a scientific assertion or enlarge a tolerance without documenting why the original assertion was wrong.

---

## 48. Test markers and execution modes

The test suite should use a small marker set, for example:

```text
unit
integration
full_data
slow
```

Exact names may vary.

Avoid a proliferation of overlapping markers.

Default local/CI execution should exclude `full_data` and genuinely slow external-data tests unless explicitly requested.

---

## 49. Release-gate definition

A VascuQuest release candidate is acceptable only when all applicable gates pass.

### Code gate

- fast CI passes;
- supported platform matrix passes;
- static/type/lint checks selected by the build plan pass;
- package builds/install smoke tests pass.

### Scientific-contract gate

- schema tests pass;
- evidence/provenance tests pass;
- built-in scientific methods pass their method-specific validation;
- API/CLI parity passes;
- no unresolved scientific-regression test is skipped without documented reason.

### Data-backend gate

- synthetic/generated adapter mechanics tests pass;
- applicable canonical-excerpt fixture tests pass;
- ingestion spike has approved the production strategy;
- full-source validation required for the claimed release scope passes.

### Extension gate

- built-in components pass protocol conformance;
- registry/version/collision behavior passes;
- third-party conformance helper suite is runnable independently.

No single aggregate test count or coverage percentage substitutes for these gates.

---

## 50. Allowed skips and expected failures

Skipped/xfail tests are allowed only when they are explicit and justified.

Each must identify:

- reason;
- condition;
- whether the issue is environmental, optional-dependency, known upstream limitation, or unresolved defect;
- issue/reference when the skip could hide a release-critical problem.

A required scientific correctness test must not be permanently skipped merely because the current implementation fails it.

---

## 51. Test isolation

Tests must not depend on execution order.

They should use temporary directories/state and clean up after themselves.

Tests must not:

- write into the installed package;
- alter registered user data;
- depend on another test having downloaded data;
- share mutable global plugin registries without reset/isolation;
- require a developer's personal configuration to pass.

---

## 52. Deterministic randomness

Tests of random methods must use explicit seeds/random-state inputs where the method supports reproducibility.

The test must verify that:

- the seed/state enters provenance;
- fixed-state behavior meets the method's declared reproducibility semantics;
- changing the seed creates new provenance;
- tests do not depend on ambient global random state.

---

## 53. Mathematical-fidelity rule

Testing code must never become an alternative source of scientific truth.

For every implemented mathematical scientific method:

1. identify the authoritative definition;
2. define the method's applicable domain;
3. establish units/dimensions;
4. build independent/reference checks where feasible;
5. test limiting/special cases only when they are authoritative for that formulation;
6. record any numerical tolerance and its justification;
7. test provenance/evidence classification separately from numerical agreement.

A copied duplicate of production algebra is not an independent validation.

If the source material does not establish a mathematical statement, the core test suite must not invent it.

---

## 54. Scientific claims boundary

Passing VascuQuest tests establishes software conformance to its defined source/model contracts.

It does not establish:

- clinical validity;
- human causal truth;
- universality of a research operator outside its declared domain;
- correctness of arbitrary third-party science;
- equivalence of unvalidated PWDB releases;
- novelty or publication worthiness of discovered relationships.

Tests must not encode such claims implicitly.

---

## 55. Implementation invariants

The following must remain true throughout the test suite and implementation.

1. Fast CI does not require the full canonical dataset.
2. Full canonical artifacts remain external to normal repository tests.
3. Test fixtures are classified as synthetic, generated, canonical excerpt, or full canonical source.
4. Tier 1 generated/synthetic parser tests do not count as Tier 2 real-source scientific fidelity evidence.
5. Exact scientific identities use exact assertions.
6. Approximate numerical tolerances are justified per method/representation.
7. No universal scientific tolerance exists.
8. Source parsing and scientific transformation tests remain distinguishable.
9. Cross-representation validation compares canonical scientific meaning, not parser internals.
10. Evidence class is tested according to operation semantics.
11. Provenance completeness is directly tested.
12. CLI/API parity is tested for each stable scientific operation.
13. Plugin conformance does not imply scientific validation.
14. Operator mathematics remain owned by the operator's scientific validation suite.
15. The core does not invent new haemodynamic equations as test invariants.
16. The `flow_rate = flow_velocity * luminal_area` reconstruction is tested only in validated applicable contexts and remains `RECONSTRUCTED`.
17. Upstream source-unit defects remain traceable and are not repaired by source mutation.
18. Ingestion-spike evidence is required before production large-path storage/access strategy is accepted.
19. Full-dataset release validation is tied to the exact release candidate/code revision.
20. Expected failures have stable Python exception/CLI exit-code behavior.
21. Regression tests are added for confirmed recurring defects where feasible.

---

## 56. Minimal acceptance scenarios

### A. Fast CI without data download

A clean checkout runs the default test suite with no PWDB dataset present and no network access.

Expected: all domain, contract, CLI, plugin, serialization, and synthetic/generated adapter-mechanics tests execute successfully.

### B. Canonical fixture validation

A retained canonical excerpt is exercised through its source adapter and canonical schema mapping.

Expected: real-source field, unit, subject/location identity, and expected scientific values/metadata are preserved according to the fixture provenance.

### C. Corrupted source artifact

A controlled fixture has an incorrect checksum.

Expected: integrity validation fails; the artifact is never promoted/used as canonical source; API and CLI expose the correct failure class/code.

### D. Cross-representation waveform

A canonical excerpt exists in two validated source representations.

Expected: subject/signal/site/unit metadata agree and numerical comparison uses a documented representation-specific tolerance.

### E. Evidence classification

A source waveform is passed to a registered deterministic derivation and separately to a research operator.

Expected: original waveform remains `SOURCE`; derivation output gets its declared class; operator output is normally `MODELLED`; provenance links remain distinct.

### F. CLI/API parity

The same subject selection and quantity retrieval are performed through Python and the CLI.

Expected: same canonical selection/value/unit/evidence semantics and equivalent provenance; only rendering differs.

### G. Plugin protocol mismatch

A test plugin declares protocol major `2` against v1 major `1`.

Expected: rejection before scientific execution and no effect on unrelated core workflows.

### H. Real large-path spike

A verified real path MAT artifact is opened and one bounded subject/path/signal slice is requested.

Expected: the measured result establishes whether selective access is genuinely bounded and informs the allowed production strategy; no assumption is made beforehand.

### I. Release validation

The release candidate is run against the claimed full canonical dataset scope.

Expected: manifest/integrity/subject/schema/representative waveform/geometry/path validations pass and the validation report identifies the exact package revision and source checksums.

---

## 57. Audit checklist

`TEST_VALIDATION_CONTRACT.md` passes only if every answer is **yes**.

### Simplicity

- Are there only four meaningful validation tiers?
- Is the Tier 1/Tier 2 boundary explicit rather than duplicated?
- Can ordinary CI run without external dataset/network dependence?
- Is there no requirement for a heavyweight test/simulation framework?
- Are markers, fixtures, and platform matrices kept small?

### Completeness

- Are source identity, acquisition, schema, domain, adapters, waveforms, geometry, evidence, provenance, plugins, API, CLI, serialization, failure behavior, and reproducibility directly testable?
- Are ingestion-spike and full-data validation both covered?
- Are regression and release gates explicit?

### Feasibility

- Can fast tests use compact synthetic/generated fixtures and fakes?
- Can real-source canonical excerpts remain small and independently traceable?
- Can large-source tests remain separate?
- Can the platform matrix be executed with normal GitHub-hosted/local CI runners?
- Are performance requirements evidence-based rather than invented?

### Scientific integrity

- Are exact versus approximate assertions distinguished?
- Are tolerance justifications mandatory?
- Are source and modelled results tested separately?
- Are upstream defects tested without modifying source data?
- Are clinical/causal claims excluded from software-validation meaning?

### Mathematical fidelity

- Does the contract avoid introducing unsupported equations?
- Is the one explicit reconstruction identity limited to its already-audited applicable context?
- Must method tests use authoritative definitions/reference checks rather than copied production algebra?
- Are dimensional and limiting tests required only where scientifically justified?

### Architecture/API compatibility

- Are domain tests independent of concrete storage?
- Are backend tests localized?
- Are plugin protocol tests independent of private internals?
- Are CLI/API parity and import-boundary requirements explicit?

If any answer is no, this file must be amended before proceeding to `BUILD_PLAN.md`.

---

## 58. Approval consequence

Once this contract passes audit:

- the v1 testing/validation architecture is frozen;
- tolerance policy is frozen as evidence-derived rather than global;
- fast CI versus canonical-fixture validation versus ingestion-spike versus full-release validation responsibilities are fixed;
- the only remaining pre-implementation planning document is `BUILD_PLAN.md`.

The next contract is `BUILD_PLAN.md`.
