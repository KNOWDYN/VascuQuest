# Virtual Disease public interface

## Status

This document describes implementation stage **5 of 5** for VascuQuest Virtual Disease v1.

The implementation chain is now complete from frozen disease request through causal transformation, disease-aware cardiovascular solving, runtime population materialisation, public Python access, command-line generation, and explicit portable export.

The scientific qualification boundary is unchanged:

```text
EvidenceClass = MODELLED
healthy reconstruction gate = METRICS_ONLY_THRESHOLDS_NOT_FROZEN
clinical validation = false
```

A generated Virtual Disease subject is a counterfactual model state, not a clinical patient observation or diagnosis.

## Public Python API

Virtual Disease is available through the first-party namespace:

```python
import vascuquest as vq

population = vq.disease.generate_population(
    patients=5,
    age_group=50,
    condition="carotid_stenosis",
    parameters={
        "side": "left",
        "artery": "common_carotid",
        "nascet_stenosis": 0.6,
        "lesion_length_m": 0.02,
    },
    seed=17,
    source="/path/to/pwdb",
    offline=True,
)
```

Selected subjects retain their canonical PWDB subject numbers while belonging to a separate content-addressed `PWDB-VD` dataset identity.

The source PWDB subject and runtime disease subject therefore remain directly pairable:

```text
PWDB:3275625 / subject 431
PWDB-VD:<run-id> / subject 431
```

The canonical PWDB source artifacts are never modified.

## Public CLI

The command group is:

```text
vascuquest disease
├── presets
├── describe
└── generate
```

### Inspect the frozen presets

```bash
vascuquest disease presets --format json
```

Inspect one preset:

```bash
vascuquest disease describe carotid_stenosis --format json
```

The description reports parameter names, simple request bounds, assumptions, mechanistic implementation scope, citations, `MODELLED` evidence, and the absence of clinical validation.

### Generate a population

Carotid stenosis example:

```bash
vascuquest disease generate carotid_stenosis \
  --patients 5 \
  --age 50 \
  --param side=left \
  --param artery=common_carotid \
  --param nascet_stenosis=0.60 \
  --param lesion_length_m=0.02 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline \
  --format json
```

Iliac stenosis example:

```bash
vascuquest disease generate iliac_stenosis \
  --patients 5 \
  --age 50 \
  --param side=right \
  --param artery=external_iliac \
  --param diameter_stenosis=0.55 \
  --param lesion_length_m=0.03 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline
```

Fusiform AAA example:

```bash
vascuquest disease generate fusiform_abdominal_aortic_aneurysm \
  --patients 5 \
  --age 60 \
  --param maximum_diameter_m=0.03 \
  --param aneurysm_length_m=0.10 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline
```

Large-artery stiffening example:

```bash
vascuquest disease generate large_artery_stiffening \
  --patients 5 \
  --age 60 \
  --param target_cfpwv_m_per_s=12.0 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline
```

Subject-specific admissibility remains enforced by the disease physics layer. For example, a requested lesion must fit inside its eligible anatomy, a fusiform AAA must actually dilate the covered healthy aorta, and the stiffening target cannot be below a selected subject's baseline model-space cfPWV.

## Generation result

The primary command result reports:

- exact `PWDB-VD` dataset identity and run ID;
- exact parent PWDB identity;
- frozen disease condition and normalized parameters;
- requested patient count, age group and deterministic seed;
- preserved canonical PWDB subject IDs;
- quantity-status mapping;
- materialised quantities and measurement sites;
- result count per subject;
- final solver diagnostics per subject;
- explicitly unsupported disease-state quantities;
- `MODELLED` evidence;
- current healthy-reconstruction gate;
- clinical-validation status;
- whether the population exists only in process memory or was explicitly exported.

Operational/scientific warnings go to `stderr`, so `--format json` remains valid machine-readable JSON on `stdout`.

## Source acquisition safety

Runtime generation requires the canonical artifacts needed for:

```text
model configurations
subject vascular geometry
common-site waveforms / aortic inflow reconstruction
```

The CLI checks their local availability before simulation.

With `--offline`, missing required artifacts fail explicitly.

Without `--offline`, any required acquisition is announced before generation. Existing VascuQuest large/unknown-size confirmation rules apply; non-interactive execution requires `--yes` when confirmation is required.

## Explicit portable bundle export

Runtime populations are intentionally in-memory unless the user explicitly requests persistence.

To save one generated population:

```bash
vascuquest disease generate carotid_stenosis \
  --patients 5 \
  --age 50 \
  --param side=left \
  --param artery=common_carotid \
  --param nascet_stenosis=0.60 \
  --param lesion_length_m=0.02 \
  --seed 17 \
  --source /path/to/pwdb \
  --offline \
  --bundle ./vd-carotid-run
```

Existing destinations are never overwritten implicitly. Replacement requires:

```text
--overwrite
```

The bundle contains:

```text
manifest.json
results/<subject-id>/*.json
provenance/*.json
```

`manifest.json` records:

- runtime and parent dataset identities;
- disease request and run ID;
- subject IDs;
- quantity statuses;
- materialised quantities and sites;
- result/provenance counts;
- current qualification state and warnings;
- every exported file path and SHA-256 checksum.

Each result file uses the existing portable VascuQuest JSON scientific-result format. Each provenance file contains the full deterministic provenance record corresponding to the materialised result.

The bundle references canonical PWDB source artifacts through provenance identities/checksums; it does not copy or relicense the upstream PWDB data.

## Materialised v1 state

For every selected subject, runtime generation materialises:

- pressure `P` at all 13 canonical common sites;
- flow velocity `U` at all 13 canonical common sites;
- luminal area `A` at all 13 canonical common sites;
- volumetric flow `Q` at all 13 canonical common sites;
- age;
- heart rate;
- stroke volume;
- cardiac output;
- brachial systolic pressure;
- resolved disease-state vascular geometry/wall-mechanical model state.

The generated waveforms are sampled onto the corresponding parent PWDB cardiac-cycle time coordinate after the adaptive disease solve, enabling direct healthy-versus-disease vector comparison.

## Explicitly unsupported v1 state

The following are not silently copied from the healthy parent:

- photoplethysmogram;
- aortic pulse-wave velocity as a public disease-state result;
- aortic augmentation index;
- pressure-onset time.

Their runtime status is `NOT_SUPPORTED` until a disease-state method exists that can regenerate them consistently.

## Scientific scope

The four frozen v1 presets are mechanistic cardiovascular model interventions. They are useful for controlled counterfactual in-silico research with known intervention ground truth.

They do not claim to reproduce the complete biological state of real patients. In particular, the current implementation does not add closed-loop autonomic/baroreflex adaptation, patient-specific plaque morphology, three-dimensional separated flow, thrombus/remodelling, clinical tonometry, ultrasound physics, diagnostic interpretation, or clinical outcome prediction unless a later explicit model adds and qualifies those capabilities.

The public interface therefore preserves the same principle as the underlying implementation: disease generation is scientifically explicit, provenance-aware, deterministic, and visibly `MODELLED`.
