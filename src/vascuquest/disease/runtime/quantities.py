"""Runtime disease quantity definitions and explicit materialisation policy."""

from __future__ import annotations

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.disease.model import DiseaseCondition, DiseaseQuantityStatus
from vascuquest.schema import load_canonical_schema

FLOW_RATE_QUANTITY = QuantityDefinition(
    canonical_name="flow_rate",
    label="Volumetric flow rate",
    description=(
        "Arterial volumetric flow-rate waveform in a Virtual Disease runtime "
        "dataset, calculated as modelled flow velocity multiplied by modelled "
        "luminal area."
    ),
    value_kind="numeric",
    schema_version="1",
    physical_dimension="volume_flow_rate",
    canonical_unit="m^3/s",
    allowed_source_units=(),
    applicable_contexts=("measurement_site",),
    source_aliases=("Q",),
    default_evidence=EvidenceClass.MODELLED,
    citations=("doi:10.1152/ajpheart.00218.2019",),
)


def canonical_quantity(name: str) -> QuantityDefinition:
    if not isinstance(name, str) or not name:
        raise ValueError("quantity name must be non-empty")
    if name == "flow_rate":
        return FLOW_RATE_QUANTITY
    return load_canonical_schema().quantity_schema(name).definition


def runtime_quantity_statuses(
    condition: DiseaseCondition,
) -> tuple[tuple[str, DiseaseQuantityStatus], ...]:
    """Return the complete v1 public/runtime quantity-status declaration.

    Unsupported source quantities are declared explicitly so a runtime dataset
    can never fall back to the healthy source value without a scientific method
    capable of recomputing it in the disease state.

    ``vascular_geometry`` is classified as MODEL_PARAMETER_MODIFIED for every
    frozen preset because the runtime structured vascular-state payload retains
    the resolved geometry *and* wall-mechanical coefficients needed to reproduce
    the disease solver state. In large-artery stiffening the radii remain
    unchanged but the retained beta wall stiffness is modified.
    """

    if not isinstance(condition, DiseaseCondition):
        raise TypeError("condition must be a DiseaseCondition")
    statuses = {
        "pressure": DiseaseQuantityStatus.RECOMPUTED,
        "flow_velocity": DiseaseQuantityStatus.RECOMPUTED,
        "luminal_area": DiseaseQuantityStatus.RECOMPUTED,
        "flow_rate": DiseaseQuantityStatus.DERIVED_FROM_RECOMPUTED,
        "photoplethysmogram": DiseaseQuantityStatus.NOT_SUPPORTED,
        "age": DiseaseQuantityStatus.UNCHANGED_CAUSAL_INPUT,
        "heart_rate": DiseaseQuantityStatus.UNCHANGED_CAUSAL_INPUT,
        "stroke_volume": DiseaseQuantityStatus.UNCHANGED_CAUSAL_INPUT,
        "cardiac_output": DiseaseQuantityStatus.RECOMPUTED,
        "brachial_systolic_pressure": DiseaseQuantityStatus.DERIVED_FROM_RECOMPUTED,
        "aortic_pulse_wave_velocity": DiseaseQuantityStatus.NOT_SUPPORTED,
        "aortic_augmentation_index": DiseaseQuantityStatus.NOT_SUPPORTED,
        "pressure_onset_time": DiseaseQuantityStatus.NOT_SUPPORTED,
        "vascular_geometry": DiseaseQuantityStatus.MODEL_PARAMETER_MODIFIED,
    }
    return tuple(sorted(statuses.items()))


def status_mapping(
    condition: DiseaseCondition,
) -> dict[str, DiseaseQuantityStatus]:
    return dict(runtime_quantity_statuses(condition))


__all__ = [
    "FLOW_RATE_QUANTITY",
    "canonical_quantity",
    "runtime_quantity_statuses",
    "status_mapping",
]
