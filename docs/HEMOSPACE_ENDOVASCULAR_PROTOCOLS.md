# HEMOSPACE Endovascular Research Protocols

These are reproducible mechanistic study templates for virtual endovascular research. They are not clinical trial protocols and do not establish treatment efficacy.

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

After generating a Virtual Disease cohort with identical carotid stenosis settings, use:

```bash
vascuquest hemospace response --subject <ID> --bundle <bundle>
```

Candidate endpoints:

- carotid pressure/flow/velocity change;
- pulse-pressure change;
- distal pressure change;
- reverse-flow change;
- hydraulic-energy change.

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
- local hydraulic-energy transport.

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
- flow pulsatility;
- hydraulic power/energy.

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
- hydraulic energy.

Do not relabel model response as arterial-age diagnosis or future event risk.

## Protocol 5 — Worst-case physiological corner search

**Question:** Which existing PWDB design-space corners produce the most severe response to a fixed disease transformation?

Method:

1. define a transparent phenotype envelope using exact HEMOSPACE criteria;
2. preserve the resulting `selection_id`;
3. run the same disease definition for all selected subjects;
4. use HEMOSPACE response records to rank a declared endpoint;
5. report the generative axes associated with high-response subjects.

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
5. compare effect magnitude, direction consistency and missingness;
6. freeze the endpoint panel before larger cohort execution.

Candidate endpoint families:

- direct source pressure/flow/velocity indices;
- pulse pressure and amplification;
- transit timing;
- waveform pulsatility;
- reverse-flow fraction;
- area strain/compliance/distensibility;
- hydraulic energy.

Avoid selecting endpoints solely because they maximize a statistical difference; require a mechanistic interpretation and an explicit evidence chain.

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
- spatial trend of flow/area amplitude.

This protocol requires local real-source qualification of the multi-GB path reader before publication-quality use.

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
- missing-data handling;
- HEMOSPACE closure status.

The preferred scientific statement is mechanistic, e.g.:

> Within the represented PWDB design space, increased prescribed arterial stiffness was associated with a larger modelled pressure response to the fixed stenosis transformation.

Avoid clinical language such as "patients with stiff arteries have higher stroke risk" unless supported by independent clinical evidence outside HEMOSPACE.
