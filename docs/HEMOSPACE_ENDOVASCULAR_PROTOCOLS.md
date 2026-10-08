# HEMOSPACE Endovascular Research Protocols

These are reproducible mechanistic study templates for virtual endovascular research in VascuQuest 1.0. They are not clinical trial protocols and do not establish treatment efficacy.

## Common v1 workflow for all protocols

Every protocol below should follow the same research sequence unless the question requires only a subset:

```text
HEMOSPACE phenotype / deterministic cohort
        ↓
existing or newly generated Virtual Disease counterfactuals
        ↓
verified healthy ↔ modelled disease alignment
        ↓
vascuquest.mechanics and/or vascuquest.spectral
        ↓
vascuquest.stats
        ↓
vascuquest.plot
```

Core rules:

- preserve canonical subject IDs throughout;
- use persisted disease bundles whenever they already exist rather than rerunning the solver;
- use `vascuquest.analysis` compatibility/alignment checks before multi-result analysis;
- distinguish HEMOSPACE-native summary quantities from dedicated `mechanics`/`spectral` method outputs;
- keep paired healthy/disease analyses paired by canonical identity;
- interpret cohort frequencies as properties of the designed PWDB population, not epidemiology;
- retain method IDs, assumptions, evidence classes and warnings;
- generate statistical annotations explicitly before plotting;
- never silently thin large cohorts in figures.

## Protocol 1 — Baseline arterial stiffness as an effect modifier of carotid stenosis

**Question:** Does baseline arterial stiffness alter the haemodynamic consequence of the same carotid stenosis?

**Cohort construction:** stratify by `arterial_stiffness_variation` while keeping the disease specification identical across selected subjects.

Example:

```bash
vascuquest hemospace cohort select \
  -c 'arterial_stiffness_variation>=1' \
  --profile carotid-stenosis \
  --describe
```

Recommended baseline descriptors:

- simulation age;
- cardiac output;
- mean pressure;
- systemic resistance;
- cfPWV;
- carotid diameter;
- DIA/HR/SV/MBP/PWV design coordinates.

After generating or loading a Virtual Disease cohort with identical carotid stenosis settings, use:

```bash
vascuquest hemospace response --subject <ID> --bundle <bundle>
```

Candidate endpoints:

- carotid pressure/flow/velocity change;
- pulse-pressure change;
- distal pressure change;
- reverse-flow change;
- hydraulic-energy change;
- local area distensibility/compliance where aligned P/A are available;
- pressure-flow impedance or harmonic changes where aligned P/Q are available.

Recommended inference:

- paired healthy/disease comparison for direct response endpoints;
- effect-modifier regression using baseline stiffness/design coordinates;
- multiplicity correction if several pre-specified endpoints are tested.

Do not report stroke risk, plaque vulnerability or treatment efficacy.

## Protocol 2 — Small-diameter phenotype and iliac stenosis burden

**Question:** Are smaller large-artery diameter phenotypes more sensitive to an identical iliac stenosis?

Example enriched cohort:

```bash
vascuquest hemospace cohort select \
  -c 'large_artery_diameter_variation<=-1' \
  --profile iliac-stenosis \
  --describe
```

Useful covariates:

- SVR;
- MBP;
- CO;
- femoral-ankle PWV;
- ankle pressure drop;
- PVC variation;
- PWV variation.

Candidate response endpoints:

- common-iliac/femoral flow change;
- distal pressure change;
- reverse-flow fraction;
- local hydraulic-energy transport;
- local pressure-flow impedance change;
- waveform harmonic redistribution.

For cohort inference, preserve healthy/disease subject pairing and test the declared phenotype modifier rather than comparing anonymous row vectors.

Do not convert these results into a clinical ischemia diagnosis or intervention threshold.

## Protocol 3 — Systemic physiology and idealized fusiform AAA response

**Question:** Which baseline systemic phenotypes alter the one-dimensional haemodynamic response to the same idealized AAA geometry?

Suggested strata:

- high vs low PWV variation;
- high vs low mean-pressure variation;
- high vs low SV variation;
- large vs small diameter variation;
- long vs short proximal-aortic-length variation.

Useful source endpoints:

- abdominal-aortic pressure;
- abdominal-aortic pulse pressure;
- flow/velocity;
- area pulsatility;
- central-to-peripheral amplification.

Useful derived endpoints:

- area strain;
- area compliance/distensibility;
- pressure-area loop integral;
- flow pulsatility;
- hydraulic power/energy;
- pressure-flow impedance;
- harmonic-energy changes.

Use the dedicated `vascuquest.mechanics` or `vascuquest.spectral` namespace when the research question requires a standardized v1 method result rather than the concise HEMOSPACE record summary.

Do not report wall shear stress, sac recirculation, intraluminal thrombus or rupture risk from HEMOSPACE/Virtual Disease v1.

## Protocol 4 — Baseline compliance and response to large-artery stiffening

**Question:** Which source physiological dimensions predict the greatest system-wide haemodynamic response to a fixed large-artery stiffening intervention?

Example:

```bash
vascuquest hemospace cohort select \
  -c 'peripheral_vascular_compliance_variation<=-1' \
  --profile large-artery-stiffening \
  --describe
```

Primary mechanistic endpoints:

- central pulse pressure;
- brachial pulse pressure;
- pulse-pressure amplification;
- augmentation measures;
- wave transit timing;
- flow pulsatility;
- hydraulic energy;
- local area distensibility / beta stiffness;
- Bramwell-Hill wave-speed estimate under its declared assumptions;
- impedance or wave-intensity changes.

Do not relabel model response as arterial-age diagnosis or future event risk.

## Protocol 5 — Worst-case physiological corner search

**Question:** Which existing PWDB design-space corners produce the most severe response to a fixed disease transformation?

Method:

1. define a transparent phenotype envelope using exact HEMOSPACE criteria;
2. preserve the resulting `selection_id`;
3. run the same disease definition for all selected subjects or load an existing compatible bundle;
4. use HEMOSPACE response records and/or standardized v1 analysis methods to calculate a declared endpoint;
5. rank only the pre-declared endpoint or explicitly label exploratory ranking;
6. report the generative axes associated with high-response subjects;
7. use ECDF/hexbin/scatter rendering without silently selecting “representative” subjects.

Example selection:

```bash
vascuquest hemospace cohort select \
  -c 'arterial_stiffness_variation>=1' \
  -c 'large_artery_diameter_variation<=-1' \
  -c 'mean_blood_pressure_variation>=1' \
  --describe
```

The result is a mechanistic boundary-case search within the represented PWDB design space, not a prediction of population frequency.

## Protocol 6 — Endpoint-selection study before an in-silico trial

**Question:** Which haemodynamic endpoints provide the strongest, most interpretable response signal for a planned Virtual Disease study?

Method:

1. select a heterogeneous HEMOSPACE cohort;
2. inspect comprehensive healthy records;
3. identify endpoints with acceptable source coverage and physiological meaning;
4. use an existing disease bundle to generate paired response records;
5. compute standardized mechanics/spectral descriptors where scientifically warranted;
6. compare effect magnitude, direction consistency, missingness and assumption validity;
7. freeze the endpoint panel before larger cohort execution.

Candidate endpoint families:

- direct source pressure/flow/velocity indices;
- pulse pressure and amplification;
- transit timing;
- waveform pulsatility;
- reverse-flow fraction;
- area strain/compliance/distensibility;
- pressure-area loop/stiffness descriptors;
- pressure-flow impedance/wave-intensity descriptors;
- hydraulic energy.

Avoid selecting endpoints solely because they maximize a statistical difference. Require a mechanistic interpretation and an explicit evidence chain. Exploratory screening and confirmatory testing should be labeled separately.

## Protocol 7 — Path-resolved propagation phenotype

**Question:** How does pressure/velocity/area propagation along a canonical arterial path differ across baseline phenotypes?

Example:

```bash
vascuquest hemospace path --subject 2104 --path aorta_brain
```

Potential descriptors:

- apparent path PWV;
- onset-time progression;
- path pressure-pulse amplification;
- spatial trend of flow/area amplitude;
- path-wise harmonic amplitude/phase evolution;
- position-wise pressure-area mechanics where aligned source P/A are available.

Only stored source-supported path positions may be analyzed. Do not create an apparently continuous field by silently interpolating unstored positions.

The path reader is qualified under `QUALIFIED_AUTHORITATIVE_EXPORTER_CONTRACT`. Publication-quality use should retain the canonical PWDB DOI and artifact checksum as ordinary provenance, but no separate multi-gigabyte reader-qualification run is required. See `HEMOSPACE_PATH_QUALIFICATION.md`.

## Protocol 8 — Reproducible subgroup/effect-modifier analysis

**Question:** Is a disease response associated with one prescribed PWDB design axis after controlling the study design for other axes?

Minimum reporting:

- exact inclusion criteria;
- exact canonical IDs;
- subject count;
- design coordinates used as effect modifiers;
- disease condition and parameters;
- paired endpoint definition;
- evidence class;
- analysis method and covariates;
- statistical seed/resample count where relevant;
- multiplicity handling where relevant;
- missing-data handling;
- HEMOSPACE closure status.

The preferred scientific statement is mechanistic, e.g.:

> Within the represented PWDB design space, increased prescribed arterial stiffness was associated with a larger modelled pressure response to the fixed stenosis transformation.

Avoid clinical language such as “patients with stiff arteries have higher stroke risk” unless supported by independent clinical evidence outside HEMOSPACE.

## Protocol 9 — Paired mechanics-response study

**Question:** How does a controlled disease intervention change local vascular mechanics in matched virtual subjects?

Method:

1. identify a common measurement site with aligned healthy and modelled P/A waveforms;
2. compute a pre-declared mechanics descriptor for every canonical subject using `vascuquest.mechanics`;
3. preserve the subject ID on each derived result;
4. assemble aligned healthy and disease cohort vectors;
5. perform a paired comparison with `vascuquest.stats`;
6. visualize paired changes or effect-modifier relationships using `vascuquest.plot`.

Appropriate endpoints may include area distensibility, compliance, beta stiffness, Peterson modulus, Bramwell-Hill wave-speed estimate, or pressure-area loop integral subject to their assumptions.

Do not call these changes measured tissue remodeling or clinical treatment response.

## Protocol 10 — Paired wave/spectral-response study

**Question:** How does a controlled disease intervention redistribute pulsatile information or wave behavior?

Method:

1. choose a pre-declared subject/location and waveform pair;
2. compute harmonics, impedance, wave separation, wave intensity, coherence/transfer or time-frequency output using the correct input contract;
3. reduce a spectrum to a declared subject-level endpoint if cohort inference is planned;
4. preserve subject identity and method parameters;
5. compare matched healthy/modelled endpoints statistically;
6. plot raw spectra and cohort-level response separately so frequency bins from one subject are not treated as independent subjects.

Do not infer causal physiology from coherence/transfer alone or clinical disease severity from spectral entropy/harmonic ratios.

## Reproducible publication package

For any protocol, retain as applicable:

- PWDB DOI/artifact checksums;
- HEMOSPACE criteria, profile and `selection_id`;
- exact canonical subject IDs;
- Virtual Disease plan/run/bundle identity;
- disease parameters and solver execution identity;
- native result JSON files;
- mechanics/spectral method IDs and assumptions;
- statistical method IDs, parameters and seeds;
- figure-spec JSON;
- rendered SVG/PDF/PNG;
- VascuQuest version;
- explicit non-claims/interpretation boundary.

This package makes the study reproducible without treating a rendered plot or an anonymous table as the scientific source of truth.
