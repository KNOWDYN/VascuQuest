# VascuQuest Scientific Model Contract

**Status:** Scientific semantics contract for implementation  
**Governing documents:** `DESIGN_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_ENGINEERING.md`  
**Repository:** `KNOWDYN/VascuQuest`  
**Canonical v1 dataset:** Zenodo record `3275625`  
**Purpose:** Define the minimum scientific concepts, identities, relationships, unit semantics, evidence semantics, and interpretation rules required for VascuQuest to expose PWDB faithfully and to host future derivations, research operators, and discovery methods without confusing source data with modelled or inferred science.

---

## 1. Objective

VascuQuest needs a scientific model that is richer than a collection of arrays but simpler than a full cardiovascular ontology.

The model must let researchers ask scientifically meaningful questions such as:

- which virtual subjects satisfy a physiological or haemodynamic condition;
- what source quantities are available for a given subject or cohort;
- what waveform is present at a specific vascular location;
- how geometry, haemodynamics, age, model configuration, and waveform features vary across the virtual population;
- which quantities are source values and which were reconstructed, derived, inferred, or modelled;
- what inputs, assumptions, source artifacts, and methods produced a result.

The model must not embed the historical PWDB file layout, impose one numerical-array library as the scientific truth, or absorb specialized haemodynamic theories into the permanent core.

The core scientific model is therefore deliberately small.

---

## 2. Governing scientific principles

The following rules are binding.

1. A PWDB **virtual subject is a simulation instance**, not a human participant or patient.
2. Source quantities retain `SOURCE` evidence unless a scientific transformation changes their status.
3. `SOURCE`, `RECONSTRUCTED`, `DERIVED`, `INFERRED`, and `MODELLED` remain distinct throughout Python, CLI, exports, and provenance.
4. Canonical meaning and units come from the versioned VascuQuest scientific schema; raw source labels remain traceable.
5. Age is a subject/model attribute unless an explicitly validated relationship establishes a stronger interpretation.
6. VascuQuest must not silently interpret different age entries as longitudinal observations of one biological individual.
7. Measurement sites, arterial segments, and path positions are related but not interchangeable concepts.
8. Missing, unavailable, not-applicable, and invalid values are distinct states and must not be collapsed without justification.
9. Physiological plausibility information is scientific metadata, not an automatic deletion rule.
10. External theoretical quantities enter through derivations or research operators and do not become source truth merely because they can be calculated from source data.
11. The scientific model must not invent anatomy, geometry, material properties, constitutive behaviour, or clinical meaning absent from the supported source or declared external model.
12. Mathematical definitions are introduced only in the scientific component that owns them and only with authoritative definition, dimensional checks, and validation tests.

This document intentionally introduces **no new governing haemodynamic equations**.

---

## 3. Scope boundary

### 3.1 In scope

The core model must represent:

- dataset identity;
- virtual subject identity and attributes;
- cohorts;
- model/configuration attributes;
- physiological plausibility state;
- vascular segments and topology;
- named measurement sites;
- arterial paths and path positions;
- source-provided geometry;
- scalar and array-valued scientific quantities;
- waveform signals and their coordinates;
- haemodynamic parameters;
- pulse-wave indices;
- onset/fiducial timing quantities;
- units and dimensions;
- evidence class;
- provenance;
- results produced by derivations, research operators, and discovery methods.

### 3.2 Out of scope for the core ontology

The core does not permanently encode:

- Womersley-specific state variables;
- anisotropic-viscosity tensors;
- fractional-order model parameters;
- complex Ginzburg--Landau variables;
- susceptibility kernels;
- endothelial-response models;
- clinical diagnoses;
- disease labels not contained in the supported source;
- patient identity;
- three-dimensional vessel coordinates not present in the source;
- wall shear stress or any other field merely because it is common in haemodynamics;
- every possible statistical or machine-learning concept.

Such concepts may be added as schema-defined quantities, derivations, research-operator inputs/outputs, or future backend-specific extensions when scientifically justified.

---

## 4. Minimal conceptual model

The v1 scientific model has ten primary concepts.

| Concept | Meaning |
|---|---|
| `DatasetIdentity` | Exact virtual-population dataset/version identity |
| `VirtualSubject` | One canonical simulation instance within a dataset |
| `Cohort` | Reproducible selection of virtual subjects |
| `VascularLocation` | Canonical reference to segment, site, or path position |
| `Geometry` | Source-provided geometric description associated with subject/location |
| `QuantityDefinition` | Canonical scientific meaning, dimensions, units, aliases, and source mappings |
| `ScientificResult` | Values plus coordinates, evidence class, context, and provenance |
| `Waveform` | Time-resolved scientific result with a signal definition and sampling/time coordinate |
| `EvidenceClass` | Scientific status: source/reconstructed/derived/inferred/modelled |
| `ProvenanceRecord` | Reproducible lineage of data, transformations, methods, and assumptions |

This is a conceptual contract, not a mandate for ten Python classes. Implementation may use value objects, dataclasses, enums, arrays, mappings, or protocols where appropriate, provided these distinctions remain observable and testable.

---

## 5. Dataset identity

A `DatasetIdentity` answers: **which exact virtual population is this?**

For v1 it must identify at least:

```text
dataset_family: PWDB
record_id: 3275625
persistent_identifier: 10.5281/zenodo.3275625
schema_version: <VascuQuest canonical schema version>
```

Scientific results must not rely on a filename or local directory as dataset identity.

A future PWDB record or another virtual-population dataset receives a distinct identity unless equivalence has been explicitly validated and documented.

Dataset identity is immutable within an opened dataset session.

---

## 6. Virtual subject

### 6.1 Definition

A `VirtualSubject` is one simulation instance exposed by the canonical backend.

It has:

- a canonical subject identifier within the dataset;
- dataset identity;
- source/model attributes available for that simulation;
- physiological plausibility metadata where available;
- links to available geometry, quantities, waveforms, sites, and paths.

The subject identifier is meaningful only together with dataset identity.

Conceptually:

```text
SubjectKey = DatasetIdentity + canonical_subject_id
```

This is an identity rule, not a mathematical equation.

### 6.2 Virtual-subject semantics

A virtual subject must not be described by VascuQuest as:

- a patient;
- a clinical case;
- a biological individual followed over time;
- an observed human participant.

Terms such as "subject" are retained for compatibility with the dataset and research literature, but the API/documentation must make the simulated nature explicit where confusion is possible.

### 6.3 Subject attributes

Subject attributes may include source-defined model configuration, age, physiological/model parameters, variation descriptors, and plausibility information.

The core must not create a unique Python field for every PWDB column. Dataset-specific attributes should be represented through canonical quantity/attribute definitions governed by the schema.

A small set of universally useful identity fields may receive direct convenience accessors after their semantics are validated.

### 6.4 Age semantics

Age is represented as a source/model attribute with its source unit and canonical interpretation.

VascuQuest must not infer that two simulations at different ages are repeated observations of the same biological individual merely because other configuration values match.

If PWDB generation logic permits a validated cross-age configuration-family relation, VascuQuest may expose that relation explicitly as a dataset-specific grouping key. Such a grouping is not equivalent to biological longitudinal identity.

---

## 7. Physiological plausibility

PWDB includes information allowing simulations to be distinguished by physiological plausibility.

VascuQuest must represent plausibility as source-backed scientific metadata whose exact canonical form is established from the source during schema/ingestion validation.

Rules:

1. plausibility must remain inspectable;
2. implausible simulations must not be silently discarded from the canonical population;
3. cohort constructors may provide explicit convenience filters for plausibility after semantics are validated;
4. every analysis using such a filter must retain it in the cohort definition/provenance;
5. plausibility in the virtual model must not be presented as a diagnosis or clinical adjudication.

---

## 8. Cohort

### 8.1 Definition

A `Cohort` is a reproducible selection of virtual subjects from one dataset identity.

A cohort is defined by selection semantics, not by copying subject data into a new dataset.

It must be able to retain:

- parent dataset identity;
- selection expression or normalized selection specification;
- resulting subject identifiers;
- ordering rule where ordering matters;
- explicit inclusion/exclusion filters;
- plausibility filter if used;
- creation provenance.

### 8.2 Cohort rules

1. A cohort belongs to one dataset identity in v1.
2. Duplicate subject identifiers are not allowed in a normal cohort unless a specialized method explicitly requires repeated weighting/resampling.
3. Default cohort order must be deterministic.
4. Selection on a missing quantity must fail or apply an explicitly requested missing-data policy; it must not silently drop subjects.
5. A cohort is not automatically a statistical sample of a real human population.
6. Population-level statements must preserve the fact that the data originate from a virtual population generated by a model.

### 8.3 Matched and grouped cohorts

Methods may form groups or matched contrasts using validated subject attributes.

Matching does not create causal identification by itself.

Any matching key, tolerance, exclusion rule, or weighting rule is method provenance, not hidden cohort state.

---

## 9. Vascular location model

VascuQuest requires a location model that can express network structure without pretending all source locations are equivalent.

`VascularLocation` is therefore a conceptual union of three distinct location kinds:

1. `SegmentLocation`
2. `MeasurementSite`
3. `PathPosition`

Implementation may use separate types or one tagged value object.

### 9.1 Arterial segment

An arterial segment represents a source-defined segment in the vascular network.

It may carry:

- canonical segment identifier;
- source segment identifier/name;
- parent/child connectivity where established;
- source-provided geometric quantities;
- subject association where geometry varies by subject.

Topology is a graph relation among source-defined segments. VascuQuest does not require a graph database or a particular graph library.

### 9.2 Measurement site

A measurement site is a canonical named location at which one or more signals or quantities are reported.

A site may map to a segment and/or a position within a segment when this relationship is established by the source.

A measurement site must not be assumed to represent the entire artery or segment.

### 9.3 Arterial path

An arterial path is an ordered sequence through the vascular network used by path-resolved data.

A path has:

- canonical path identity;
- ordered membership/route information where available;
- path coordinate/distance information supplied by the source;
- accessible path positions;
- association with path-resolved signals.

A path is not a new anatomical vessel. It is a traversal through source-defined arterial segments.

### 9.4 Path position

A path position identifies a source-supported location along a path.

It may include:

- path identity;
- path distance coordinate;
- source segment identity;
- within-segment distance when supplied;
- source point/sample index for traceability.

Path distance must retain its source/canonical unit and coordinate orientation.

No interpolation between stored path positions is implied by the location model. Interpolation, if offered, is a `DERIVED` operation with explicit method provenance.

---

## 10. Geometry

### 10.1 Definition

`Geometry` represents geometric information actually supplied by the supported dataset.

It may describe source-defined quantities such as segment lengths and radii where confirmed by the schema.

The scientific model allows geometry to be associated with:

- a virtual subject;
- a segment;
- a site;
- a path position;
- or another source-defined vascular entity.

The exact mapping is backend/schema controlled.

### 10.2 Geometry restrictions

VascuQuest must not infer or fabricate:

- 3D centerlines;
- curvature;
- torsion;
- bifurcation angles;
- wall thickness;
- plaque geometry;
- stenosis geometry;
- surface meshes;
- patient-specific anatomy;

unless such information is present in a future supported source or explicitly produced by a declared external model.

### 10.3 Geometry versus non-geometric model parameters

Parameters associated with arterial segments or boundary conditions are not automatically geometry merely because they appear in the same upstream file.

The canonical schema determines whether a source field is geometric, haemodynamic, material/constitutive, boundary-condition related, or another model parameter.

---

## 11. Quantity definition

### 11.1 Purpose

A `QuantityDefinition` describes what a scientific value means independently of one subject or one numerical result.

It should be able to define:

- canonical name;
- human-readable label;
- scientific description;
- physical dimensions;
- canonical unit;
- allowed source units;
- expected value shape/kind;
- applicable contexts/locations;
- source aliases/mappings;
- default evidence class when directly sourced;
- known source defects or ambiguities;
- citations or authoritative definition references;
- schema version.

### 11.2 Quantity identity is semantic

Two source columns/signals with the same numerical values are not the same canonical quantity unless their scientific meaning is the same.

Two quantities with similar names must not be merged based on string similarity.

Conversely, source aliases may map to one canonical quantity when their equivalence has been validated.

### 11.3 No class-per-variable design

VascuQuest must not create permanent Python subclasses such as one class for every haemodynamic parameter or pulse-wave index.

New canonical quantities should normally be data-driven through the versioned schema.

Dedicated types are reserved for cases where behaviour or invariants genuinely differ, such as waveforms or vascular locations.

---

## 12. Scientific result

### 12.1 Definition

A `ScientificResult` couples numerical/categorical values with enough scientific context to interpret them correctly.

It must be able to retain, where applicable:

- quantity definition/identity;
- values;
- coordinates/dimensions;
- canonical units;
- source-unit information when relevant;
- subject or cohort context;
- vascular location context;
- evidence class;
- provenance;
- validity/admissibility state;
- warnings;
- method identity for non-source results.

### 12.2 Scalars, vectors, tables, and arrays

A scientific result may contain:

- one scalar;
- one value per subject;
- one value per site;
- one value per path position;
- a time series;
- a multi-dimensional array;
- a table-like collection of heterogeneous canonical quantities.

The scientific model defines semantics, not one storage container.

### 12.3 Coordinates

Coordinates give meaning to array axes.

Examples include:

- subject identifier;
- time;
- measurement site;
- segment;
- path position/distance;
- signal component;
- method-specific dimensions declared by an operator.

Axis ordering is an implementation representation and must not be treated as the scientific identity of a dimension.

---

## 13. Waveform

### 13.1 Definition

A `Waveform` is a time-resolved scientific result for a canonical signal at a defined vascular location and subject/context.

It must retain:

- signal/quantity identity;
- samples;
- time coordinate or sufficient sampling metadata to reconstruct it exactly;
- unit;
- subject identity;
- vascular location;
- evidence class;
- source representation/provenance;
- missing/padding information where applicable.

### 13.2 Canonical v1 signal families

The core must be capable of representing the source waveform families exposed by PWDB, including:

- pressure;
- flow velocity;
- luminal area;
- photoplethysmogram signal;

using canonical quantity definitions established by the schema.

Additional quantities such as flow rate may be exposed only with the evidence status appropriate to how they are obtained.

### 13.3 Waveform identity

A waveform is not identified by its filename.

Its scientific identity includes at least:

```text
dataset + subject + signal + vascular location + time/sampling context
```

### 13.4 Waveform transformations

Operations such as:

- resampling;
- interpolation;
- filtering;
- smoothing;
- differentiation;
- integration;
- Fourier decomposition;
- normalization;
- phase alignment;
- beat selection;

are scientific transformations, not parsing conveniences, unless they are proven lossless representation changes.

They must therefore create explicit provenance and receive the evidence classification appropriate to the operation.

---

## 14. Haemodynamic parameters, pulse-wave indices, and timing quantities

PWDB exposes source-level scalar/summary quantities in dedicated data products.

The scientific model treats these primarily as `QuantityDefinition` + `ScientificResult`, not as separate inheritance hierarchies.

The schema may tag a canonical quantity by category such as:

```text
haemodynamic_parameter
pulse_wave_index
onset_or_fiducial_time
model_parameter
geometry_parameter
waveform_signal
```

Categories aid discovery and presentation but do not replace precise scientific definitions.

VascuQuest must not recompute a source pulse-wave index merely because an algorithm with the same name exists. A recomputed value is a separate result whose provenance and evidence class identify the method used.

---

## 15. Units and physical dimensions

### 15.1 Canonical-unit rule

Every dimensional canonical quantity must declare a canonical unit and physical dimensionality in the scientific schema.

Dimensionless quantities must be marked explicitly as dimensionless rather than represented by an absent unit.

### 15.2 Source versus canonical units

A source may contain a unit label that differs from the VascuQuest canonical unit or contains a documented upstream metadata defect.

VascuQuest must preserve both:

```text
source unit/label
canonical unit/interpretation
```

A correction to interpretation occurs in the schema, not by editing source data.

### 15.3 Unit conversion

Unit conversion must be explicit, deterministic, dimensionally valid, and provenance-aware where it affects exported or computed values.

A pure scale conversion between verified equivalent units does not invent new scientific information. Whether it is represented as the same `SOURCE` result with canonicalized units or as an explicit transformation is an implementation policy to be fixed consistently in `API_PLUGIN_CONTRACT.md`/tests.

It must never become an untraceable silent reinterpretation.

### 15.4 No unit-library lock-in

This contract does not mandate Pint, Astropy Units, unyt, or another units package.

The chosen implementation must support the required dimensional validation without leaking a mandatory third-party unit type into the stable public scientific meaning unless deliberately approved.

---

## 16. Evidence classes

`EvidenceClass` has exactly the five binding values established by `DESIGN_CONTRACT.md`.

### 16.1 `SOURCE`

A value represented directly by the canonical upstream dataset after faithful parsing and scientifically lossless normalization.

### 16.2 `RECONSTRUCTED`

A value recovered deterministically from source quantities through an authoritative identity/definition that does not add a fitted or external physical model.

The exact reconstruction method must be registered and cited. The existence of a plausible formula is not enough.

### 16.3 `DERIVED`

A value computed from source/reconstructed/derived inputs using an explicit deterministic scientific transformation.

Examples include registered signal features or transformations, provided their definitions are explicit.

### 16.4 `INFERRED`

A value estimated statistically from a population, cohort, resampling procedure, fitted relationship, or other inferential method.

An `INFERRED` result must preserve the population/cohort and method context required to interpret it.

### 16.5 `MODELLED`

A value predicted by a declared scientific model or research operator whose output is not source truth.

External haemodynamic theories, constitutive models, susceptibility models, fractional models, and similar research formulations normally produce `MODELLED` outputs unless a different classification is specifically justified by the registered operation.

### 16.6 Evidence propagation is explicit

Evidence class is not determined by taking the "highest" or "lowest" label in a generic hierarchy.

Each registered transformation/operator declares the scientific status of its output based on what the method does.

A result using `SOURCE` inputs can still be `MODELLED` or `INFERRED`.

---

## 17. Provenance record

### 17.1 Purpose

A `ProvenanceRecord` answers: **what exactly produced this result?**

It must be serializable and sufficiently stable for reproduction checks.

### 17.2 Minimum provenance content

Depending on result type, provenance may contain:

- dataset identity;
- source artifact identifiers/checksums;
- schema version;
- subject/cohort identity;
- vascular-location selection;
- source fields/signals;
- input result identities;
- transformation/derivation/operator/discovery method identifier;
- implementation/package/plugin version;
- parameters;
- assumptions;
- random seed or random-state identity when applicable;
- software environment identifiers where material;
- warnings/admissibility results;
- citations;
- output identity/hash where useful.

### 17.3 Provenance graph semantics

A result may depend on multiple prior results. Provenance therefore forms a directed acyclic lineage for a completed computation.

The implementation does not require a graph database.

Cycles in provenance dependencies indicate an invalid completed-result lineage and must be rejected or resolved before serialization.

### 17.4 Content identity versus storage identity

A source file path is not scientific provenance by itself.

Canonical checksum/artifact identity determines source identity. A local path, mirror URL, cache key, or temporary filename is operational metadata.

---

## 18. Missingness and validity

The model must distinguish at least the following meanings where they occur:

- **missing** — a value should exist in the scientific structure but is absent;
- **unavailable** — required source capability/artifact is not locally/operationally available;
- **not applicable** — the quantity is not scientifically defined for that entity/context;
- **invalid** — a value or computation fails a declared validity rule;
- **not evaluated** — a method/validity test has not been run.

A numeric `NaN` may be a storage representation for some of these states, but `NaN` alone must not define their scientific semantics.

Discovery/statistical methods must declare their missing-data policy rather than silently applying implementation defaults.

---

## 19. Scientific admissibility and warnings

A method may declare an admissible or validated domain.

A computation may therefore complete numerically while remaining scientifically limited.

VascuQuest should be able to represent at least:

```text
valid/in-domain
valid-with-warning
out-of-declared-domain
invalid-input
numerical-failure
not-evaluated
```

These states are not evidence classes. They describe applicability/validity of a result.

A `MODELLED` result outside its declared validation domain remains `MODELLED`; it also carries the relevant admissibility warning.

---

## 20. Derivation semantics

A derivation is a registered deterministic scientific transformation.

It declares:

- canonical identifier/version;
- required input quantities;
- input units/dimensions;
- required coordinate/location context;
- output quantity definition;
- output evidence class;
- parameters and defaults;
- missing-data policy;
- citations/definition source;
- validation scope.

A derivation must not discover source fields by filename or column name. It receives canonical scientific inputs through the application/domain boundary.

If two algorithms calculate nominally similar metrics but use different definitions, they are distinct derivations unless equivalence is established.

---

## 21. Research-operator semantics

A research operator introduces an explicit scientific model beyond direct source interpretation.

It must declare:

- operator identity/version;
- required canonical inputs;
- produced canonical or operator-scoped outputs;
- units/dimensions;
- assumptions;
- parameter definitions;
- admissible/validated domain;
- citations;
- evidence class, normally `MODELLED`;
- deterministic/random behaviour;
- provenance requirements.

Research operators may implement specialized formulations, including those developed in independent research papers, without forcing their notation or equations into VascuQuest core.

### 21.1 Operator-scoped quantities

An operator may introduce scientifically legitimate quantities not present in the dataset.

Such a quantity must have a definition namespace tied to the operator/plugin so it cannot collide silently with a source or canonical dataset quantity.

If a quantity later becomes broadly accepted across backends/operators, it may be promoted to the canonical schema only through an explicit schema change and scientific review.

### 21.2 No equation laundering

A mathematical expression copied into code does not become scientifically valid merely because it executes.

Every operator equation must be traceable to its authoritative definition or an explicitly documented new derivation, and must have dimensional/limiting/reference tests appropriate to that formulation.

---

## 22. Discovery-result semantics

A discovery method operates on canonical scientific data/cohorts and produces an auditable result.

A discovery result may contain:

- selected features/quantities;
- cohort/subgroup definitions;
- associations;
- estimated effects;
- clusters/phenotypes;
- outliers/counterexamples;
- sensitivities;
- low-dimensional representations;
- ranking or screening results;
- uncertainty/validation information.

The method determines the evidence class of quantities it produces.

Rules:

1. exploratory results are labelled exploratory where applicable;
2. statistical estimates are normally `INFERRED`;
3. deterministic grouping or sorting is not automatically `INFERRED` merely because it occurs in the discovery subsystem;
4. virtual-population association is not automatically human causation;
5. multiplicity, resampling, held-out validation, and uncertainty information must remain available when the method uses them;
6. a discovery result must preserve the exact cohort definition and method parameters.

---

## 23. Source, derived, and external-theory boundaries

The scientific model recognizes three different questions:

### 23.1 What did PWDB store?

Answer through canonical `SOURCE` quantities backed by verified artifacts.

### 23.2 What can be deterministically calculated from PWDB?

Answer through registered `RECONSTRUCTED` or `DERIVED` operations with explicit definitions.

### 23.3 What does an external scientific theory predict for PWDB subjects?

Answer through a research operator producing `MODELLED` outputs.

These three questions must remain distinguishable in every result and export.

---

## 24. Scientific relationships

The minimum relationship model is:

```text
DatasetIdentity
    contains -> VirtualSubject

VirtualSubject
    has -> source/canonical attributes and quantities
    may have -> Geometry
    may expose -> MeasurementSite
    may expose -> ArterialPath
    has -> plausibility metadata where available

Cohort
    selects -> VirtualSubject(s) from one DatasetIdentity

SegmentLocation
    participates in -> vascular topology

MeasurementSite
    may map to -> SegmentLocation / source position

ArterialPath
    traverses -> ordered SegmentLocation(s)
    contains -> PathPosition(s)

ScientificResult
    refers to -> QuantityDefinition
    is contextualized by -> subject/cohort/location/coordinates
    carries -> EvidenceClass
    carries -> ProvenanceRecord

Waveform
    is a -> time-resolved ScientificResult

Derivation / ResearchOperator / DiscoveryMethod
    consumes -> canonical ScientificResult(s)
    produces -> ScientificResult(s) and/or DiscoveryResult
```

These are semantic relationships, not database-table prescriptions.

---

## 25. Identity and equality rules

### 25.1 Subject equality

Two subject references are identical only when dataset identity and canonical subject identifier match.

### 25.2 Quantity-definition equality

Canonical quantity identity includes schema namespace/version semantics, not display label alone.

### 25.3 Location equality

Two vascular locations are equal only when location kind and canonical location identity match within the relevant dataset/backend namespace.

A measurement site and a path position do not become equal merely because they correspond anatomically.

### 25.4 Result equality

Numerical equality is not sufficient for scientific-result equality.

Two results may contain the same numbers but differ in:

- units;
- evidence class;
- subject/cohort context;
- location;
- method;
- provenance;
- validity scope.

The exact programmatic equality semantics are deferred to implementation; scientific comparison utilities should compare the dimensions relevant to the use case rather than relying on object identity.

---

## 26. Naming and namespaces

Canonical scientific names should be:

- stable;
- machine-readable;
- semantically specific;
- independent of one source filename;
- documented with aliases.

Recommended conceptual namespaces are:

```text
pwdb/source-mapped canonical quantities
vascuquest/general derivations
plugin-or-operator scoped quantities
```

The final serialization syntax is deferred to `API_PLUGIN_CONTRACT.md`.

Display names may be concise, but machine identities must prevent collisions.

---

## 27. Serialization boundary

Scientific objects/results must be serializable into machine-readable forms sufficient for:

- CLI structured output;
- result export;
- provenance persistence;
- reproducibility checks;
- plugin interchange at the public-contract level.

Serialization must not require embedding multi-gigabyte numerical arrays directly inside provenance records.

Large values may be referenced by stable result/artifact identities where appropriate.

The scientific model does not require JSON as the only serialization format, but core metadata/provenance must have a portable representation.

---

## 28. Performance implications of the scientific model

Scientific semantics must not force inefficient data materialization.

Therefore:

1. a `VirtualSubject` object must not load all subject waveforms on construction;
2. a `Cohort` must be able to represent thousands of subject IDs without copying all source data;
3. a `Waveform` may wrap or reference lazily obtained data while it remains open/valid under the API contract;
4. requesting metadata must not materialize path-resolved signals;
5. provenance must reference source identities rather than duplicate source arrays;
6. canonical quantity definitions are lightweight metadata and may be cached eagerly;
7. large cohort results may be streamed/batched where the operation permits.

The exact lazy-array mechanics remain an implementation/data-engineering decision.

---

## 29. Extensibility requirements

The model is considered extensible only if the following can occur without changing the meaning of existing objects:

- a second validated vascular-population backend is added;
- a new canonical quantity is added to a schema version;
- a new derivation is installed;
- a new research operator introduces operator-scoped quantities;
- a new discovery method consumes existing canonical results;
- a future backend contains different vascular sites or topology;
- a future backend adds pathological or treatment-modified virtual populations.

Extensibility does not mean every future concept must fit without schema evolution. It means extension occurs through explicit versioned contracts rather than by silently changing existing meaning.

---

## 30. Explicit scientific non-goals

VascuQuest v1 scientific core will not:

- claim clinical validity;
- treat the virtual population as epidemiological ground truth;
- imply causal human ageing trajectories from age-stratified simulations;
- infer disease from haemodynamic patterns;
- invent absent vascular geometry;
- collapse site, segment, and path-position identities;
- hide physiological plausibility filtering;
- treat source pulse-wave indices and independently recomputed indices as identical without validation;
- label model predictions as source observations;
- embed project-specific equations into the core ontology;
- create one Python class for every scientific variable;
- force all numerical values into one universal table shape;
- require all plugins to use internal backend objects;
- assume all datasets will share PWDB's exact artery names or simulation design.

---

## 31. Implementation invariants

The following rules must remain true in code.

1. Every scientific result has an identifiable quantity/meaning.
2. Every material scientific result can expose its evidence class.
3. Every nontrivial transformed/modelled/inferred result has provenance identifying its method and inputs.
4. Dataset identity accompanies subject identity.
5. A cohort cannot silently span incompatible dataset identities in v1.
6. Subject age is not used as implicit longitudinal identity.
7. Site, segment, path, and path position remain distinct location concepts.
8. Raw source labels remain traceable through the schema.
9. Source metadata defects are not repaired by modifying upstream files.
10. Missing/unavailable/not-applicable/invalid states are not intentionally conflated.
11. Plausibility filters are explicit and reproducible.
12. Scientific transformations do not occur inside source parsers merely for convenience.
13. Operator-scoped quantities cannot silently shadow canonical source quantities.
14. A source-backed result does not become `MODELLED` merely because it is accessed through an operator workflow; output classification follows the actual operation.
15. A modelled result does not become `SOURCE` because its numerical value agrees with source data.
16. No mathematical equation enters the core implementation without an owning registered method, authoritative definition, and validation tests.

---

## 32. Minimal acceptance scenarios

### Scenario A — inspect one virtual subject

A researcher opens PWDB `3275625`, selects one subject, inspects age/configuration/plausibility metadata, and lists available quantities without loading large waveform/path artifacts.

Expected semantics:

- subject identity includes dataset identity;
- attributes are canonical/schema-backed;
- unavailable capabilities are distinguishable from missing values.

### Scenario B — build a cohort

A researcher selects subjects by age plus an explicit plausibility criterion.

Expected semantics:

- selection definition is preserved;
- resulting subject IDs are deterministic;
- the cohort does not imply a human observational cohort.

### Scenario C — retrieve a source waveform

A researcher obtains a pressure waveform for one subject at a supported measurement site.

Expected semantics:

- signal and site identities are canonical;
- time/sampling context is present;
- unit is present;
- evidence is `SOURCE`;
- provenance identifies the canonical artifact/field representation.

### Scenario D — request a registered derivation

A researcher applies a deterministic registered signal transformation to the waveform.

Expected semantics:

- the original source waveform is unchanged;
- method identity/parameters are recorded;
- the new result receives the evidence class declared for that derivation;
- units/dimensions are validated.

### Scenario E — run a research operator

A specialized arterial-mechanics plugin receives canonical PWDB inputs and computes an operator-defined response quantity.

Expected semantics:

- operator equations/parameters remain owned by the plugin;
- output quantity is namespaced and defined;
- evidence is `MODELLED` unless the operator contract justifies otherwise;
- assumptions/admissibility/citations are retained;
- no operator notation contaminates source-variable definitions.

### Scenario F — compare source and modelled results

A researcher compares a source quantity with a model prediction.

Expected semantics:

- numerical comparison is allowed;
- evidence classes remain distinct;
- agreement does not merge their provenance or identity.

### Scenario G — path-resolved analysis

A researcher requests one signal along an arterial path.

Expected semantics:

- path identity and path coordinate are explicit;
- path positions may map to segments without becoming interchangeable with segment identities;
- no interpolation is implied unless a derivation performs it.

### Scenario H — future backend

A future vascular-population backend has a different network and different source files.

Expected semantics:

- it can expose subjects, canonical quantities, locations, geometry, waveforms, cohorts, evidence, and provenance without imitating PWDB filenames or MATLAB structures.

---

## 33. Audit checklist

`SCIENTIFIC_MODEL.md` passes only if all answers are **yes**.

### Source fidelity

- Is a virtual subject clearly represented as a simulation instance rather than a patient?
- Are source attributes and quantities mapped through the canonical schema rather than invented core fields?
- Are site, segment, geometry, and path concepts kept faithful to what the backend/source can establish?
- Is physiological plausibility retained rather than silently filtering the population?

### Mathematical fidelity

- Does the core avoid introducing equations it does not own?
- Are equations delegated to registered derivations/operators with authoritative definitions and tests?
- Are project-specific theoretical quantities prevented from becoming accidental source truth?
- Are unit/dimensional checks required for every mathematical method that needs them?

### Simplicity

- Is the conceptual model small enough to implement with ordinary Python value objects and result containers?
- Does it avoid one-class-per-variable design?
- Does it avoid requiring a knowledge graph, ontology server, graph database, or universal dataframe type?
- Are categories expressed through schema metadata where classes would add no behaviour?

### Completeness

- Can the model express subjects, cohorts, quantities, waveforms, geometry, locations, evidence, provenance, derivations, operators, and discovery outputs?
- Can missingness, validity, and admissibility be represented distinctly?
- Can source, reconstructed, derived, inferred, and modelled science coexist without ambiguity?

### Feasibility

- Can subject/cohort/location metadata remain lightweight and lazy with respect to large data?
- Can large numerical arrays remain backend-managed while scientific metadata stays stable?
- Does the model avoid requiring conversion of the full dataset into an object graph?

### Scientific integrity

- Is age prevented from becoming an implicit longitudinal-person identity?
- Are virtual-population associations prevented from becoming automatic human causal claims?
- Are source and recomputed quantities distinguishable?
- Are operator-scoped outputs prevented from shadowing canonical source quantities?

### Architecture compatibility

- Does the model remain independent of Zenodo filenames, MAT/HDF5/WFDB reader objects, and CLI frameworks?
- Can ports/services use these semantics without importing concrete backends?
- Can plugins consume canonical inputs without receiving PWDB-specific storage objects?

If any answer is no, this file must be amended before proceeding to `API_PLUGIN_CONTRACT.md`.

---

## 34. Approval consequence

Once this contract passes audit:

- the scientific identity and relationship model is frozen for v1;
- evidence/provenance semantics are fixed;
- subject/cohort/location interpretation rules are fixed;
- mathematical theories remain outside the core and enter through registered scientific methods/operators;
- exact Python signatures and plugin protocol shapes remain to be defined in `API_PLUGIN_CONTRACT.md`.

The next contract after approval is `API_PLUGIN_CONTRACT.md`.

---

## 35. Reference hierarchy

When scientific meaning is ambiguous, implementation must use the following authority order:

1. verified canonical source data and authoritative upstream dataset documentation/code for source semantics;
2. VascuQuest versioned canonical schema and documented source-defect resolutions;
3. the governing VascuQuest design/data/scientific contracts;
4. authoritative publication/definition for a registered derivation or research operator;
5. implementation convenience only after the above constraints are satisfied.

Implementation convenience may never override a known scientific definition.