"""Frozen Virtual Disease v1 preset catalogue.

The catalogue is intentionally non-executable in PR 1. Scientific equations,
validated numerical ranges, and benchmark qualification are introduced only in
the later disease-physics implementation stage.
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


_CONTRACT_ONLY_DOMAIN = (
    "Contract frozen; haemodynamic execution and scientific qualification are not "
    "implemented in Virtual Disease PR 1."
)
_PWDB_CITATION = "doi:10.1152/ajpheart.00218.2019"


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
            "Carotid artery class targeted by the future disease transformation.",
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
        "This descriptor defines request semantics only; it does not create a stenotic geometry.",
        "Scientific admissibility and validated severity limits are deferred to the disease-physics stage.",
    ),
    validated_domain=_CONTRACT_ONLY_DOMAIN,
    citations=(_PWDB_CITATION,),
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
            "Iliac artery class targeted by the future disease transformation.",
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
        "This descriptor defines request semantics only; it does not create a stenotic geometry.",
        "Scientific admissibility and validated severity limits are deferred to the disease-physics stage.",
    ),
    validated_domain=_CONTRACT_ONLY_DOMAIN,
    citations=(_PWDB_CITATION,),
)


FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM = DiseasePresetDescriptor(
    condition=DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM,
    name="Fusiform abdominal aortic aneurysm",
    summary="Idealised fusiform dilatation of the abdominal aorta.",
    parameter_specs=(
        DiseaseParameterSpec(
            "maximum_diameter_m",
            DiseaseParameterKind.NUMBER,
            "Requested maximum aneurysm diameter.",
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
            "Normalized aneurysm-centre position along the eligible abdominal-aortic region.",
            required=False,
            minimum=0.0,
            maximum=1.0,
            unit="1",
            default=0.5,
            has_default=True,
        ),
    ),
    assumptions=(
        "This descriptor defines request semantics only; it does not dilate the aorta.",
        "Wall-property changes and scientific admissibility are deferred to the disease-physics stage.",
    ),
    validated_domain=_CONTRACT_ONLY_DOMAIN,
    citations=(_PWDB_CITATION,),
)


LARGE_ARTERY_STIFFENING = DiseasePresetDescriptor(
    condition=DiseaseCondition.LARGE_ARTERY_STIFFENING,
    name="Large-artery stiffening",
    summary="Haemodynamic phenotype represented by a future increase in large-artery wall stiffness.",
    parameter_specs=(
        DiseaseParameterSpec(
            "target_cfpwv_m_per_s",
            DiseaseParameterKind.NUMBER,
            "Requested target carotid-femoral pulse-wave velocity.",
            minimum=1e-6,
            unit="m/s",
        ),
    ),
    assumptions=(
        "This descriptor defines request semantics only; it does not alter arterial wall mechanics.",
        "The conduit-artery scope and qualified PWV domain are deferred to the disease-physics stage.",
    ),
    validated_domain=_CONTRACT_ONLY_DOMAIN,
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
