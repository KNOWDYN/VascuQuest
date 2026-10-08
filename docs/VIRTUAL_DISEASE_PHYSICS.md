# Virtual Disease causal physics

## 1. Purpose

This document defines the causal disease transformations used by the completed VascuQuest 1.0 Virtual Disease subsystem.

A disease request is applied to an immutable healthy `BaselineCardiovascularState` and produces a separate `DiseasePhysicsModel` containing:

- the unchanged healthy parent state;
- the canonical `DiseaseSpecification`;
- the transformed solver network;
- explicit localized excess pressure-loss terms where required;
- the exact modified PWDB segment IDs;
- assumptions and citations.

The disease layer changes model parameters/geometry causally and then relies on the disease-aware network solver to recompute haemodynamics. It never prescribes the desired output waveform.

## 2. Scientific boundary

Every disease-state result is mechanistic `MODELLED` evidence. The implemented transformations are research interventions in the PWDB-compatible one-dimensional model.

They are not clinical measurements, treatment simulations validated against patients, or three-dimensional CFD/FSI models.

## 3. Frozen source anatomy

Disease targets are defined from the canonical PWDB 116-artery input network, not inferred from the 13 common waveform measurement sites.

Frozen focal targets include:

| Disease target | PWDB segment |
|---|---:|
| Right common carotid | 5 |
| Right internal carotid | 12 |
| Left common carotid | 15 |
| Left internal carotid | 16 |
| Left common iliac | 42 |
| Right common iliac | 43 |
| Left external iliac | 44 |
| Right external iliac | 50 |

The frozen main abdominal-aortic path used by the fusiform AAA model is:

```text
28 -> 35 -> 37 -> 39 -> 41
```

This anatomical distinction is intentional: source measurement-site conventions are not repurposed as disease anatomy.

## 4. Common model construction

For a healthy segment, the disease layer builds/retains solver meshes from the subject-specific source geometry and wall model.

Reference area is calculated from the local radius. Wall stiffness (`beta`) and Voigt/source wall terms are generated from the same healthy source parameterization unless the disease specifically modifies them.

Any transformed radius must remain positive and finite. Any wall-stiffness scale must remain positive and finite.

## 5. Focal stenosis geometry

Carotid and iliac stenoses use a smooth raised-cosine diameter-reduction profile over an explicit lesion interval.

The lesion:

- has finite positive length;
- is centered by an explicit center fraction within the selected source segment;
- must fit entirely inside the selected segment;
- matches the healthy radius at both lesion boundaries;
- reaches the requested relative diameter reduction at the center;
- must satisfy an open-vessel executable range `0 <= severity < 1`.

A requested stenosis severity of exactly zero is an exact causal no-op: the healthy network is returned without an excess loss term.

## 6. Carotid stenosis

The `carotid_stenosis` preset selects:

- side: left/right;
- artery: common/internal carotid;
- NASCET-style relative diameter stenosis;
- lesion length;
- lesion center fraction.

The geometry transform applies the raised-cosine narrowing to the chosen canonical carotid segment.

The model is a mechanistic stenosis intervention. The requested stenosis parameter is not a claim of imaging-derived patient stenosis severity.

## 7. Iliac stenosis

The `iliac_stenosis` preset selects:

- side: left/right;
- artery: common/external iliac;
- relative diameter stenosis;
- lesion length;
- lesion center fraction.

It uses the same smooth focal-lumen principle and excess-loss treatment as the carotid model, targeted to the selected iliac source segment.

## 8. Young/Seeley excess stenosis loss

Changing the one-dimensional lumen alone does not represent all focal-stenosis energy loss, especially separation-related loss downstream of a narrowing. VascuQuest therefore supplements the native 1-D momentum model with an implemented Young/Seeley-style localized excess pressure-loss term.

The reference coefficients include the familiar viscous/separation structure:

```text
Kv = 32 (0.83 Ls + 1.64 Ds) / D0 * (A0 / As)^2
Kt = 1.52
```

with corresponding linear and quadratic flow-dependent pressure-loss contributions.

The localized loss is distributed over the lesion support with normalized mesh weights.

Important implementation boundary:

- the empirical excess viscous/separation terms supplement the native one-dimensional solver;
- the original empirical inertial term is not added because the native 1-D momentum equation already contains fluid inertia.

The implementation records the Seeley/Young citation in the disease physics metadata.

## 9. Fusiform abdominal aortic aneurysm

The `fusiform_abdominal_aortic_aneurysm` preset applies an idealized smooth fusiform dilation over the frozen main abdominal-aortic path.

Parameters include:

- absolute maximum model-space lumen diameter;
- aneurysm length;
- center fraction along the frozen path.

The requested aneurysm region must fit entirely inside the frozen path. The requested maximum radius/diameter must exceed the healthy diameter throughout the affected region so the transform represents dilation rather than accidental narrowing.

The smooth raised-cosine spatial envelope blends the healthy local radius into the requested target radius and back to the healthy path.

Affected segment meshes are regenerated from the dilated radius field so area and wall coefficients are consistent with the transformed local geometry.

## 10. AAA non-claims

The one-dimensional fusiform AAA model does **not** represent:

- three-dimensional aneurysm vortices;
- recirculation structures;
- wall shear stress fields;
- asymmetric sac morphology;
- intraluminal thrombus;
- local wall-thickness remodeling;
- rupture mechanics/risk;
- growth/remodeling over time.

Its scientific claim is limited to the systemic/one-dimensional haemodynamic consequences of the explicit idealized dilation within the deployed network model.

## 11. Large-artery stiffening

The `large_artery_stiffening` preset changes wall stiffness over a frozen conduit-artery set while preserving healthy radii.

The causal target is an explicit model-space carotid-femoral PWV value (`target_cfpwv_m_per_s`). VascuQuest computes the subject's baseline model-space differential characteristic PWV from the frozen carotid/femoral travel paths and solves for the wall-stiffness scaling required to reach the admissible target.

The target must not be below the subject's baseline when the condition is specifically “stiffening.”

The transform changes the retained wall `beta` state of the selected large arteries; it does not need to change source radii.

## 12. cfPWV interpretation

The large-artery-stiffening target is a model-space propagation quantity computed from the deployed 1-D wall/network representation and frozen travel paths.

It must not be described as a clinical carotid-femoral tonometry measurement or clinical arterial-age diagnosis.

## 13. Unchanged causal inputs

Unless a preset explicitly modifies a quantity/model parameter, the healthy parent inputs remain unchanged. Examples include the preserved healthy cardiac inflow and terminal-bed state for the four frozen arterial interventions.

This helps isolate the controlled vascular intervention from unrelated physiological changes.

## 14. Modified-segment identity

Every `DiseasePhysicsModel` records the exact canonical segment IDs whose geometry/wall state was modified.

This is important for:

- provenance;
- reproducibility;
- anatomy audits;
- runtime geometry materialization;
- downstream research interpretation.

## 15. Solver coupling

The transformed network and localized loss terms are consumed by the same disease-aware one-dimensional solver framework documented in the reconstruction/runtime references.

The disease transformation itself does not fabricate output P/U/A/Q. Those outputs are recomputed by network integration.

## 16. Zero-intervention behavior

Where a disease parameter permits a true zero/no-op state, the implementation must reproduce the healthy causal state exactly rather than introduce numerical/geometric perturbation merely because a disease object was constructed.

This invariant is tested explicitly for focal stenosis.

## 17. Admissibility

Subject-specific transforms may reject a request when the intervention cannot be represented physically/geometrically within that subject's source anatomy.

Examples include:

- a stenosis lesion that does not fit within the target segment;
- an AAA region that does not fit the frozen path;
- an AAA maximum diameter that does not represent dilation relative to the local healthy vessel;
- a stiffening target below the subject's baseline model-space cfPWV.

Parameterized cohort planning uses these same deployed transforms as the admissibility authority. It does not silently clamp invalid severities.

## 18. Downstream v1 analytics

`vascuquest.analysis`, `stats`, `mechanics`, `spectral`, and `plot` consume outputs generated by these physics; they do not modify these transforms.

For example, a downstream mechanics calculation may derive area distensibility from modelled P/A waveforms, but it cannot change the stenosis geometry or wall-law parameterization that generated those waveforms.

## 19. Citations

The physics layer records references including:

- the canonical PWDB model/publication DOI `10.1152/ajpheart.00218.2019`;
- the source 116-artery model reference recorded by VascuQuest;
- the implemented Seeley/Young stenosis-loss reference for focal stenosis.

Research publications should cite the particular model literature relevant to the intervention being reported.

## 20. Non-claims

Virtual Disease physics does not claim:

- clinical diagnosis or prognosis;
- clinical stenosis grading from imaging;
- device-treatment efficacy;
- plaque composition/vulnerability;
- thrombus formation;
- embolic/stroke risk;
- AAA rupture risk;
- three-dimensional recirculation;
- wall shear stress;
- patient-specific tissue mechanics;
- biological remodeling/progression.

## 21. Related documentation

- [`VIRTUAL_DISEASE.md`](VIRTUAL_DISEASE.md)
- [`VIRTUAL_DISEASE_RECONSTRUCTION.md`](VIRTUAL_DISEASE_RECONSTRUCTION.md)
- [`VIRTUAL_DISEASE_RUNTIME.md`](VIRTUAL_DISEASE_RUNTIME.md)
- [`VIRTUAL_DISEASE_COHORTS.md`](VIRTUAL_DISEASE_COHORTS.md)
