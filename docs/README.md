# VascuQuest documentation

This directory contains the current normative and subsystem documentation for **VascuQuest 1.0**, an in-silico vascular research platform built around PWDB, HEMOSPACE, Virtual Disease, qualified analysis, vascular mechanics, spectral/wave analysis, and reproducible scientific plotting.

A VascuQuest `VirtualSubject` is a simulation instance, not a patient. All current documentation preserves the evidence model `SOURCE / RECONSTRUCTED / DERIVED / INFERRED / MODELLED` and the architectural rule that new analysis layers consume existing VascuQuest scientific objects without mutating PWDB source semantics, HEMOSPACE semantics, or qualified Virtual Disease physics.

## Documentation synchronization status

The current documentation set was synchronized against the `feature/v1-platform` VascuQuest 1.0 release candidate in PR #25 after implementation of the five-pass research-platform program.

The synchronization rule is:

- **governing/current docs** describe the actual VascuQuest 1.0 platform and current public contracts;
- **qualification docs** preserve the exact scope and wording of the evidence they qualify, even when the platform later gains unrelated capabilities;
- **`docs/evidence/**`** is immutable machine-readable qualification evidence;
- **`docs/history/**`** is superseded historical planning/audit material and must not be used as the current product contract.

Where a frozen qualification record contains an older qualification-state label, that label remains evidence metadata for that frozen test lineage; it must not be generalized into a broader present-day claim about unrelated v1.0 subsystems.

## Governing v1.0 contracts

- [`BUILD_PLAN.md`](BUILD_PLAN.md) — current v1.0 release boundary, validation strategy, and release state.
- [`DESIGN_CONTRACT.md`](DESIGN_CONTRACT.md) — non-negotiable product, scientific, provenance, and interpretation constraints.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — package architecture, subsystem ownership, and dependency direction.
- [`DATA_ENGINEERING.md`](DATA_ENGINEERING.md) — canonical PWDB source identity, integrity, acquisition, storage, and path-data rules.
- [`SCIENTIFIC_MODEL.md`](SCIENTIFIC_MODEL.md) — scientific vocabulary, result model, subject/cohort semantics, evidence classes, and analysis semantics.
- [`API_PLUGIN_CONTRACT.md`](API_PLUGIN_CONTRACT.md) — public Python namespaces, extension boundaries, and plugin contracts.
- [`CLI_CONTRACT.md`](CLI_CONTRACT.md) — top-level CLI groups, output conventions, and API/CLI parity rules.
- [`TEST_VALIDATION_CONTRACT.md`](TEST_VALIDATION_CONTRACT.md) — validation tiers, fast qualification, real-source evidence, and release gates.
- [`V1_RESEARCH_PLATFORM.md`](V1_RESEARCH_PLATFORM.md) — end-to-end v1 research workflow and subsystem integration.

## Analysis and research layers

- [`ANALYSIS.md`](ANALYSIS.md) — common scientific-result analysis contract, identity/alignment rules, deterministic analysis provenance, and controlled external-data entry.
- [`STATS.md`](STATS.md) — qualified statistical/probabilistic analyses and subject/cohort alignment rules.
- [`VASCULAR_MECHANICS.md`](VASCULAR_MECHANICS.md) — pressure-area mechanics and qualified wave-mechanics derivations; this is not an FSI solver.
- [`SPECTRAL_ANALYSIS.md`](SPECTRAL_ANALYSIS.md) — Fourier, impedance, wave-separation, wave-intensity, coherence, transfer, and time-frequency methods.
- [`PLOTTING.md`](PLOTTING.md) — declarative publication-grade figures, compound panels, insets, large-cohort rendering, and collision-free exterior legends.

The canonical research flow is:

```text
PWDB / persisted Virtual Disease / external wrapped result
        ↓
ScientificResult / Waveform
        ↓
analysis identity + alignment contract
        ↓
mechanics and/or spectral derivation
        ↓
qualified statistics
        ↓
declarative plotting
        ↓
reproducible result JSON + figure-spec JSON + figure
```

None of these downstream operations implicitly reruns Virtual Disease or changes an upstream evidence class.

## HEMOSPACE

- [`HEMOSPACE.md`](HEMOSPACE.md) — Virtual Cardiovascular Record operation mode and public use.
- [`HEMOSPACE_AGENT.md`](HEMOSPACE_AGENT.md) — machine/agent scientific contract and forbidden gap filling, including use of the v1 analysis stack.
- [`HEMOSPACE_QUANTITY_CATALOGUE.md`](HEMOSPACE_QUANTITY_CATALOGUE.md) — source and HEMOSPACE-native derived knowledge catalogue, with ownership boundaries relative to `mechanics` and `spectral`.
- [`HEMOSPACE_ENDOVASCULAR_PROTOCOLS.md`](HEMOSPACE_ENDOVASCULAR_PROTOCOLS.md) — phenotype-driven research protocols using the final v1 analysis workflow.
- [`HEMOSPACE_KNOWLEDGE_CLOSURE.md`](HEMOSPACE_KNOWLEDGE_CLOSURE.md) — source-coverage and knowability closure.
- [`HEMOSPACE_PATH_QUALIFICATION.md`](HEMOSPACE_PATH_QUALIFICATION.md) — qualified MATLAB-v7.3/HDF5 path-reader contract and its explicit qualification boundary.

HEMOSPACE remains the comprehensive phenotype/knowledge layer. The v1 `mechanics`, `spectral`, `stats`, and `plot` namespaces consume HEMOSPACE/core scientific results downstream; they do not expand what PWDB itself knows.

## Virtual Disease

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md) — complete v1 mechanistic disease subsystem, scientific meaning, quantity-status boundary, and downstream integration.
- [`VIRTUAL_DISEASE_PUBLIC.md`](VIRTUAL_DISEASE_PUBLIC.md) — current Python/CLI surface, runtime bundles, and cohort commands.
- [`VIRTUAL_DISEASE_PHYSICS.md`](VIRTUAL_DISEASE_PHYSICS.md) — causal disease transformations, anatomy, equations, admissibility, and limitations.
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md) — healthy baseline reconstruction/forward-solver foundation and qualification boundary.
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md) — runtime `PWDB-VD` population, quantity-status, execution-identity, and bundle semantics.
- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md) — parameterized disease cohorts, designed-counterfactual interpretation, and v1 downstream analysis.
- [`PARAMETERIZED_COHORT_QUALIFICATION.md`](PARAMETERIZED_COHORT_QUALIFICATION.md) — deterministic planner, full-network persistence, resume/integrity, and cohort qualification boundary.
- [`JAX_VIRTUAL_DISEASE_QUALIFICATION.md`](JAX_VIRTUAL_DISEASE_QUALIFICATION.md) — bounded scalar JAX backend qualification tied to the machine-readable evidence certificate.

Virtual Disease remains the sole owner of disease-state generation. The research-analysis stack operates on already materialized/persisted disease outputs and must not mutate disease physics or silently initiate a solver run.

## Qualification evidence and historical records

`docs/evidence/` contains immutable machine-readable qualification evidence. `docs/history/` contains superseded planning documents retained only for auditability. Historical files are not current product contracts and must not override the governing v1.0 documents listed above.

The historical PR #20 static closure audit still names the legacy `PARAMETERIZED_COHORT_QUALIFICATION.md` path because that filename was part of the frozen closure diff. The current human-readable qualification documents provide the present-day separation between JAX-backend evidence and parameterized-cohort qualification.

## Current platform boundary

VascuQuest 1.0 supports canonical PWDB access, provenance-aware scientific results, HEMOSPACE records and cohorts, qualified lazy dense-path access, mechanistic Virtual Disease populations, statistics, vascular mechanics, spectral/wave analysis, and declarative research figures.

It does **not** claim clinical validation, patient digital twins, epidemiological representativeness, patient-specific prognosis, treatment efficacy, patient-specific rupture/stroke/thrombosis risk, or a three-dimensional FSI/CFD solver.

## Documentation maintenance rule

Any future code change that alters a public scientific capability must update the corresponding current documentation in the same development cycle. A release candidate is documentation-incomplete if README, governing contracts, subsystem references, CLI/API documentation, and qualification-boundary wording disagree about current behavior.
