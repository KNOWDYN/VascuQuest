"""Frozen executable Virtual Disease v1 preset catalogue.

The catalogue owns user-facing request semantics. Causal equations and
subject-specific scientific admissibility remain implemented in the disease
physics layer; catalogue bounds alone are not clinical validation.
"""

from __future__ import annotations

from collections.abc import Mapping

from vascuquest.errors import AdmissibilityError

from .model import DiseaseCondition, DiseaseSpecification
from .presets.base import (
    DiseaseParameterKind,
    DiseaseParameterSpec,
    DiseasePresetDescriptor,
)


_PWDB_CITATION = "doi:10.1152/ajpheart.00218.2019"
_STENOSIS_LOSS_CITATION = "doi:10.1016/0021-9290(76)90086-5"


CAROTID_STENOSIS = DiseasePresetDescriptor(
    condition=DiseaseCondition.CAROTID_STENOSIS,
    name="Carotid stenosis",
    summary="Idealised focal stenosis of a selected common or internal carotid artery.",
    parameter_specs=(
        DiseaseParameterSpec(
            "side",
            DiseaseParameterKind.TEXT,
            "Anatomical side of the affected carotid artery.",
            allowed_values=("left", "right"),
        ),
        DiseaseParameterSpec(
            "artery",
            DiseaseParameterKind.TEXT,
            "Carotid artery class targeted by the executable disease transformation.",
            allowed_values=("common_carotid", "internal_carotid"),
        ),
        DiseaseParameterSpec(
            "nascet_stenosis",
            DiseaseParameterKind.NUMBER,
            "Requested NASCET-compatible diameter stenosis fraction.",
            minimum=0.0,
            maximum=1.0,
            unit="1",
        ),
        DiseaseParameterSpec(
            "lesion_length_m",
            DiseaseParameterKind.NUMBER,
            "Requested axial lesion length.",
            minimum=1e-6,
            unit="m",
        ),
        DiseaseParameterSpec(
            "lesion_center_fraction",
            DiseaseParameterKind.NUMBER,
            "Normalized lesion-centre position along the selected arterial segment.",
            required=False,
            minimum=0.0,
            maximum=1.0,
            unit="1",
            default=0.5,
            has_default=True,
        ),
    ),
    assumptions=(
        "The lesion is an idealised smooth raised-cosine diameter reduction on the selected source PWDB carotid segment.",
        "The lesion must fit completely inside the selected source segment and executable stenosis must remain below complete geometric occlusion.",
        "A Young/Seeley-based excess pressure-loss term represents focal separation loss without double-counting native 1-D inertia and baseline viscous loss.",
        "The model is mechanistic and MODELLED; it is not a clinical stenosis reconstruction or diagnostic claim.",
    ),
    validated_domain=(
        "Executable v1 mechanistic domain: left/right common or internal carotid source segments; "
        "0 <= diameter stenosis < 1 after disease-physics admissibility; lesion fully contained in the target segment. "
        "Software/mechanistic verification only; not clinically validated."
    ),
    citations=(_PWDB_CITATION, _STENOSIS_LOSS_CITATION),
)


ILIAC_STENOSIS = DiseasePresetDescriptor(
    condition=DiseaseCondition.ILIAC_STENOSIS,
    name="Iliac stenosis",
    summary="Idealised focal stenosis of a selected common or external iliac artery.",
    parameter_specs=(
        DiseaseParameterSpec(
            "side",
            DiseaseParameterKind.TEXT,
            "Anatomical side of the affected iliac artery.",
            allowed_values=("left", "right"),
        ),
        DiseaseParameterSpec(
            "artery",
            DiseaseParameterKind.TEXT,
            "Iliac artery class targeted by the executable disease transformation.",
            allowed_values=("common_iliac", "external_iliac"),
        ),
        DiseaseParameterSpec(
            "diameter_stenosis",
            DiseaseParameterKind.NUMBER,
            "Requested diameter stenosis fraction for the idealised iliac lesion.",
            minimum=0.0,
            maximum=1.0,
            unit="1",
        ),
        DiseaseParameterSpec(
            "lesion_length_m",
            DiseaseParameterKind.NUMBER,
            "Requested axial lesion length.",
            minimum=1e-6,
            unit="m",
        ),
        DiseaseParameterSpec(
            "lesion_center_fraction",
            DiseaseParameterKind.NUMBER,
            "Normalized lesion-centre position along the selected arterial segment.",
            required=False,
            minimum=0.0,
            maximum=1.0,
            unit="1",
            default=0.5,
            has_default=True,
        ),
    ),
    assumptions=(
        "The lesion is an idealised smooth raised-cosine diameter reduction on the selected source PWDB iliac segment.",
        "The lesion must fit completely inside the selected source segment and executable stenosis must remain below complete geometric occlusion.",
        "A Young/Seeley-based excess pressure-loss term represents focal separation loss without double-counting native 1-D inertia and baseline viscous loss.",
        "The model is mechanistic and MODELLED; it is not a clinical stenosis reconstruction or diagnostic claim.",
    ),
    validated_domain=(
        "Executable v1 mechanistic domain: left/right common or external iliac source segments; "
        "0 <= diameter stenosis < 1 after disease-physics admissibility; lesion fully contained in the target segment. "
        "Software/mechanistic verification only; not clinically validated."
    ),
    citations=(_PWDB_CITATION, _STENOSIS_LOSS_CITATION),
)


FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM = DiseasePresetDescriptor(
    condition=DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM,
    name="Fusiform abdominal aortic aneurysm",
    summary="Idealised smooth fusiform dilatation over the main abdominal-aortic PWDB path.",
    parameter_specs=(
        DiseaseParameterSpec(
            "maximum_diameter_m",
            DiseaseParameterKind.NUMBER,
            "Requested absolute maximum model-space aneurysm lumen diameter.",
            minimum=1e-6,
            unit="m",
        ),
        DiseaseParameterSpec(
            "aneurysm_length_m",
            DiseaseParameterKind.NUMBER,
            "Requested axial aneurysm length.",
            minimum=1e-6,
            unit="m",
        ),
        DiseaseParameterSpec(
            "aneurysm_center_fraction",
            DiseaseParameterKind.NUMBER,
            "Normalized aneurysm-centre position along the eligible abdominal-aortic path.",
            required=False,
            minimum=0.0,
            maximum=1.0,
            unit="1",
            default=0.5,
            has_default=True,
        ),
    ),
    assumptions=(
        "The aneurysm is a smooth idealised fusiform dilation restricted to the frozen main abdominal-aortic PWDB path.",
        "The requested maximum diameter must exceed the healthy diameter throughout the covered aneurysm region and the lesion must fit within the eligible path.",
        "Reference area and local wall coefficients are recalculated from the transformed radius using the same constitutive relations as the disease solver.",
        "The model does not represent three-dimensional vortices, recirculation, thrombus, asymmetric sac geometry, rupture mechanics or remodelling.",
    ),
    validated_domain=(
        "Executable v1 mechanistic domain: smooth fusiform dilation confined to PWDB abdominal-aortic segments 28, 35, 37, 39 and 41; "
        "subject-specific geometry admissibility is enforced at runtime. Software/mechanistic verification only; not clinically validated."
    ),
    citations=(_PWDB_CITATION,),
)


LARGE_ARTERY_STIFFENING = DiseasePresetDescriptor(
    condition=DiseaseCondition.LARGE_ARTERY_STIFFENING,
    name="Large-artery stiffening",
    summary="Model-space large-conduit stiffening to a requested carotid-femoral characteristic PWV target.",
    parameter_specs=(
        DiseaseParameterSpec(
            "target_cfpwv_m_per_s",
            DiseaseParameterKind.NUMBER,
            "Requested model-space carotid-femoral characteristic pulse-wave-velocity target.",
            minimum=1e-6,
            unit="m/s",
        ),
    ),
    assumptions=(
        "The target is a model-space characteristic travel-time PWV, not a simulated clinical tonometry measurement.",
        "Wall beta is uniformly scaled across the frozen bilateral large-conduit set while reference geometry, source wall viscosity, inflow and terminal beds remain unchanged.",
        "Targets below the selected subject's baseline model-space cfPWV are rejected because this preset represents stiffening rather than softening.",
        "The model is mechanistic and MODELLED; it is not a clinical arterial-stiffness diagnosis.",
    ),
    validated_domain=(
        "Executable v1 mechanistic domain: target model-space cfPWV at or above each selected subject's baseline model-space cfPWV over the frozen large-conduit set. "
        "Software/mechanistic verification only; not clinically validated."
    ),
    citations=(_PWDB_CITATION,),
)


FROZEN_PRESET_CATALOGUE = (
    CAROTID_STENOSIS,
    ILIAC_STENOSIS,
    FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM,
    LARGE_ARTERY_STIFFENING,
)

if tuple(item.condition for item in FROZEN_PRESET_CATALOGUE) != tuple(DiseaseCondition):
    raise RuntimeError("Virtual Disease v1 catalogue must contain each frozen condition exactly once")


def resolve_condition(value: DiseaseCondition | str) -> DiseaseCondition:
    if isinstance(value, DiseaseCondition):
        return value
    if not isinstance(value, str):
        raise TypeError("condition must be a DiseaseCondition or string")
    try:
        return DiseaseCondition(value)
    except ValueError as exc:
        raise AdmissibilityError(
            f"unknown Virtual Disease v1 condition {value!r}; "
            f"choose {[item.value for item in DiseaseCondition]!r}"
        ) from exc


def presets() -> tuple[DiseasePresetDescriptor, ...]:
    return FROZEN_PRESET_CATALOGUE


def preset(value: DiseaseCondition | str) -> DiseasePresetDescriptor:
    condition = resolve_condition(value)
    for descriptor in FROZEN_PRESET_CATALOGUE:
        if descriptor.condition is condition:
            return descriptor
    raise RuntimeError(f"missing frozen disease descriptor for {condition.value!r}")


def specification(
    condition: DiseaseCondition | str,
    parameters: Mapping[str, object] | None = None,
) -> DiseaseSpecification:
    return preset(condition).specification(parameters)


__all__ = [
    "CAROTID_STENOSIS",
    "FROZEN_PRESET_CATALOGUE",
    "FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM",
    "ILIAC_STENOSIS",
    "LARGE_ARTERY_STIFFENING",
    "preset",
    "presets",
    "resolve_condition",
    "specification",
]
